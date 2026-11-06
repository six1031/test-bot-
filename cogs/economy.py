"""Pillow Palace economy and shop cog (discord.py 2.x, PostgreSQL).

Requires bot.db with async execute(query, *args), fetch(query, *args),
fetchrow(query, *args). Uses the same database connection as other cogs.
Games can use: await bot.get_cog('Economy').add_coins(guild_id, user_id, amount, reason)
"""
import asyncio
import datetime as dt
import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

LOG = logging.getLogger(__name__)
COIN = '🪙'


def money(value):
    return f'{COIN} {int(value):,}'


def clean_name(name):
    return discord.utils.escape_markdown(discord.utils.escape_mentions(name))


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._locks = {}

    async def cog_load(self):
        db = self.bot.db
        await db.execute('''CREATE TABLE IF NOT EXISTS economy_settings (
            guild_id BIGINT PRIMARY KEY,
            daily_amount BIGINT NOT NULL DEFAULT 50,
            weekly_amount BIGINT NOT NULL DEFAULT 300,
            enabled BOOLEAN NOT NULL DEFAULT TRUE
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS economy_balances (
            guild_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
            balance BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0),
            earned BIGINT NOT NULL DEFAULT 0,
            daily_at TIMESTAMPTZ, weekly_at TIMESTAMPTZ,
            PRIMARY KEY (guild_id, user_id)
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS economy_items (
            item_id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            price BIGINT NOT NULL CHECK (price >= 1),
            stock BIGINT CHECK (stock IS NULL OR stock >= 0),
            role_id BIGINT,
            active BOOLEAN NOT NULL DEFAULT TRUE
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS economy_inventory (
            guild_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
            item_id BIGINT NOT NULL REFERENCES economy_items(item_id),
            quantity BIGINT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
            PRIMARY KEY (guild_id, user_id, item_id)
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS economy_transactions (
            id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL, amount BIGINT NOT NULL,
            reason TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )''')
        await db.execute('CREATE INDEX IF NOT EXISTS economy_items_guild_idx ON economy_items(guild_id)')
        await db.execute('CREATE INDEX IF NOT EXISTS economy_transactions_user_idx ON economy_transactions(guild_id,user_id)')

    async def ensure(self, guild_id, user_id):
        await self.bot.db.execute('''INSERT INTO economy_balances(guild_id,user_id)
            VALUES($1,$2) ON CONFLICT DO NOTHING''', guild_id, user_id)

    async def balance_of(self, guild_id, user_id):
        await self.ensure(guild_id, user_id)
        row = await self.bot.db.fetchrow('''SELECT balance FROM economy_balances
            WHERE guild_id=$1 AND user_id=$2''', guild_id, user_id)
        return int(row['balance'])

    async def add_coins(self, guild_id, user_id, amount, reason='Reward'):
        """Public integration for games/XP. Returns new balance."""
        if not isinstance(amount, int) or not 0 < amount <= 1_000_000:
            raise ValueError('Coin award must be between 1 and 1,000,000')
        await self.ensure(guild_id, user_id)
        row = await self.bot.db.fetchrow('''UPDATE economy_balances SET
            balance=balance+$3, earned=earned+$3
            WHERE guild_id=$1 AND user_id=$2 RETURNING balance''', guild_id, user_id, amount)
        await self.log(guild_id, user_id, amount, reason)
        return int(row['balance'])

    async def remove_coins(self, guild_id, user_id, amount, reason='Purchase'):
        """Atomically debit if affordable; returns True/False."""
        if not isinstance(amount, int) or not 0 < amount <= 1_000_000_000:
            raise ValueError('Invalid coin amount')
        await self.ensure(guild_id, user_id)
        row = await self.bot.db.fetchrow('''UPDATE economy_balances SET balance=balance-$3
            WHERE guild_id=$1 AND user_id=$2 AND balance >= $3 RETURNING balance''',
            guild_id, user_id, amount)
        if row is None:
            return False
        await self.log(guild_id, user_id, -amount, reason)
        return True

    async def log(self, guild_id, user_id, amount, reason):
        try:
            await self.bot.db.execute('''INSERT INTO economy_transactions
                (guild_id,user_id,amount,reason) VALUES($1,$2,$3,$4)''',
                guild_id, user_id, amount, reason[:150])
        except Exception:
            LOG.exception('Economy transaction log failed')

    async def settings(self, guild_id):
        await self.bot.db.execute('''INSERT INTO economy_settings(guild_id) VALUES($1)
            ON CONFLICT DO NOTHING''', guild_id)
        return await self.bot.db.fetchrow('SELECT * FROM economy_settings WHERE guild_id=$1', guild_id)

    async def enabled(self, interaction):
        if not interaction.guild:
            await interaction.response.send_message('This command only works in a server.', ephemeral=True)
            return False
        s = await self.settings(interaction.guild.id)
        if not s['enabled']:
            await interaction.response.send_message('The Palace economy is currently disabled.', ephemeral=True)
            return False
        return True

    @app_commands.command(name='balance', description='Check Palace Coins for yourself or another member')
    @app_commands.guild_only()
    async def balance(self, interaction: discord.Interaction, member: discord.Member | None = None):
        if not await self.enabled(interaction): return
        member = member or interaction.user
        amount = await self.balance_of(interaction.guild_id, member.id)
        await interaction.response.send_message(f'**{clean_name(member.display_name)}** has **{money(amount)}** Palace Coins.')

    @app_commands.command(name='daily', description='Claim your daily Palace Coins')
    @app_commands.guild_only()
    async def daily(self, interaction: discord.Interaction):
        await self._claim(interaction, 'daily')

    @app_commands.command(name='weekly', description='Claim your weekly Palace Coins')
    @app_commands.guild_only()
    async def weekly(self, interaction: discord.Interaction):
        await self._claim(interaction, 'weekly')

    async def _claim(self, interaction, kind):
        if not await self.enabled(interaction): return
        await self.ensure(interaction.guild_id, interaction.user.id)
        s = await self.settings(interaction.guild_id)
        amount = int(s[f'{kind}_amount'])
        period = '1 day' if kind == 'daily' else '7 days'
        column = 'daily_at' if kind == 'daily' else 'weekly_at'
        row = await self.bot.db.fetchrow(f'''UPDATE economy_balances
            SET balance=balance+$3, earned=earned+$3, {column}=NOW()
            WHERE guild_id=$1 AND user_id=$2 AND
            ({column} IS NULL OR {column} <= NOW() - INTERVAL '{period}')
            RETURNING balance''', interaction.guild_id, interaction.user.id, amount)
        if row:
            await self.log(interaction.guild_id, interaction.user.id, amount, f'{kind.title()} claim')
            await interaction.response.send_message(f'🎉 You claimed your **{kind}** reward: **{money(amount)}**!\nNew balance: **{money(row["balance"])}**')
            return
        previous = await self.bot.db.fetchrow(f'''SELECT {column} FROM economy_balances
            WHERE guild_id=$1 AND user_id=$2''', interaction.guild_id, interaction.user.id)
        wait = dt.timedelta(days=1 if kind == 'daily' else 7)
        next_at = previous[column] + wait
        await interaction.response.send_message(f'You already claimed your {kind} coins. Come back <t:{int(next_at.timestamp())}:R>.', ephemeral=True)

    @app_commands.command(name='pay', description='Send Palace Coins to another member')
    @app_commands.guild_only()
    async def pay(self, interaction: discord.Interaction, member: discord.Member,
                  amount: app_commands.Range[int, 1, 1000000]):
        if not await self.enabled(interaction): return
        if member.bot or member.id == interaction.user.id:
            await interaction.response.send_message('Choose another human member.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        # Per-sender lock serializes transfers and prevents overlapping transfers.
        lock = self._locks.setdefault((interaction.guild_id, interaction.user.id), asyncio.Lock())
        async with lock:
            if not await self.remove_coins(interaction.guild_id, interaction.user.id, amount, f'Transfer to {member.id}'):
                await interaction.followup.send('You do not have enough coins.', ephemeral=True)
                return
            try:
                await self.add_coins(interaction.guild_id, member.id, amount, f'Transfer from {interaction.user.id}')
            except Exception:
                LOG.exception('Transfer credit failed; attempting refund')
                await self.add_coins(interaction.guild_id, interaction.user.id, amount, 'Transfer refund')
                await interaction.followup.send('Transfer failed and was refunded.', ephemeral=True)
                return
        await interaction.followup.send(f'Sent **{money(amount)}** to {member.mention}.', ephemeral=True)

    @app_commands.command(name='richest', description='See the richest members in the server')
    @app_commands.guild_only()
    async def richest(self, interaction: discord.Interaction):
        if not await self.enabled(interaction): return
        rows = await self.bot.db.fetch('''SELECT user_id,balance FROM economy_balances
            WHERE guild_id=$1 ORDER BY balance DESC, user_id LIMIT 10''', interaction.guild_id)
        if not rows:
            await interaction.response.send_message('No Palace Coins have been earned yet.')
            return
        lines = [f'**{i}.** <@{r["user_id"]}> — {money(r["balance"])}' for i,r in enumerate(rows, 1)]
        await interaction.response.send_message('👑 **Palace Coin Leaderboard**\n' + '\n'.join(lines))

    @app_commands.command(name='shop', description='Browse the Palace Shop')
    @app_commands.guild_only()
    async def shop(self, interaction: discord.Interaction):
        if not await self.enabled(interaction): return
        rows = await self.bot.db.fetch('''SELECT item_id,name,description,price,stock,role_id
            FROM economy_items WHERE guild_id=$1 AND active=TRUE
            ORDER BY price, item_id LIMIT 25''', interaction.guild_id)
        if not rows:
            await interaction.response.send_message('🛍️ The Palace Shop is empty. Check back later!')
            return
        embed = discord.Embed(title='🛍️ Pillow Palace Shop', color=discord.Color.purple(),
                              description='Use `/buy item_id:<number>` to purchase an item. Showing up to 25 items.')
        for r in rows:
            stock = 'Unlimited' if r['stock'] is None else str(r['stock'])
            desc = r['description'] or 'A Palace collectible'
            reward = ' • Discord role' if r['role_id'] else ''
            embed.add_field(name=f'#{r["item_id"]} • {clean_name(r["name"])} — {money(r["price"])}',
                            value=f'{clean_name(desc[:160])}\nStock: {stock}{reward}', inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='inventory', description='View your collected Palace Shop items')
    @app_commands.guild_only()
    async def inventory(self, interaction: discord.Interaction, member: discord.Member | None = None):
        if not await self.enabled(interaction): return
        member = member or interaction.user
        rows = await self.bot.db.fetch('''SELECT i.item_id,i.quantity,s.name
            FROM economy_inventory i JOIN economy_items s ON s.item_id=i.item_id
            WHERE i.guild_id=$1 AND i.user_id=$2 AND i.quantity>0
            ORDER BY s.name LIMIT 40''', interaction.guild_id, member.id)
        if not rows:
            await interaction.response.send_message(f'🎒 {clean_name(member.display_name)} has no items yet.')
            return
        lines = [f'• **{clean_name(r["name"])}** ×{r["quantity"]} (#{r["item_id"]})' for r in rows]
        await interaction.response.send_message(f'🎒 **{clean_name(member.display_name)}’s Inventory**\n' + '\n'.join(lines))

    @app_commands.command(name='buy', description='Buy an item from the Palace Shop using its item ID')
    @app_commands.guild_only()
    async def buy(self, interaction: discord.Interaction, item_id: app_commands.Range[int, 1, 999999999]):
        if not await self.enabled(interaction): return
        await interaction.response.defer(ephemeral=True)
        lock = self._locks.setdefault((interaction.guild_id, interaction.user.id), asyncio.Lock())
        async with lock:
            item = await self.bot.db.fetchrow('''SELECT * FROM economy_items
                WHERE guild_id=$1 AND item_id=$2 AND active=TRUE''', interaction.guild_id, item_id)
            if not item or item['stock'] == 0:
                await interaction.followup.send('That item is unavailable.', ephemeral=True)
                return
            role = None
            if item['role_id']:
                role = interaction.guild.get_role(item['role_id'])
                me = interaction.guild.me
                if role is None or me is None or not me.guild_permissions.manage_roles or role >= me.top_role or role.managed:
                    await interaction.followup.send('This role reward is unavailable. Please contact an admin.', ephemeral=True)
                    return
                if role in interaction.user.roles:
                    await interaction.followup.send('You already have this role.', ephemeral=True)
                    return
            # Reserve stock first (atomic across bot processes), then debit.
            if item['stock'] is not None:
                reserved = await self.bot.db.fetchrow('''UPDATE economy_items SET stock=stock-1
                    WHERE item_id=$1 AND guild_id=$2 AND active=TRUE AND stock>0
                    RETURNING item_id''', item_id, interaction.guild_id)
                if reserved is None:
                    await interaction.followup.send('That item just sold out.', ephemeral=True)
                    return
            try:
                paid = await self.remove_coins(interaction.guild_id, interaction.user.id,
                                               int(item['price']), f'Bought item #{item_id}')
            except Exception:
                if item['stock'] is not None:
                    await self.bot.db.execute('UPDATE economy_items SET stock=stock+1 WHERE item_id=$1', item_id)
                raise
            if not paid:
                if item['stock'] is not None:
                    await self.bot.db.execute('UPDATE economy_items SET stock=stock+1 WHERE item_id=$1', item_id)
                await interaction.followup.send('You do not have enough Palace Coins.', ephemeral=True)
                return
            try:
                if role:
                    await interaction.user.add_roles(role, reason='Palace Shop purchase')
                await self.bot.db.execute('''INSERT INTO economy_inventory(guild_id,user_id,item_id,quantity)
                    VALUES($1,$2,$3,1) ON CONFLICT(guild_id,user_id,item_id)
                    DO UPDATE SET quantity=economy_inventory.quantity+1''',
                    interaction.guild_id, interaction.user.id, item_id)
            except Exception:
                LOG.exception('Shop reward failed; refunding')
                await self.add_coins(interaction.guild_id, interaction.user.id, int(item['price']), 'Purchase refund')
                if item['stock'] is not None:
                    await self.bot.db.execute('UPDATE economy_items SET stock=stock+1 WHERE item_id=$1', item_id)
                await interaction.followup.send('The purchase could not be completed; your coins were refunded.', ephemeral=True)
                return
        await interaction.followup.send(f'🎉 Purchased **{clean_name(item["name"])}** for **{money(item["price"])}**! Check `/inventory`.', ephemeral=True)

    economy = app_commands.Group(name='economy', description='Admin controls for Palace Coins')
    shopsetup = app_commands.Group(name='shopsetup', description='Admin controls for Palace Shop')
    coins = app_commands.Group(name='coins', description='Admin tools for member coin balances')

    @economy.command(name='settings', description='Show economy settings')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def economy_settings(self, interaction: discord.Interaction):
        s = await self.settings(interaction.guild_id)
        await interaction.response.send_message(
            f'**Economy:** {"Enabled" if s["enabled"] else "Disabled"}\n'
            f'Daily: {money(s["daily_amount"])}\nWeekly: {money(s["weekly_amount"])}', ephemeral=True)

    @economy.command(name='configure', description='Set daily and weekly rewards and enable/disable economy')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def economy_configure(self, interaction: discord.Interaction,
                                daily: app_commands.Range[int, 0, 100000] | None = None,
                                weekly: app_commands.Range[int, 0, 1000000] | None = None,
                                enabled: bool | None = None):
        await self.settings(interaction.guild_id)
        await self.bot.db.execute('''UPDATE economy_settings SET
            daily_amount=COALESCE($2,daily_amount), weekly_amount=COALESCE($3,weekly_amount),
            enabled=COALESCE($4,enabled) WHERE guild_id=$1''',
            interaction.guild_id, daily, weekly, enabled)
        await interaction.response.send_message('✅ Economy settings updated.', ephemeral=True)

    @coins.command(name='add', description='Give a member Palace Coins')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def coins_add(self, interaction: discord.Interaction, member: discord.Member,
                        amount: app_commands.Range[int, 1, 1000000]):
        balance = await self.add_coins(interaction.guild_id, member.id, amount, f'Admin grant by {interaction.user.id}')
        await interaction.response.send_message(f'Added {money(amount)} to {member.mention}. New balance: {money(balance)}.', ephemeral=True)

    @coins.command(name='remove', description='Remove coins from a member (up to their balance)')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def coins_remove(self, interaction: discord.Interaction, member: discord.Member,
                           amount: app_commands.Range[int, 1, 1000000]):
        await self.ensure(interaction.guild_id, member.id)
        row = await self.bot.db.fetchrow('''UPDATE economy_balances SET balance=GREATEST(0,balance-$3)
            WHERE guild_id=$1 AND user_id=$2 RETURNING balance''', interaction.guild_id, member.id, amount)
        await self.log(interaction.guild_id, member.id, -amount, f'Admin removal by {interaction.user.id}')
        await interaction.response.send_message(f'Updated {member.mention} balance to {money(row["balance"])}.', ephemeral=True)

    @coins.command(name='set', description='Set a member’s coin balance')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def coins_set(self, interaction: discord.Interaction, member: discord.Member,
                        amount: app_commands.Range[int, 0, 1000000000]):
        await self.ensure(interaction.guild_id, member.id)
        await self.bot.db.execute('''UPDATE economy_balances SET balance=$3
            WHERE guild_id=$1 AND user_id=$2''', interaction.guild_id, member.id, amount)
        await self.log(interaction.guild_id, member.id, 0, f'Admin set balance to {amount} by {interaction.user.id}')
        await interaction.response.send_message(f'Set {member.mention} balance to {money(amount)}.', ephemeral=True)

    @shopsetup.command(name='add', description='Add a collectible or Discord role to the shop')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def shop_add(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 70],
                       price: app_commands.Range[int, 1, 100000000],
                       description: app_commands.Range[str, 1, 250] = 'A Palace collectible',
                       stock: app_commands.Range[int, 0, 1000000] | None = None,
                       role: discord.Role | None = None):
        if role and (role.is_default() or role.managed):
            await interaction.response.send_message('That role cannot be sold.', ephemeral=True)
            return
        if role and (not interaction.guild.me.guild_permissions.manage_roles or role >= interaction.guild.me.top_role):
            await interaction.response.send_message('Move the bot role above the reward role and grant Manage Roles first.', ephemeral=True)
            return
        row = await self.bot.db.fetchrow('''INSERT INTO economy_items
            (guild_id,name,description,price,stock,role_id) VALUES($1,$2,$3,$4,$5,$6)
            RETURNING item_id''', interaction.guild_id, name, description, price, stock,
            role.id if role else None)
        await interaction.response.send_message(f'✅ Added **{clean_name(name)}** as shop item **#{row["item_id"]}**.', ephemeral=True)

    @shopsetup.command(name='edit', description='Edit an existing shop item')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def shop_edit(self, interaction: discord.Interaction,
                        item_id: app_commands.Range[int, 1, 999999999],
                        name: app_commands.Range[str, 1, 70] | None = None,
                        price: app_commands.Range[int, 1, 100000000] | None = None,
                        description: app_commands.Range[str, 1, 250] | None = None,
                        active: bool | None = None):
        row = await self.bot.db.fetchrow('''UPDATE economy_items SET
            name=COALESCE($3,name), price=COALESCE($4,price),
            description=COALESCE($5,description), active=COALESCE($6,active)
            WHERE guild_id=$1 AND item_id=$2 RETURNING item_id''',
            interaction.guild_id, item_id, name, price, description, active)
        await interaction.response.send_message('✅ Shop item updated.' if row else 'Item not found.', ephemeral=True)

    @shopsetup.command(name='stock', description='Set item stock; -1 means unlimited')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def shop_stock(self, interaction: discord.Interaction,
                         item_id: app_commands.Range[int, 1, 999999999],
                         stock: app_commands.Range[int, -1, 1000000]):
        row = await self.bot.db.fetchrow('''UPDATE economy_items SET stock=$3
            WHERE guild_id=$1 AND item_id=$2 RETURNING item_id''',
            interaction.guild_id, item_id, None if stock == -1 else stock)
        await interaction.response.send_message('✅ Stock updated.' if row else 'Item not found.', ephemeral=True)

    @shopsetup.command(name='remove', description='Hide a shop item without deleting purchase history')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def shop_remove(self, interaction: discord.Interaction,
                          item_id: app_commands.Range[int, 1, 999999999]):
        row = await self.bot.db.fetchrow('''UPDATE economy_items SET active=FALSE
            WHERE guild_id=$1 AND item_id=$2 RETURNING item_id''', interaction.guild_id, item_id)
        await interaction.response.send_message('✅ Item hidden from shop.' if row else 'Item not found.', ephemeral=True)

    @app_commands.command(name='coinhistory', description='See your last 10 Palace Coin transactions')
    @app_commands.guild_only()
    async def coinhistory(self, interaction: discord.Interaction):
        if not await self.enabled(interaction): return
        rows = await self.bot.db.fetch('''SELECT amount,reason,created_at FROM economy_transactions
            WHERE guild_id=$1 AND user_id=$2 ORDER BY id DESC LIMIT 10''',
            interaction.guild_id, interaction.user.id)
        if not rows:
            await interaction.response.send_message('No transactions yet.', ephemeral=True)
            return
        lines = [f'{"+" if r["amount"] > 0 else ""}{r["amount"]:,} — {clean_name(r["reason"])} • <t:{int(r["created_at"].timestamp())}:R>' for r in rows]
        await interaction.response.send_message('🧾 **Recent Transactions**\n' + '\n'.join(lines), ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            message = 'Only server administrators can use that command.'
        else:
            LOG.error('Economy command failed: %s', error, exc_info=(type(error), error, error.__traceback__))
            message = 'Something went wrong with the economy command. Check the bot logs.'
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Economy(bot))
