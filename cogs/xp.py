"""Pillow Palace XP system (discord.py 2.x; asyncpg-style bot.db).

Commands: /xpsetup, /rank, /leaderboard, /xpadd, /xpremove,
/xpreset, /xpsync, /xpimporthistory, /xpgif, /xptest.

The historical importer awards 5 XP per eligible historic message (up to 2,000
messages per text channel per run), and records message IDs to avoid duplicates.
It cannot see deleted messages or inaccessible channels.
"""

import asyncio
import logging
import random
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)
LIVE_COOLDOWN = timedelta(seconds=15)
HISTORY_XP = 5
HISTORY_LIMIT_PER_CHANNEL = 2000


def xp_to_reach(level: int) -> int:
    """Total lifetime XP needed to reach level (strictly increasing costs)."""
    # Sum of (100 + 50*n + 10*n*n), for n = 1..level
    return 100 * level + 25 * level * (level + 1) + (10 * level * (level + 1) * (2 * level + 1)) // 6


def level_for_xp(xp: int) -> int:
    lo, hi = 0, 1
    while xp_to_reach(hi) <= xp:
        hi *= 2
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if xp_to_reach(mid) <= xp:
            lo = mid
        else:
            hi = mid
    return lo


class RewardLevelSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="Choose reward level", min_values=1, max_values=1,
                         options=[discord.SelectOption(label=f"Level {i}", value=str(i))
                                  for i in range(5, 101, 5)])

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_level = int(self.values[0])
        await interaction.response.send_message(
            f"Selected Level {self.view.selected_level}. Now choose a server role and press **Save reward**.", ephemeral=True)


class RewardRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Choose an existing level role", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_role = self.values[0]
        await interaction.response.send_message(
            f"Selected {self.values[0].mention}. Press **Save reward** to assign it.", ephemeral=True)


class AnnouncementChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="Choose level-up announcement channel",
                         channel_types=[discord.ChannelType.text], min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        await self.view.cog.bot.db.execute(
            "UPDATE xp_settings SET announce_channel_id=$2 WHERE guild_id=$1",
            interaction.guild_id, channel.id)
        await interaction.response.send_message(f"Level-up announcements set to <#{channel.id}>.", ephemeral=True)


class XPSetupView(discord.ui.View):
    def __init__(self, cog, owner_id: int):
        super().__init__(timeout=600)
        self.cog = cog
        self.owner_id = owner_id
        self.selected_level = None
        self.selected_role = None
        self.add_item(RewardLevelSelect())
        self.add_item(RewardRoleSelect())
        self.add_item(AnnouncementChannelSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the administrator who opened this panel can use it.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Save reward", style=discord.ButtonStyle.success, row=3)
    async def save_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_level is None or self.selected_role is None:
            await interaction.response.send_message("Choose a level and role first.", ephemeral=True)
            return
        role = interaction.guild.get_role(self.selected_role.id)
        if role is None or role.is_default() or role.managed:
            await interaction.response.send_message("That role cannot be managed.", ephemeral=True)
            return
        me = interaction.guild.me
        if not me.guild_permissions.manage_roles or role >= me.top_role:
            await interaction.response.send_message("Give the bot Manage Roles and move its role above that reward role.", ephemeral=True)
            return
        await self.cog.bot.db.execute(
            "INSERT INTO xp_rewards(guild_id, level, role_id) VALUES($1,$2,$3) "
            "ON CONFLICT(guild_id,level) DO UPDATE SET role_id=EXCLUDED.role_id",
            interaction.guild_id, self.selected_level, role.id)
        await interaction.response.send_message(
            f"Saved: Level **{self.selected_level}** → {role.mention}. Use `/xpsync` to apply to existing members.", ephemeral=True)

    @discord.ui.button(label="Remove reward", style=discord.ButtonStyle.secondary, row=3)
    async def remove_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_level is None:
            await interaction.response.send_message("Select a reward level first.", ephemeral=True)
            return
        await self.cog.bot.db.execute(
            "DELETE FROM xp_rewards WHERE guild_id=$1 AND level=$2",
            interaction.guild_id, self.selected_level)
        await interaction.response.send_message(
            f"Removed the Level {self.selected_level} reward. Use `/xpsync` to reconcile existing roles.", ephemeral=True)

    @discord.ui.button(label="Toggle announcements", style=discord.ButtonStyle.primary, row=4)
    async def toggle_announcements(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await self.cog.bot.db.fetchrow(
            "UPDATE xp_settings SET announce_enabled=NOT announce_enabled "
            "WHERE guild_id=$1 RETURNING announce_enabled", interaction.guild_id)
        await interaction.response.send_message(
            f"Level-up announcements: **{'enabled' if row['announce_enabled'] else 'disabled'}**.", ephemeral=True)

    @discord.ui.button(label="Show configured rewards", style=discord.ButtonStyle.secondary, row=4)
    async def show_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
        rows = await self.cog.bot.db.fetch(
            "SELECT level, role_id FROM xp_rewards WHERE guild_id=$1 ORDER BY level", interaction.guild_id)
        msg = "\n".join(f"Level {r['level']}: <@&{r['role_id']}>" for r in rows) or "No rewards configured yet."
        await interaction.response.send_message(msg[:1900], ephemeral=True)


class ImportConfirmView(discord.ui.View):
    def __init__(self, cog, owner_id: int, limit: int):
        super().__init__(timeout=120)
        self.cog, self.owner_id, self.limit = cog, owner_id, limit

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the administrator who requested the import can confirm.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Import message history", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        for item in self.children:
            item.disabled = True
        await self.cog.import_history(interaction, self.limit)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(content="History import cancelled.", view=None)


class XP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._import_locks = set()

    async def cog_load(self):
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS xp_settings (
                guild_id BIGINT PRIMARY KEY,
                announce_channel_id BIGINT,
                announce_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                normal_gif_url TEXT,
                reward_gif_url TEXT,
                level_50_gif_url TEXT,
                level_100_gif_url TEXT
            )
        """)
        # Upgrade existing installations without losing their settings.
        await self.bot.db.execute(
            "ALTER TABLE xp_settings ADD COLUMN IF NOT EXISTS normal_gif_url TEXT")
        await self.bot.db.execute(
            "ALTER TABLE xp_settings ADD COLUMN IF NOT EXISTS reward_gif_url TEXT")
        await self.bot.db.execute(
            "ALTER TABLE xp_settings ADD COLUMN IF NOT EXISTS level_50_gif_url TEXT")
        await self.bot.db.execute(
            "ALTER TABLE xp_settings ADD COLUMN IF NOT EXISTS level_100_gif_url TEXT")
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS xp_members (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                xp BIGINT NOT NULL DEFAULT 0,
                last_award TIMESTAMPTZ,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS xp_rewards (
                guild_id BIGINT NOT NULL,
                level INTEGER NOT NULL,
                role_id BIGINT NOT NULL,
                PRIMARY KEY (guild_id, level)
            )
        """)
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS xp_message_ledger (
                guild_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                PRIMARY KEY (guild_id, message_id)
            )
        """)
        await self.bot.db.execute(
            "CREATE INDEX IF NOT EXISTS xp_members_leaderboard_idx ON xp_members(guild_id, xp DESC)")

    async def ensure_settings(self, guild_id):
        await self.bot.db.execute(
            "INSERT INTO xp_settings(guild_id) VALUES($1) ON CONFLICT DO NOTHING", guild_id)

    async def apply_reward_role(self, member: discord.Member, level: int):
        rewards = await self.bot.db.fetch(
            "SELECT level, role_id FROM xp_rewards WHERE guild_id=$1 ORDER BY level", member.guild.id)
        if not rewards:
            return
        desired = next((r['role_id'] for r in reversed(rewards) if r['level'] <= level), None)
        reward_ids = {r['role_id'] for r in rewards}
        current_ids = {r.id for r in member.roles}
        remove = [r for r in member.roles if r.id in reward_ids and r.id != desired]
        add = member.guild.get_role(desired) if desired and desired not in current_ids else None
        if not remove and not add:
            return
        try:
            # Only touch XP reward roles, leaving all other roles unchanged.
            if remove:
                await member.remove_roles(*remove, reason="XP reward level changed")
            if add:
                await member.add_roles(add, reason="XP reward level reached")
        except discord.Forbidden:
            log.warning("Cannot manage XP reward roles for member %s in %s", member.id, member.guild.id)
        except discord.HTTPException:
            log.exception("Discord rejected XP role change")

    @staticmethod
    def valid_gif_url(url: str) -> bool:
        """Discord embeds need a public HTTPS image URL (ideally direct .gif)."""
        try:
            parsed = urlparse(url)
            return (parsed.scheme == "https" and bool(parsed.netloc)
                    and not parsed.username and not parsed.password
                    and len(url) <= 1800 and not any(c.isspace() for c in url))
        except ValueError:
            return False

    async def build_level_embed(self, guild: discord.Guild, member: discord.Member,
                                level: int, reward_preview: bool = False):
        rewards = await self.bot.db.fetch(
            "SELECT level, role_id FROM xp_rewards WHERE guild_id=$1 AND level<=$2 ORDER BY level DESC",
            guild.id, level)
        # A reward announcement is only used when this exact level unlocks a configured role.
        reward = next((r for r in rewards if r['level'] == level), None)
        is_reward = reward_preview or reward is not None
        settings = await self.bot.db.fetchrow(
            "SELECT normal_gif_url, reward_gif_url, level_50_gif_url, level_100_gif_url FROM xp_settings WHERE guild_id=$1", guild.id)
        # Level 100 has its own GIF; if unset, fall back to the reward GIF.
        if settings and level == 100 and is_reward:
            gif_url = settings['level_100_gif_url'] or settings['reward_gif_url']
        elif settings and level == 50 and is_reward:
            gif_url = settings['level_50_gif_url'] or settings['reward_gif_url']
        else:
            gif_url = settings['reward_gif_url' if is_reward else 'normal_gif_url'] if settings else None
        if is_reward:
            embed = discord.Embed(
                title=f"🏆 Level {level} — Reward Unlocked!",
                description=f"Congratulations {member.mention}! You've reached **Level {level}**!",
                color=discord.Color.gold())
            if reward:
                embed.add_field(name="New level role", value=f"<@&{reward['role_id']}>", inline=False)
            elif reward_preview:
                embed.add_field(name="Reward preview", value="Configure a reward role for this level in `/xpsetup`.", inline=False)
        else:
            embed = discord.Embed(
                title=f"🎉 Level {level}!",
                description=f"Congratulations {member.mention}! You've reached **Level {level}**!",
                color=discord.Color.blurple())
        if gif_url and self.valid_gif_url(gif_url):
            embed.set_image(url=gif_url)
        embed.set_footer(text="Pillow Palace • XP & Levels")
        return embed

    async def announce_level(self, member, old_level, new_level):
        row = await self.bot.db.fetchrow(
            "SELECT announce_channel_id, announce_enabled FROM xp_settings WHERE guild_id=$1", member.guild.id)
        if not row or not row['announce_enabled'] or not row['announce_channel_id']:
            return
        channel = member.guild.get_channel(row['announce_channel_id'])
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            embed = await self.build_level_embed(member.guild, member, new_level)
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        except discord.HTTPException:
            log.exception("Could not send level-up announcement")

    @app_commands.command(name="xpgif", description="Set normal, reward, level 50 or level 100 GIF URL (admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(kind=[
        app_commands.Choice(name="Normal level-up", value="normal"),
        app_commands.Choice(name="Role reward level-up", value="reward"),
        app_commands.Choice(name="Level 50 special", value="50"),
        app_commands.Choice(name="Level 100 special", value="100")])
    @app_commands.describe(kind="Which announcement uses this GIF", url="Public direct GIF URL, or 'remove' to clear")
    async def xpgif(self, interaction: discord.Interaction, kind: app_commands.Choice[str], url: str):
        if not interaction.guild:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        if url.lower().strip() == "remove":
            url = None
        elif not self.valid_gif_url(url):
            return await interaction.response.send_message(
                "Use a public HTTPS GIF/image URL (preferably ending in `.gif`), or `remove`.", ephemeral=True)
        await self.ensure_settings(interaction.guild_id)
        column = {"normal": "normal_gif_url", "reward": "reward_gif_url", "50": "level_50_gif_url", "100": "level_100_gif_url"}[kind.value]
        await self.bot.db.execute(f"UPDATE xp_settings SET {column}=$2 WHERE guild_id=$1",
                                  interaction.guild_id, url)
        await interaction.response.send_message(
            f"{'Saved' if url else 'Cleared'} the **{kind.name}** GIF. Use `/xptest` to preview it.", ephemeral=True)

    @app_commands.command(name="xptest", description="Preview a level-up announcement without awarding XP (admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(kind=[
        app_commands.Choice(name="Normal level-up", value="normal"),
        app_commands.Choice(name="Role reward level-up", value="reward"),
        app_commands.Choice(name="Level 50 special", value="50"),
        app_commands.Choice(name="Level 100 special", value="100")])
    @app_commands.describe(kind="Type of announcement to preview", level="Level to show (optional)")
    async def xptest(self, interaction: discord.Interaction, kind: app_commands.Choice[str],
                     level: app_commands.Range[int, 1, 10000] = None):
        if not interaction.guild:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        await self.ensure_settings(interaction.guild_id)
        if level is None:
            level = 100 if kind.value == "100" else (50 if kind.value == "50" else (10 if kind.value == "reward" else 7))
        embed = await self.build_level_embed(interaction.guild, interaction.user, level,
                                             reward_preview=(kind.value in ("reward", "50", "100")))
        # Force the Level 50 preview to use the special GIF, even when testing a different level.
        if kind.value == "50":
            row = await self.bot.db.fetchrow(
                "SELECT level_50_gif_url, reward_gif_url FROM xp_settings WHERE guild_id=$1", interaction.guild_id)
            embed.title = "🏆 Level 50 — Special Milestone!"
            if row:
                special_url = row['level_50_gif_url'] or row['reward_gif_url']
                if special_url and self.valid_gif_url(special_url):
                    embed.set_image(url=special_url)
                else:
                    embed.set_image(url=None)
        # Force the Level 100 preview to use the special GIF, even when testing a different level.
        if kind.value == "100":
            row = await self.bot.db.fetchrow(
                "SELECT level_100_gif_url, reward_gif_url FROM xp_settings WHERE guild_id=$1", interaction.guild_id)
            embed.title = "🏆 Level 100 — Special Milestone!"
            if row:
                special_url = row['level_100_gif_url'] or row['reward_gif_url']
                if special_url and self.valid_gif_url(special_url):
                    embed.set_image(url=special_url)
                else:
                    embed.set_image(url=None)
        # For a normal preview, force the normal GIF even if a role exists at this level.
        if kind.value == "normal":
            row = await self.bot.db.fetchrow(
                "SELECT normal_gif_url FROM xp_settings WHERE guild_id=$1", interaction.guild_id)
            embed = discord.Embed(title=f"🎉 Level {level}!",
                                  description=f"Congratulations {interaction.user.mention}! You've reached **Level {level}**!",
                                  color=discord.Color.blurple())
            if row and row['normal_gif_url'] and self.valid_gif_url(row['normal_gif_url']):
                embed.set_image(url=row['normal_gif_url'])
            embed.set_footer(text="Pillow Palace • XP & Levels")
        row = await self.bot.db.fetchrow(
            "SELECT announce_channel_id FROM xp_settings WHERE guild_id=$1", interaction.guild_id)
        channel = interaction.guild.get_channel(row['announce_channel_id']) if row and row['announce_channel_id'] else None
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "Set an announcement channel in `/xpsetup` first.", ephemeral=True)
        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            log.exception("Could not send XP test announcement")
            return await interaction.response.send_message(
                "Couldn't post the preview. Check Send Messages and Embed Links permissions.", ephemeral=True)
        await interaction.response.send_message(
            f"Posted a **{kind.name}** preview in {channel.mention}. No XP or roles were changed.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or not isinstance(message.author, discord.Member):
            return
        if not message.content or len(message.content.strip()) < 3:
            return
        if message.webhook_id is not None:
            return
        now = datetime.now(timezone.utc)
        amount = random.randint(15, 25)
        try:
            # One conditional upsert atomically enforces the per-user cooldown.
            row = await self.bot.db.fetchrow("""
                INSERT INTO xp_members(guild_id,user_id,xp,last_award)
                VALUES($1,$2,$3,$4)
                ON CONFLICT(guild_id,user_id) DO UPDATE SET
                    xp=xp_members.xp + EXCLUDED.xp,
                    last_award=EXCLUDED.last_award
                WHERE xp_members.last_award IS NULL OR xp_members.last_award <= $5
                RETURNING xp
            """, message.guild.id, message.author.id, amount, now, now - LIVE_COOLDOWN)
            if row is None:
                return
            await self.bot.db.execute(
                "INSERT INTO xp_message_ledger(guild_id,message_id,user_id) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                message.guild.id, message.id, message.author.id)
            new_xp = row['xp']
            old_level = level_for_xp(max(0, new_xp - amount))
            new_level = level_for_xp(new_xp)
            if new_level > old_level:
                await self.apply_reward_role(message.author, new_level)
                await self.announce_level(message.author, old_level, new_level)
        except Exception:
            log.exception("Failed to award XP for message %s", message.id)

    @app_commands.command(name="xpsetup", description="Open the XP settings panel (administrator only).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def xpsetup(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        await self.ensure_settings(interaction.guild.id)
        await interaction.response.send_message(
            "**Pillow Palace XP settings**\nSelect a level (5–100) and an existing role, then Save reward. "
            "Choose a text channel for level-up announcements. Only the highest earned reward role is kept. "
            "Members can continue levelling beyond 100 and retain the Level 100 reward. "
            "Use `/xpgif` to set GIF links and `/xptest` to preview announcements.",
            view=XPSetupView(self, interaction.user.id), ephemeral=True)

    @app_commands.command(name="rank", description="Show a member's XP level and progress.")
    @app_commands.describe(member="Member to view (defaults to you)")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        if not interaction.guild:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        member = member or interaction.user
        row = await self.bot.db.fetchrow(
            "SELECT xp FROM xp_members WHERE guild_id=$1 AND user_id=$2", interaction.guild.id, member.id)
        xp = int(row['xp']) if row else 0
        level = level_for_xp(xp)
        start, target = xp_to_reach(level), xp_to_reach(level + 1)
        place = await self.bot.db.fetchrow(
            "SELECT COUNT(*) + 1 AS place FROM xp_members WHERE guild_id=$1 AND xp>$2", interaction.guild.id, xp)
        embed = discord.Embed(title=f"⭐ {member.display_name}'s rank", color=discord.Color.blurple())
        embed.add_field(name="Level", value=str(level))
        embed.add_field(name="Total XP", value=f"{xp:,}")
        embed.add_field(name="Leaderboard position", value=f"#{place['place']}")
        embed.add_field(name="Next level", value=f"{xp-start:,} / {target-start:,} XP", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show the top 10 XP earners.")
    async def leaderboard(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        rows = await self.bot.db.fetch(
            "SELECT user_id,xp FROM xp_members WHERE guild_id=$1 ORDER BY xp DESC,user_id LIMIT 10", interaction.guild.id)
        lines = [f"**{i}.** <@{r['user_id']}> — Level **{level_for_xp(r['xp'])}** ({r['xp']:,} XP)"
                 for i, r in enumerate(rows, 1)]
        await interaction.response.send_message(embed=discord.Embed(
            title="🏆 Pillow Palace XP leaderboard", description="\n".join(lines) or "No XP earned yet.",
            color=discord.Color.gold()), allowed_mentions=discord.AllowedMentions.none())

    async def change_xp(self, member, delta=None, reset=False):
        old = await self.bot.db.fetchrow(
            "SELECT xp FROM xp_members WHERE guild_id=$1 AND user_id=$2", member.guild.id, member.id)
        old_xp = int(old['xp']) if old else 0
        new_xp = 0 if reset else max(0, old_xp + delta)
        await self.bot.db.execute("""
            INSERT INTO xp_members(guild_id,user_id,xp) VALUES($1,$2,$3)
            ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=EXCLUDED.xp
        """, member.guild.id, member.id, new_xp)
        await self.apply_reward_role(member, level_for_xp(new_xp))
        return old_xp, new_xp

    @app_commands.command(name="xpadd", description="Add XP to a member (admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def xpadd(self, interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 1000000]):
        _, new = await self.change_xp(member, delta=amount)
        await interaction.response.send_message(f"Added {amount:,} XP to {member.mention}. Total: {new:,}.", ephemeral=True)

    @app_commands.command(name="xpremove", description="Remove XP from a member (admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def xpremove(self, interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 1000000]):
        _, new = await self.change_xp(member, delta=-amount)
        await interaction.response.send_message(f"Removed up to {amount:,} XP from {member.mention}. Total: {new:,}.", ephemeral=True)

    @app_commands.command(name="xpreset", description="Reset a member's XP (admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def xpreset(self, interaction: discord.Interaction, member: discord.Member):
        await self.change_xp(member, reset=True)
        await interaction.response.send_message(f"Reset XP for {member.mention}.", ephemeral=True)

    @app_commands.command(name="xpsync", description="Apply correct reward roles to tracked members (admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def xpsync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        rows = await self.bot.db.fetch("SELECT user_id,xp FROM xp_members WHERE guild_id=$1", interaction.guild_id)
        count = 0
        for r in rows:
            member = interaction.guild.get_member(r['user_id'])
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(r['user_id'])
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue
            await self.apply_reward_role(member, level_for_xp(r['xp']))
            count += 1
        await interaction.followup.send(f"Checked reward roles for {count} tracked members.", ephemeral=True)

    @app_commands.command(name="xpimporthistory", description="Import previous channel messages as starting XP (admin).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(messages_per_channel="Messages to scan per channel (default 2000, maximum 10000)")
    async def xpimporthistory(self, interaction: discord.Interaction,
                              messages_per_channel: app_commands.Range[int, 1, 10000] = HISTORY_LIMIT_PER_CHANNEL):
        if interaction.guild_id in self._import_locks:
            return await interaction.response.send_message("A history import is already running.", ephemeral=True)
        await interaction.response.send_message(
            f"**Import previous messages?**\nThis will scan up to **{messages_per_channel:,}** recent messages "
            f"per accessible text channel and award **{HISTORY_XP} XP** per eligible historical message. "
            "Previously imported messages will not be counted twice. This may take several minutes. "
            "The bot needs View Channel and Read Message History permissions.",
            view=ImportConfirmView(self, interaction.user.id, messages_per_channel), ephemeral=True)

    async def import_history(self, interaction: discord.Interaction, limit: int):
        guild = interaction.guild
        if guild.id in self._import_locks:
            await interaction.followup.send("Another import is running.", ephemeral=True)
            return
        self._import_locks.add(guild.id)
        scanned, awarded, channels = 0, 0, 0
        touched = set()
        try:
            for channel in guild.text_channels:
                me = guild.me
                perms = channel.permissions_for(me)
                if not (perms.view_channel and perms.read_message_history):
                    continue
                channels += 1
                # Import oldest-first within the chosen recent-message window.
                try:
                    messages = [m async for m in channel.history(limit=limit)]
                except (discord.Forbidden, discord.HTTPException):
                    continue
                for msg in reversed(messages):
                    scanned += 1
                    if msg.author.bot or msg.webhook_id or not msg.content or len(msg.content.strip()) < 3:
                        continue
                    # INSERT ... RETURNING makes repeat imports idempotent.
                    inserted = await self.bot.db.fetchrow("""
                        INSERT INTO xp_message_ledger(guild_id,message_id,user_id)
                        VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING user_id
                    """, guild.id, msg.id, msg.author.id)
                    if inserted is None:
                        continue
                    await self.bot.db.execute("""
                        INSERT INTO xp_members(guild_id,user_id,xp) VALUES($1,$2,$3)
                        ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=xp_members.xp+EXCLUDED.xp
                    """, guild.id, msg.author.id, HISTORY_XP)
                    awarded += 1
                    touched.add(msg.author.id)
            # Apply roles once per member, not after every historical message.
            for user_id in touched:
                member = guild.get_member(user_id)
                if member is None:
                    try:
                        member = await guild.fetch_member(user_id)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        continue
                row = await self.bot.db.fetchrow(
                    "SELECT xp FROM xp_members WHERE guild_id=$1 AND user_id=$2", guild.id, user_id)
                if row:
                    await self.apply_reward_role(member, level_for_xp(row['xp']))
            await interaction.followup.send(
                f"✅ History import complete. Scanned **{scanned:,}** messages in **{channels}** channels; "
                f"awarded **{awarded:,}** previously uncounted messages to **{len(touched)}** members "
                f"({awarded * HISTORY_XP:,} total XP).\n"
                "Run `/xpsync` after configuring reward roles if needed.", ephemeral=True)
        except Exception:
            log.exception("XP history import failed")
            await interaction.followup.send(
                f"⚠️ Import stopped early after scanning {scanned:,} messages and awarding {awarded:,}. "
                "You can safely rerun it; previously counted messages are skipped.", ephemeral=True)
        finally:
            self._import_locks.discard(guild.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(XP(bot))
