import asyncio
from datetime import timedelta

import discord
from discord.ext import commands
from discord import app_commands


# ==================================================
# TEMP BAN SUPPORT
# ==================================================

def convert_duration_to_seconds(
    duration: str,
):
    duration = duration.lower().strip()

    try:
        if duration.endswith("h"):
            return int(duration[:-1]) * 3600

        if duration.endswith("m"):
            return int(duration[:-1]) * 60

        if duration.endswith("d"):
            return int(duration[:-1]) * 86400

        if duration == "n/a":
            return None

        return None

    except (ValueError, TypeError):
        return None


async def unban_after_delay(
    guild: discord.Guild,
    user_id: int,
    delay: int,
):
    await asyncio.sleep(delay)

    user = discord.Object(
        id=user_id
    )

    try:
        await guild.unban(
            user,
            reason="Temporary ban expired",
        )

    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException,
    ):
        pass


# ==================================================
# MODERATION COG
# ==================================================

class Moderation(commands.Cog):

    def __init__(
        self,
        bot,
    ):
        self.bot = bot

    # ==================================================
    # ROLE HELPERS
    # ==================================================

    async def get_server_roles(
        self,
        guild: discord.Guild,
    ):
        """
        Get the configured Admin, Mod and Member roles.

        staff_role remains as a temporary fallback
        for older saved server settings.
        """

        settings = await self.bot.db.get_guild_settings(
            guild.id
        )

        if not settings:
            return None, None, None

        admin_role_id = settings.get(
            "admin_role"
        )

        mod_role_id = (
            settings.get("mod_role")
            or settings.get("staff_role")
        )

        member_role_id = settings.get(
            "member_role"
        )

        admin_role = (
            guild.get_role(admin_role_id)
            if admin_role_id
            else None
        )

        mod_role = (
            guild.get_role(mod_role_id)
            if mod_role_id
            else None
        )

        member_role = (
            guild.get_role(member_role_id)
            if member_role_id
            else None
        )

        return (
            admin_role,
            mod_role,
            member_role,
        )

    # ==================================================
    # ADMIN CHECK
    # ==================================================

    async def is_admin(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            return False

        member = interaction.user

        if not isinstance(
            member,
            discord.Member,
        ):
            return False

        # Discord Administrator permission
        if member.guild_permissions.administrator:
            return True

        admin_role, _, _ = (
            await self.get_server_roles(
                interaction.guild
            )
        )

        if (
            admin_role
            and admin_role in member.roles
        ):
            return True

        return False

    # ==================================================
    # MOD OR ADMIN CHECK
    # ==================================================

    async def is_mod_or_admin(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            return False

        member = interaction.user

        if not isinstance(
            member,
            discord.Member,
        ):
            return False

        if member.guild_permissions.administrator:
            return True

        admin_role, mod_role, _ = (
            await self.get_server_roles(
                interaction.guild
            )
        )

        if (
            admin_role
            and admin_role in member.roles
        ):
            return True

        if (
            mod_role
            and mod_role in member.roles
        ):
            return True

        return False

    # ==================================================
    # GET LOG CHANNEL
    # ==================================================

    async def get_log_channel(
        self,
        guild: discord.Guild,
    ):
        settings = await self.bot.db.get_guild_settings(
            guild.id
        )

        if not settings:
            return None

        log_channel_id = settings.get(
            "log_channel"
        )

        if not log_channel_id:
            return None

        channel = guild.get_channel(
            log_channel_id
        )

        if isinstance(
            channel,
            discord.TextChannel,
        ):
            return channel

        return None

    # ==================================================
    # /PING
    # ==================================================

    @app_commands.command(
        name="ping",
        description="Check if the bot is alive.",
    )
    async def ping(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.send_message(
            "🏓 Pong!"
        )

    # ==================================================
    # /BAN
    # ADMIN ONLY
    # ==================================================

    @app_commands.command(
        name="ban",
        description="Ban a member with full logging.",
    )
    @app_commands.describe(
        member="The member to ban",
        ban_type="Temporary or Permanent",
        duration="Duration such as 1h, 2d or 30m",
        rules="Rule numbers broken",
        reason="Reason for the ban",
        evidence="Links to screenshots, videos or messages",
        warnings="Previous warnings or moderation history",
    )
    @app_commands.choices(
        ban_type=[
            app_commands.Choice(
                name="Temporary",
                value="temporary",
            ),
            app_commands.Choice(
                name="Permanent",
                value="permanent",
            ),
        ]
    )
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        ban_type: app_commands.Choice[str],
        duration: str = "N/A",
        rules: str = "N/A",
        reason: str = "No reason provided",
        evidence: str = "None provided",
        warnings: str = "None",
    ):

        # --------------------------------------------------
        # ADMIN ONLY
        # --------------------------------------------------

        if not await self.is_admin(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured **Admin role** can use `/ban`.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # DON'T BAN YOURSELF
        # --------------------------------------------------

        if member.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ You cannot ban yourself.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # BOT ROLE HIERARCHY
        # --------------------------------------------------

        bot_member = interaction.guild.me

        if (
            bot_member is None
            or member.top_role >= bot_member.top_role
        ):
            return await interaction.response.send_message(
                (
                    "❌ I cannot ban that member because "
                    "their highest role is above or equal to mine."
                ),
                ephemeral=True,
            )

        # --------------------------------------------------
        # TEMPORARY BAN
        # --------------------------------------------------

        if ban_type.value == "temporary":

            seconds = convert_duration_to_seconds(
                duration
            )

            if seconds is None:
                return await interaction.response.send_message(
                    (
                        "❌ Invalid duration.\n"
                        "Use something like `30m`, `1h`, or `2d`."
                    ),
                    ephemeral=True,
                )

            try:
                await member.ban(
                    reason=reason
                )

            except discord.Forbidden:
                return await interaction.response.send_message(
                    "❌ I do not have permission to ban that member.",
                    ephemeral=True,
                )

            except discord.HTTPException:
                return await interaction.response.send_message(
                    "❌ Discord rejected the ban request.",
                    ephemeral=True,
                )

            self.bot.loop.create_task(
                unban_after_delay(
                    interaction.guild,
                    member.id,
                    seconds,
                )
            )

            ban_message = (
                f"⏳ {member.mention} has been temporarily "
                f"banned for **{duration}**."
            )

        # --------------------------------------------------
        # PERMANENT BAN
        # --------------------------------------------------

        else:

            try:
                await member.ban(
                    reason=reason
                )

            except discord.Forbidden:
                return await interaction.response.send_message(
                    "❌ I do not have permission to ban that member.",
                    ephemeral=True,
                )

            except discord.HTTPException:
                return await interaction.response.send_message(
                    "❌ Discord rejected the ban request.",
                    ephemeral=True,
                )

            ban_message = (
                f"🔨 {member} has been permanently banned."
            )

        # --------------------------------------------------
        # RESPONSE
        # --------------------------------------------------

        await interaction.response.send_message(
            ban_message
        )

        # --------------------------------------------------
        # LOG EMBED
        # --------------------------------------------------

        embed = discord.Embed(
            title="🔨 Member Banned",
            colour=discord.Colour.red(),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="Member",
            value=f"{member} (`{member.id}`)",
            inline=False,
        )

        embed.add_field(
            name="Banned By",
            value=(
                f"{interaction.user} "
                f"(`{interaction.user.id}`)"
            ),
            inline=False,
        )

        embed.add_field(
            name="Ban Type",
            value=ban_type.name,
            inline=False,
        )

        embed.add_field(
            name="Duration",
            value=duration,
            inline=False,
        )

        embed.add_field(
            name="Rule(s) Broken",
            value=rules,
            inline=False,
        )

        embed.add_field(
            name="Reason",
            value=reason,
            inline=False,
        )

        embed.add_field(
            name="Evidence",
            value=evidence,
            inline=False,
        )

        embed.add_field(
            name="Previous Warnings",
            value=warnings,
            inline=False,
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        log_channel = await self.get_log_channel(
            interaction.guild
        )

        if log_channel:
            try:
                await log_channel.send(
                    embed=embed
                )
            except discord.HTTPException:
                pass

    # ==================================================
    # /KICK
    # MOD + ADMIN
    # ==================================================

    @app_commands.command(
        name="kick",
        description="Kick a member from the server.",
    )
    @app_commands.describe(
        member="The member to kick",
        reason="Reason for the kick",
    )
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):

        if not await self.is_mod_or_admin(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only **Mods or Admins** can use `/kick`.",
                ephemeral=True,
            )

        if member.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ You cannot kick yourself.",
                ephemeral=True,
            )

        bot_member = interaction.guild.me

        if (
            bot_member is None
            or member.top_role >= bot_member.top_role
        ):
            return await interaction.response.send_message(
                "❌ I cannot manage that member because of the role hierarchy.",
                ephemeral=True,
            )

        try:
            await member.kick(
                reason=reason
            )

        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to kick that member.",
                ephemeral=True,
            )

        except discord.HTTPException:
            return await interaction.response.send_message(
                "❌ Discord rejected the kick request.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            (
                f"👢 {member} has been kicked.\n"
                f"**Reason:** {reason}"
            )
        )

    # ==================================================
    # /ADDROLE
    # ADMIN ONLY
    # ==================================================

    @app_commands.command(
        name="addrole",
        description="Add a role to a member.",
    )
    @app_commands.describe(
        member="The member",
        role="The role to add",
    )
    async def addrole(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ):

        if not await self.is_admin(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only **Admins** can use `/addrole`.",
                ephemeral=True,
            )

        bot_member = interaction.guild.me

        if (
            bot_member is None
            or role >= bot_member.top_role
        ):
            return await interaction.response.send_message(
                (
                    "❌ I cannot manage that role.\n"
                    "Move my bot role above it first."
                ),
                ephemeral=True,
            )

        if role.managed:
            return await interaction.response.send_message(
                "❌ That role is managed by Discord or an integration.",
                ephemeral=True,
            )

        try:
            await member.add_roles(
                role,
                reason=(
                    f"Role added by {interaction.user}"
                ),
            )

        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to add that role.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            (
                f"✅ Added **{role.name}** "
                f"to **{member.display_name}**."
            )
        )

    # ==================================================
    # /REMOVEROLE
    # ADMIN ONLY
    # ==================================================

    @app_commands.command(
        name="removerole",
        description="Remove a role from a member.",
    )
    @app_commands.describe(
        member="The member",
        role="The role to remove",
    )
    async def removerole(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ):

        if not await self.is_admin(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only **Admins** can use `/removerole`.",
                ephemeral=True,
            )

        bot_member = interaction.guild.me

        if (
            bot_member is None
            or role >= bot_member.top_role
        ):
            return await interaction.response.send_message(
                (
                    "❌ I cannot manage that role.\n"
                    "Move my bot role above it first."
                ),
                ephemeral=True,
            )

        if role.managed:
            return await interaction.response.send_message(
                "❌ That role is managed by Discord or an integration.",
                ephemeral=True,
            )

        try:
            await member.remove_roles(
                role,
                reason=(
                    f"Role removed by {interaction.user}"
                ),
            )

        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to remove that role.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            (
                f"✅ Removed **{role.name}** "
                f"from **{member.display_name}**."
            )
        )

    # ==================================================
    # /TIMEOUT
    # MOD + ADMIN
    # ==================================================

    @app_commands.command(
        name="timeout",
        description="Timeout a member.",
    )
    @app_commands.describe(
        member="The member to timeout",
        duration="Duration in seconds",
        reason="Reason for the timeout",
    )
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: app_commands.Range[int, 1, 2419200],
        reason: str = "No reason provided",
    ):

        if not await self.is_mod_or_admin(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only **Mods or Admins** can use `/timeout`.",
                ephemeral=True,
            )

        if member.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ You cannot timeout yourself.",
                ephemeral=True,
            )

        bot_member = interaction.guild.me

        if (
            bot_member is None
            or member.top_role >= bot_member.top_role
        ):
            return await interaction.response.send_message(
                "❌ I cannot timeout that member because of the role hierarchy.",
                ephemeral=True,
            )

        until = (
            discord.utils.utcnow()
            + timedelta(
                seconds=duration
            )
        )

        try:
            await member.timeout(
                until,
                reason=reason,
            )

        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to timeout that member.",
                ephemeral=True,
            )

        except discord.HTTPException:
            return await interaction.response.send_message(
                "❌ Discord rejected the timeout request.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            (
                f"⏳ {member.mention} has been timed out "
                f"for **{duration} seconds**.\n"
                f"**Reason:** {reason}"
            )
        )


# ==================================================
# SETUP
# ==================================================

async def setup(
    bot,
):
    await bot.add_cog(
        Moderation(bot)
    )
