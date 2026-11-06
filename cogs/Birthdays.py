"""Pillow Palace birthday cog. discord.py 2.x, asyncpg-compatible bot.db."""
import asyncio
import calendar
import logging
import random
from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands, tasks

log = logging.getLogger(__name__)
UK = ZoneInfo('Europe/London')


def birthday_on(day: int, month: int, year: int | None = None) -> str:
    return f'{day:02d}/{month:02d}' + (f'/{year}' if year else '')


def next_birthday(day: int, month: int, today: date) -> date:
    for y in (today.year, today.year + 1, today.year + 2, today.year + 3, today.year + 4):
        try:
            candidate = date(y, month, day)
        except ValueError:
            # Feb 29 is celebrated on Feb 28 in non-leap years.
            candidate = date(y, 2, 28)
        if candidate >= today:
            return candidate
    return today


def valid_gif_url(url: str) -> bool:
    """Require a direct HTTPS GIF image URL (not a GIF hosting page)."""
    try:
        parsed = urlparse(url.strip())
        return (parsed.scheme == 'https' and bool(parsed.hostname)
                and parsed.path.lower().endswith('.gif')
                and len(url) <= 1500)
    except ValueError:
        return False


class BirthdayGifModal(discord.ui.Modal, title='Set Birthday GIF'):
    gif_link = discord.ui.TextInput(
        label='Direct HTTPS GIF link',
        placeholder='https://media.giphy.com/media/EXAMPLE/giphy.gif',
        max_length=1500,
    )

    def __init__(self, cog, guild_id: int, slot: int):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.slot = slot

    async def on_submit(self, interaction: discord.Interaction):
        url = str(self.gif_link.value).strip()
        if not valid_gif_url(url):
            return await interaction.response.send_message(
                'Use a direct HTTPS .gif image URL, not a GIPHY/Tenor/KLIPY webpage.',
                ephemeral=True,
            )
        await self.cog.save_gif(self.guild_id, self.slot, url)
        await interaction.response.send_message(
            f'🎂 Birthday GIF slot **{self.slot}** saved. Use `/birthdaytest` to preview.', ephemeral=True)


class BirthdayGifManager(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        choices = [discord.SelectOption(label=f'Set GIF {i}', value=f'set:{i}') for i in range(1, 6)]
        choices += [discord.SelectOption(label=f'Remove GIF {i}', value=f'remove:{i}') for i in range(1, 6)]
        selector = discord.ui.Select(placeholder='Choose a GIF slot to set or remove', options=choices)
        selector.callback = self.selected
        self.add_item(selector)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id != self.guild_id or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('Only server managers can edit birthday GIFs.', ephemeral=True)
            return False
        return True

    async def selected(self, interaction: discord.Interaction):
        action, slot_text = interaction.data['values'][0].split(':')
        slot = int(slot_text)
        if action == 'set':
            await interaction.response.send_modal(BirthdayGifModal(self.cog, self.guild_id, slot))
        else:
            await self.cog.save_gif(self.guild_id, slot, None)
            await interaction.response.send_message(f'Birthday GIF slot **{slot}** removed.', ephemeral=True)


class BirthdaySetupView(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        channel = discord.ui.ChannelSelect(
            placeholder='Choose birthday announcement channel',
            channel_types=[discord.ChannelType.text], min_values=1, max_values=1,
        )
        channel.callback = self.channel_selected
        self.add_item(channel)
        role = discord.ui.RoleSelect(placeholder='Choose birthday role (optional)', min_values=1, max_values=1)
        role.callback = self.role_selected
        self.add_item(role)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id != self.guild_id or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('Only server managers can use this panel.', ephemeral=True)
            return False
        return True

    async def channel_selected(self, interaction: discord.Interaction):
        channel = interaction.data['values'][0]
        await self.cog.bot.db.execute('UPDATE birthday_settings SET channel_id=$2 WHERE guild_id=$1', self.guild_id, int(channel))
        await interaction.response.send_message(f'Birthday announcements will be sent to <#{channel}>.', ephemeral=True)

    async def role_selected(self, interaction: discord.Interaction):
        role_id = int(interaction.data['values'][0])
        await self.cog.bot.db.execute('UPDATE birthday_settings SET role_id=$2 WHERE guild_id=$1', self.guild_id, role_id)
        await interaction.response.send_message(f'Birthday role set to <@&{role_id}>.', ephemeral=True)

    @discord.ui.button(label='Toggle announcements', style=discord.ButtonStyle.primary, row=2)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        enabled = await self.cog.bot.db.fetchval('UPDATE birthday_settings SET enabled=NOT enabled WHERE guild_id=$1 RETURNING enabled', self.guild_id)
        await interaction.response.send_message(f'Birthday announcements: {"enabled" if enabled else "disabled"}.', ephemeral=True)

    @discord.ui.button(label='Remove birthday role', style=discord.ButtonStyle.secondary, row=2)
    async def clear_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.bot.db.execute('UPDATE birthday_settings SET role_id=NULL WHERE guild_id=$1', self.guild_id)
        await interaction.response.send_message('Birthday role disabled.', ephemeral=True)

    @discord.ui.button(label='Manage 5 Birthday GIFs', style=discord.ButtonStyle.success, row=2)
    async def set_gif(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            'Select a slot to add, replace or remove a GIF:',
            view=BirthdayGifManager(self.cog, self.guild_id), ephemeral=True)


class Birthdays(commands.Cog):
    birthday = app_commands.Group(name='birthday', description='Birthday commands')

    def __init__(self, bot):
        self.bot = bot
        self.ready = asyncio.Event()

    async def cog_load(self):
        await self.bot.db.execute('''
            CREATE TABLE IF NOT EXISTS birthday_members (
                guild_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
                day SMALLINT NOT NULL, month SMALLINT NOT NULL, birth_year SMALLINT,
                PRIMARY KEY(guild_id,user_id)
            )''')
        await self.bot.db.execute('''
            CREATE TABLE IF NOT EXISTS birthday_settings (
                guild_id BIGINT PRIMARY KEY, channel_id BIGINT,
                role_id BIGINT, enabled BOOLEAN NOT NULL DEFAULT TRUE
            )''')
        await self.bot.db.execute('''
            CREATE TABLE IF NOT EXISTS birthday_announcements (
                guild_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
                celebration_year INTEGER NOT NULL,
                PRIMARY KEY(guild_id,user_id,celebration_year)
            )''')
        await self.bot.db.execute('ALTER TABLE birthday_settings ADD COLUMN IF NOT EXISTS gif_url TEXT')
        await self.bot.db.execute('''
            CREATE TABLE IF NOT EXISTS birthday_gifs (
                guild_id BIGINT NOT NULL,
                slot SMALLINT NOT NULL CHECK(slot BETWEEN 1 AND 5),
                gif_url TEXT NOT NULL,
                PRIMARY KEY(guild_id,slot)
            )''')
        # Preserve an existing single GIF as slot 1, but do not overwrite new settings.
        await self.bot.db.execute('''
            INSERT INTO birthday_gifs(guild_id,slot,gif_url)
            SELECT guild_id,1,gif_url FROM birthday_settings
            WHERE gif_url IS NOT NULL AND gif_url <> ''
            ON CONFLICT(guild_id,slot) DO NOTHING
        ''')
        self.ready.set()
        self.check_birthdays.start()

    def cog_unload(self):
        self.check_birthdays.cancel()

    async def save_gif(self, guild_id: int, slot: int, url: str | None):
        if not 1 <= slot <= 5:
            raise ValueError('Birthday GIF slot must be between 1 and 5')
        if url is None:
            await self.bot.db.execute(
                'DELETE FROM birthday_gifs WHERE guild_id=$1 AND slot=$2', guild_id, slot)
        else:
            await self.bot.db.execute('''
                INSERT INTO birthday_gifs(guild_id,slot,gif_url) VALUES($1,$2,$3)
                ON CONFLICT(guild_id,slot) DO UPDATE SET gif_url=EXCLUDED.gif_url
            ''', guild_id, slot, url)
        # Clear legacy setting so removing slot 1 stays removed on restart.
        await self.bot.db.execute(
            'UPDATE birthday_settings SET gif_url=NULL WHERE guild_id=$1', guild_id)

    async def get_gifs(self, guild_id: int) -> dict[int, str]:
        rows = await self.bot.db.fetch(
            'SELECT slot,gif_url FROM birthday_gifs WHERE guild_id=$1 ORDER BY slot', guild_id)
        return {row['slot']: row['gif_url'] for row in rows if valid_gif_url(row['gif_url'])}

    async def random_gif(self, guild_id: int, slot: int | None = None) -> str | None:
        gifs = await self.get_gifs(guild_id)
        if slot is not None:
            return gifs.get(slot)
        return random.choice(list(gifs.values())) if gifs else None

    @staticmethod
    def birthday_embed(member: discord.Member, gif_url: str | None):
        embed = discord.Embed(
            title='🎉🎂 Happy Birthday!',
            description=(f'Happy Birthday {member.mention}!\n\n'
                         'Everyone at **Pillow Palace** wishes you a wonderful day! 💜'),
            color=discord.Color.magenta(),
        )
        embed.set_footer(text='🎈 Have an amazing birthday!')
        if gif_url and valid_gif_url(gif_url):
            embed.set_image(url=gif_url)
        return embed

    @app_commands.command(name='birthdaygif', description='Set or remove one of five birthday GIFs (admin).')
    @app_commands.describe(slot='GIF slot, from 1 to 5', url='Direct HTTPS .gif link; omit to remove the slot')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def birthdaygif(self, interaction: discord.Interaction,
                          slot: app_commands.Range[int, 1, 5], url: str | None = None):
        if interaction.guild is None:
            return await interaction.response.send_message('Use this in a server.', ephemeral=True)
        if url is not None:
            url = url.strip()
            if not valid_gif_url(url):
                return await interaction.response.send_message(
                    'Please use a direct HTTPS .gif image link, not a webpage.', ephemeral=True)
        await self.save_gif(interaction.guild_id, slot, url)
        await interaction.response.send_message(
            f'🎂 Birthday GIF **{slot}** {"saved" if url else "removed"}.', ephemeral=True)

    @app_commands.command(name='birthdaytest', description='Preview a random or selected birthday GIF (admin).')
    @app_commands.describe(member='Member to feature (defaults to you)',
                           slot='Optional GIF slot 1–5; omit for random selection')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def birthdaytest(self, interaction: discord.Interaction,
                           member: discord.Member | None = None,
                           slot: app_commands.Range[int, 1, 5] | None = None):
        if interaction.guild is None:
            return await interaction.response.send_message('Use this in a server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        settings = await self.bot.db.fetchrow(
            'SELECT channel_id FROM birthday_settings WHERE guild_id=$1', interaction.guild_id)
        if not settings or not settings['channel_id']:
            return await interaction.followup.send(
                'Set an announcement channel with `/birthdaysetup` first.', ephemeral=True)
        channel = interaction.guild.get_channel(settings['channel_id'])
        if not isinstance(channel, discord.TextChannel):
            return await interaction.followup.send('The birthday channel is missing.', ephemeral=True)
        gifs = await self.get_gifs(interaction.guild_id)
        if slot is not None and slot not in gifs:
            return await interaction.followup.send(f'GIF slot {slot} is empty.', ephemeral=True)
        gif_url = gifs[slot] if slot is not None else (random.choice(list(gifs.values())) if gifs else None)
        target = member or interaction.user
        try:
            await channel.send(
                embed=self.birthday_embed(target, gif_url),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (discord.Forbidden, discord.HTTPException):
            log.exception('Birthday test announcement failed in guild %s', interaction.guild_id)
            return await interaction.followup.send('Cannot post in the birthday channel.', ephemeral=True)
        await interaction.followup.send(
            f'🎂 Test posted in {channel.mention} ({"selected slot" if slot else "random GIF"}). '
            'No birthdays or roles were changed.', ephemeral=True)

    @birthday.command(name='set', description='Set your birthday (year optional).')
    @app_commands.describe(day='Day of month', month='Month number', year='Optional birth year')
    async def set_birthday(self, interaction: discord.Interaction, day: app_commands.Range[int, 1, 31], month: app_commands.Range[int, 1, 12], year: app_commands.Range[int, 1900, 2100] = None):
        if interaction.guild is None:
            return await interaction.response.send_message('Use this in a server.', ephemeral=True)
        try:
            date(year or 2000, month, day)
        except ValueError:
            return await interaction.response.send_message('That is not a valid date.', ephemeral=True)
        if year and year > datetime.now(UK).year:
            return await interaction.response.send_message('Birth year cannot be in the future.', ephemeral=True)
        await self.bot.db.execute('''
            INSERT INTO birthday_members(guild_id,user_id,day,month,birth_year)
            VALUES($1,$2,$3,$4,$5)
            ON CONFLICT(guild_id,user_id) DO UPDATE SET day=$3,month=$4,birth_year=$5
        ''', interaction.guild_id, interaction.user.id, day, month, year)
        await interaction.response.send_message(f'🎂 Your birthday is set to **{birthday_on(day,month)}**. Birth year is {"saved privately" if year else "not recorded"}.', ephemeral=True)

    @birthday.command(name='view', description='View your birthday or another member’s.')
    @app_commands.describe(member='Member to look up; leave blank for yourself')
    async def view_birthday(self, interaction: discord.Interaction, member: discord.Member = None):
        if interaction.guild is None:
            return await interaction.response.send_message('Use this in a server.', ephemeral=True)
        member = member or interaction.user
        row = await self.bot.db.fetchrow('SELECT day,month FROM birthday_members WHERE guild_id=$1 AND user_id=$2', interaction.guild_id, member.id)
        if not row:
            return await interaction.response.send_message(f'No birthday saved for {member.display_name}.', ephemeral=True)
        today = datetime.now(UK).date()
        upcoming = next_birthday(row['day'], row['month'], today)
        days = (upcoming-today).days
        await interaction.response.send_message(f'🎂 **{member.display_name}**: **{birthday_on(row["day"],row["month"])}** — {"Today! 🎉" if days == 0 else f"in {days} day(s)"}.', ephemeral=True)

    @birthday.command(name='remove', description='Delete your saved birthday.')
    async def remove_birthday(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message('Use this in a server.', ephemeral=True)
        await self.bot.db.execute('DELETE FROM birthday_members WHERE guild_id=$1 AND user_id=$2', interaction.guild_id, interaction.user.id)
        await interaction.response.send_message('Your birthday has been removed.', ephemeral=True)

    @birthday.command(name='upcoming', description='Show the next 10 birthdays.')
    async def upcoming(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message('Use this in a server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        rows = await self.bot.db.fetch('SELECT user_id,day,month FROM birthday_members WHERE guild_id=$1', interaction.guild_id)
        today = datetime.now(UK).date()
        entries = []
        for row in rows:
            if interaction.guild.get_member(row['user_id']) is None:
                continue
            upcoming = next_birthday(row['day'], row['month'], today)
            entries.append((upcoming, row['user_id']))
        entries.sort()
        lines = [f'🎂 <@{uid}> — {d.strftime("%d %b")} ({(d-today).days} days)' for d, uid in entries[:10]]
        await interaction.followup.send('\n'.join(lines) if lines else 'No upcoming birthdays recorded.', ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name='birthdaysetup', description='Configure birthday announcements and roles (admins).')
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def birthdaysetup(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message('Use this in a server.', ephemeral=True)
        await self.bot.db.execute('INSERT INTO birthday_settings(guild_id) VALUES($1) ON CONFLICT DO NOTHING', interaction.guild_id)
        row = await self.bot.db.fetchrow('SELECT * FROM birthday_settings WHERE guild_id=$1', interaction.guild_id)
        embed = discord.Embed(title='🎂 Pillow Palace • Birthday Setup', description='Use the menus below to choose an announcement channel and optional birthday role.\n\nBirthdays are checked every minute (UK time).', color=discord.Color.magenta())
        embed.add_field(name='Announcement channel', value=f'<#{row["channel_id"]}>' if row['channel_id'] else 'Not set')
        embed.add_field(name='Birthday role', value=f'<@&{row["role_id"]}>' if row['role_id'] else 'None')
        embed.add_field(name='Announcements', value='Enabled' if row['enabled'] else 'Disabled')
        gifs = await self.get_gifs(interaction.guild_id)
        embed.add_field(name='Birthday GIFs', value=f'{len(gifs)}/5 configured • Slots: ' + (', '.join(map(str, gifs)) if gifs else 'None'))
        embed.description += '\n\nManage GIF slots below or with `/birthdaygif`. Each birthday picks a random configured GIF. Preview with `/birthdaytest`.'
        await interaction.response.send_message(embed=embed, view=BirthdaySetupView(self, interaction.guild_id), ephemeral=True)

    @tasks.loop(minutes=1)
    async def check_birthdays(self):
        await self.ready.wait()
        today = datetime.now(UK).date()
        try:
            settings = await self.bot.db.fetch('SELECT * FROM birthday_settings')
            for setting in settings:
                try:
                    await self.process_guild(setting, today)
                except Exception:
                    log.exception('Birthday processing failed for guild %s', setting['guild_id'])
        except Exception:
            log.exception('Birthday checker failed')

    @check_birthdays.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def process_guild(self, setting, today: date):
        guild = self.bot.get_guild(setting['guild_id'])
        if guild is None:
            return
        role = guild.get_role(setting['role_id']) if setting['role_id'] else None
        rows = await self.bot.db.fetch('SELECT user_id,day,month FROM birthday_members WHERE guild_id=$1', guild.id)
        birthday_ids = set()
        for row in rows:
            member = guild.get_member(row['user_id'])
            if member is None:
                continue
            is_birthday = row['day'] == today.day and row['month'] == today.month
            if today.month == 2 and today.day == 28 and not calendar.isleap(today.year):
                is_birthday = is_birthday or (row['day'] == 29 and row['month'] == 2)
            if is_birthday:
                birthday_ids.add(member.id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason='Birthday role')
                    except (discord.Forbidden, discord.HTTPException):
                        log.warning('Could not add birthday role for %s', member.id)
                if not setting['enabled'] or not setting['channel_id']:
                    continue
                channel = guild.get_channel(setting['channel_id'])
                if not isinstance(channel, discord.TextChannel):
                    continue
                # Reserve before sending to prevent duplicate messages after retries.
                inserted = await self.bot.db.fetchrow('''
                    INSERT INTO birthday_announcements(guild_id,user_id,celebration_year)
                    VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING user_id
                ''', guild.id, member.id, today.year)
                if not inserted:
                    continue
                try:
                    await channel.send(embed=self.birthday_embed(member, await self.random_gif(guild.id)), allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
                except (discord.Forbidden, discord.HTTPException):
                    await self.bot.db.execute('DELETE FROM birthday_announcements WHERE guild_id=$1 AND user_id=$2 AND celebration_year=$3', guild.id, member.id, today.year)
                    log.warning('Could not announce birthday for %s', member.id)
        if role:
            # Remove yesterday's birthday role; leave all other roles untouched.
            for member in role.members:
                if member.id not in birthday_ids:
                    try:
                        await member.remove_roles(role, reason='Birthday has ended')
                    except (discord.Forbidden, discord.HTTPException):
                        log.warning('Could not remove birthday role from %s', member.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Birthdays(bot))
