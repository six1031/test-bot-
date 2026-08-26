import traceback
import discord

from discord.ext import commands
from discord import app_commands


DEFAULT_VERIFICATION_MESSAGE = (
    "✅ Welcome {mention}! You are now verified in **{server}**."
)


def render_verification_message(
    template: str,
    member: discord.Member,
) -> str:
    values = {
        "mention": member.mention,
        "display_name": member.display_name,
        "username": member.name,
        "server": member.guild.name,
    }

    try:
        return template.format_map(
            values
        )
    except (
        KeyError,
        ValueError,
    ):
        return template


class Verification(
    commands.Cog
):

    def __init__(
        self,
        bot,
    ):
        self.bot = bot

    async def _get_settings(
        self,
        guild_id: int,
    ):
        try:
            return (
                await self.bot.db
                .get_guild_settings(
                    guild_id
                )
            )

        except Exception:
            traceback.print_exc()
            return None

    async def _send_verified_message(
        self,
        member: discord.Member,
        settings: dict,
    ):
        channel_id = settings.get(
            "verification_channel"
        )

        if not channel_id:
            return

        channel = member.guild.get_channel(
            channel_id
        )

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            return

        template = (
            settings.get(
                "verification_message"
            )
            or DEFAULT_VERIFICATION_MESSAGE
        )

        message = render_verification_message(
            template,
            member,
        )

        try:
            await channel.send(
                message
            )

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            traceback.print_exc()

    # ==================================================
    # /VERIFY
    # Admin + Mod command
    # ==================================================

    @app_commands.command(
        name="verify",
        description="Verify a member and give them the configured Verified role.",
    )
    @app_commands.describe(
        member="The member you want to verify.",
    )
    @app_commands.guild_only()
    async def verify(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        guild = interaction.guild
        staff_member = interaction.user

        if (
            guild is None
            or not isinstance(
                staff_member,
                discord.Member,
            )
        ):
            return await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True,
            )

        settings = await self._get_settings(
            guild.id
        )

        if not settings:
            return await interaction.response.send_message(
                (
                    "❌ Verification has not been configured yet.\n"
                    "Ask an admin to open `/config` → **Verification**."
                ),
                ephemeral=True,
            )

        # Native Discord Administrator always counts as Admin.
        is_native_admin = (
            staff_member.guild_permissions.administrator
        )

        admin_role_id = settings.get(
            "admin_role"
        )

        mod_role_id = (
            settings.get("mod_role")
            or settings.get("staff_role")
        )

        staff_role_ids = {
            role.id
            for role in staff_member.roles
        }

        is_configured_staff = bool(
            (
                admin_role_id
                and admin_role_id in staff_role_ids
            )
            or (
                mod_role_id
                and mod_role_id in staff_role_ids
            )
        )

        if not (
            is_native_admin
            or is_configured_staff
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use `/verify`.",
                ephemeral=True,
            )

        verified_role_id = settings.get(
            "verified_role"
        )

        if not verified_role_id:
            return await interaction.response.send_message(
                (
                    "❌ No Verified role has been configured.\n"
                    "Use `/config` → **Verification** first."
                ),
                ephemeral=True,
            )

        role = guild.get_role(
            verified_role_id
        )

        if role is None:
            return await interaction.response.send_message(
                "❌ The configured Verified role no longer exists.",
                ephemeral=True,
            )

        if member.bot:
            return await interaction.response.send_message(
                "❌ Bots cannot be verified.",
                ephemeral=True,
            )

        if role in member.roles:
            return await interaction.response.send_message(
                f"✅ {member.mention} is already verified.",
                ephemeral=True,
            )

        if role.managed:
            return await interaction.response.send_message(
                "❌ The configured Verified role is managed by Discord.",
                ephemeral=True,
            )

        if role.permissions.administrator:
            return await interaction.response.send_message(
                (
                    "❌ The configured Verified role has Administrator "
                    "permission, so I will not assign it."
                ),
                ephemeral=True,
            )

        settings_admin_role = settings.get(
            "admin_role"
        )

        settings_mod_role = (
            settings.get("mod_role")
            or settings.get("staff_role")
        )

        if role.id in {
            settings_admin_role,
            settings_mod_role,
        }:
            return await interaction.response.send_message(
                (
                    "❌ The Verified role is currently also configured "
                    "as an Admin/Mod role, so I will not assign it."
                ),
                ephemeral=True,
            )

        bot_member = (
            guild.me
            or guild.get_member(
                self.bot.user.id
            )
        )

        if (
            bot_member is None
            or role >= bot_member.top_role
        ):
            return await interaction.response.send_message(
                (
                    "❌ I can't give that role because it is above "
                    "my highest role. Move the bot role higher."
                ),
                ephemeral=True,
            )

        try:
            await member.add_roles(
                role,
                reason=(
                    f"Verified by {staff_member} "
                    f"({staff_member.id}) using /verify"
                ),
            )

        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to give that member the Verified role.",
                ephemeral=True,
            )

        except discord.HTTPException:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ Discord rejected the role update. Please try again.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            f"✅ {member.mention} has been verified and given {role.mention}.",
            ephemeral=True,
        )

    # ==================================================
    # VERIFIED ROLE ADDED
    #
    # This fires whether the role was added by /verify,
    # an admin, another bot, or another part of this bot.
    # ==================================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ):
        if after.bot:
            return

        settings = await self._get_settings(
            after.guild.id
        )

        if not settings:
            return

        verified_role_id = settings.get(
            "verified_role"
        )

        if not verified_role_id:
            return

        before_role_ids = {
            role.id
            for role in before.roles
        }

        after_role_ids = {
            role.id
            for role in after.roles
        }

        if (
            verified_role_id
            not in before_role_ids
            and verified_role_id
            in after_role_ids
        ):
            await self._send_verified_message(
                after,
                settings,
            )


async def setup(
    bot,
):
    await bot.add_cog(
        Verification(
            bot
        )
    )
