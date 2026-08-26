# cogs/setup.py

import asyncio
import traceback
import discord

from discord import app_commands
from discord.ext import commands


# ==================================================
# AUTO ROLE PANEL
# ==================================================

class AutoRoleSelect(discord.ui.RoleSelect):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
        mode: str,
    ):
        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.mode = mode

        if mode == "add":
            placeholder = "Choose roles to add as join auto roles"
        else:
            placeholder = "Choose saved auto roles to remove"

        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=25,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message(
                "❌ This Auto Roles picker isn't for you.",
                ephemeral=True,
            )

        guild = interaction.guild

        if (
            guild is None
            or guild.id != self.guild_id
        ):
            return await interaction.response.send_message(
                "❌ I couldn't find this server.",
                ephemeral=True,
            )

        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ You need Discord Administrator permission.",
                ephemeral=True,
            )

        selected_roles = [
            role
            for role in self.values
            if isinstance(
                role,
                discord.Role,
            )
        ]

        if self.mode == "add":

            allowed = []
            skipped = []

            settings = None

            try:
                settings = (
                    await self.cog.bot.db
                    .get_guild_settings(
                        guild.id
                    )
                )
            except Exception:
                settings = None

            protected_role_ids = set()

            if settings:
                for key in (
                    "admin_role",
                    "mod_role",
                ):
                    role_id = settings.get(
                        key
                    )

                    if role_id:
                        protected_role_ids.add(
                            role_id
                        )

            bot_member = (
                guild.me
                or guild.get_member(
                    self.cog.bot.user.id
                )
            )

            for role in selected_roles:

                if role == guild.default_role:
                    skipped.append(
                        f"{role.name} (@everyone)"
                    )
                    continue

                if role.managed:
                    skipped.append(
                        f"{role.name} (managed role)"
                    )
                    continue

                if (
                    bot_member is None
                    or role >= bot_member.top_role
                ):
                    skipped.append(
                        f"{role.name} (above the bot)"
                    )
                    continue

                if role.id in protected_role_ids:
                    skipped.append(
                        f"{role.name} (Admin/Mod role)"
                    )
                    continue

                if role.permissions.administrator:
                    skipped.append(
                        f"{role.name} (Administrator role)"
                    )
                    continue

                allowed.append(
                    role.id
                )

            if allowed:
                await self.cog._add_auto_role_ids(
                    guild.id,
                    allowed,
                )

            total = len(
                await self.cog._get_auto_role_ids(
                    guild.id
                )
            )

            message = (
                f"✅ Added **{len(allowed)}** Auto Role(s).\n"
                f"📦 **{total}** total Auto Roles are now saved."
            )

            if skipped:
                preview = ", ".join(
                    skipped[:8]
                )

                if len(skipped) > 8:
                    preview += (
                        f", and {len(skipped) - 8} more"
                    )

                message += (
                    "\n\n⚠️ Skipped: "
                    + preview
                )

            await interaction.response.edit_message(
                content=message,
                view=None,
            )

            self.view.stop()
            return

        # --------------------------------------------------
        # REMOVE MODE
        # --------------------------------------------------

        saved_ids = set(
            await self.cog._get_auto_role_ids(
                guild.id
            )
        )

        remove_ids = [
            role.id
            for role in selected_roles
            if role.id in saved_ids
        ]

        if remove_ids:
            await self.cog._remove_auto_role_ids(
                guild.id,
                remove_ids,
            )

        total = len(
            await self.cog._get_auto_role_ids(
                guild.id
            )
        )

        await interaction.response.edit_message(
            content=(
                f"✅ Removed **{len(remove_ids)}** "
                "Auto Role(s).\n"
                f"📦 **{total}** Auto Roles remain."
            ),
            view=None,
        )

        self.view.stop()


class AutoRoleSelectView(discord.ui.View):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
        mode: str,
    ):
        super().__init__(
            timeout=300
        )

        self.add_item(
            AutoRoleSelect(
                cog=cog,
                owner_id=owner_id,
                guild_id=guild_id,
                mode=mode,
            )
        )


class ClearAutoRolesConfirmView(discord.ui.View):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
    ):
        super().__init__(
            timeout=120
        )

        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ This confirmation isn't for you.",
                ephemeral=True,
            )
            return False

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need Discord Administrator permission.",
                ephemeral=True,
            )
            return False

        return True

    @discord.ui.button(
        label="Clear All Auto Roles",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
    )
    async def clear_all(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._clear_auto_role_ids(
            self.guild_id
        )

        self.stop()

        await interaction.response.edit_message(
            content="✅ All join Auto Roles have been cleared.",
            view=None,
        )

    @discord.ui.button(
        label="Cancel",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.stop()

        await interaction.response.edit_message(
            content="✅ Nothing was changed.",
            view=None,
        )


class AutoRolePanelView(discord.ui.View):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
    ):
        super().__init__(
            timeout=600
        )

        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ This Auto Roles panel isn't for you.",
                ephemeral=True,
            )
            return False

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need Discord Administrator permission.",
                ephemeral=True,
            )
            return False

        return True

    async def build_embed(
        self,
        guild: discord.Guild,
    ):
        role_ids = (
            await self.cog._get_auto_role_ids(
                guild.id
            )
        )

        roles = []
        missing = []

        for role_id in role_ids:
            role = guild.get_role(
                role_id
            )

            if role:
                roles.append(
                    role
                )
            else:
                missing.append(
                    role_id
                )

        if roles:
            shown = roles[:50]

            description = "\n".join(
                f"• {role.mention}"
                for role in shown
            )

            if len(roles) > 50:
                description += (
                    f"\n• … and **{len(roles) - 50}** more"
                )

        else:
            description = (
                "No join Auto Roles are configured yet."
            )

        if missing:
            description += (
                f"\n\n⚠️ **{len(missing)}** saved role(s) "
                "no longer exist and will be skipped."
            )

        embed = discord.Embed(
            title="🎭 Join Auto Roles",
            description=description,
            colour=discord.Colour.blurple(),
        )

        embed.add_field(
            name="Saved",
            value=f"**{len(role_ids)}** role(s)",
            inline=True,
        )

        embed.add_field(
            name="How it works",
            value=(
                "Every non-bot member who joins receives "
                "all saved roles the bot is able to manage."
            ),
            inline=False,
        )

        embed.set_footer(
            text=(
                "Add up to 25 roles per selection. "
                "Press Add Roles again to add more."
            )
        )

        return embed

    @discord.ui.button(
        label="Add Roles",
        emoji="➕",
        style=discord.ButtonStyle.success,
    )
    async def add_roles(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            (
                "🎭 **Add Join Auto Roles**\n\n"
                "Select up to **25 roles** below. "
                "You can repeat this as many times as needed."
            ),
            view=AutoRoleSelectView(
                cog=self.cog,
                owner_id=self.owner_id,
                guild_id=self.guild_id,
                mode="add",
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Remove Roles",
        emoji="➖",
        style=discord.ButtonStyle.secondary,
    )
    async def remove_roles(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        role_ids = (
            await self.cog._get_auto_role_ids(
                self.guild_id
            )
        )

        if not role_ids:
            return await interaction.response.send_message(
                "🌸 There are no Auto Roles to remove.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            (
                "🎭 **Remove Join Auto Roles**\n\n"
                "Choose saved Auto Roles to remove. "
                "Selecting a role that isn't saved does nothing."
            ),
            view=AutoRoleSelectView(
                cog=self.cog,
                owner_id=self.owner_id,
                guild_id=self.guild_id,
                mode="remove",
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Refresh",
        emoji="🔄",
        style=discord.ButtonStyle.primary,
    )
    async def refresh(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "❌ I couldn't find this server.",
                ephemeral=True,
            )

        await interaction.response.edit_message(
            embed=(
                await self.build_embed(
                    guild
                )
            ),
            view=self,
        )

    @discord.ui.button(
        label="Clear All",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
    )
    async def clear_all(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            (
                "⚠️ **Clear every Join Auto Role?**\n\n"
                "New members will stop receiving these roles."
            ),
            view=ClearAutoRolesConfirmView(
                cog=self.cog,
                owner_id=self.owner_id,
                guild_id=self.guild_id,
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Close",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.stop()

        await interaction.response.edit_message(
            content="✅ Auto Roles panel closed.",
            embed=None,
            view=None,
        )



# ==================================================
# MAIN CONFIG PANEL
# ==================================================

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


class ConfigRoleSelect(
    discord.ui.RoleSelect
):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
        setting: str,
        label: str,
    ):
        super().__init__(
            placeholder=f"Choose the {label}",
            min_values=1,
            max_values=1,
        )

        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.setting = setting
        self.label = label

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message(
                "❌ This role picker isn't for you.",
                ephemeral=True,
            )

        guild = interaction.guild

        if (
            guild is None
            or guild.id != self.guild_id
        ):
            return await interaction.response.send_message(
                "❌ I couldn't find this server.",
                ephemeral=True,
            )

        role = self.values[0]

        if not isinstance(
            role,
            discord.Role,
        ):
            return await interaction.response.send_message(
                "❌ I couldn't resolve that role.",
                ephemeral=True,
            )

        bot_member = (
            guild.me
            or guild.get_member(
                self.cog.bot.user.id
            )
        )

        if role == guild.default_role:
            return await interaction.response.send_message(
                "❌ `@everyone` cannot be used for this setting.",
                ephemeral=True,
            )

        if role.managed:
            return await interaction.response.send_message(
                "❌ That role is managed by Discord or an integration.",
                ephemeral=True,
            )

        if (
            bot_member is None
            or role >= bot_member.top_role
        ):
            return await interaction.response.send_message(
                "❌ That role must be below the bot's highest role.",
                ephemeral=True,
            )

        if (
            self.setting == "verified_role"
            and role.permissions.administrator
        ):
            return await interaction.response.send_message(
                "❌ The Verified role cannot have Administrator permission.",
                ephemeral=True,
            )

        try:
            await self.cog._save_role_setting(
                guild.id,
                self.setting,
                role.id,
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't save that role.",
                ephemeral=True,
            )

        self.view.stop()

        await interaction.response.edit_message(
            content=(
                f"✅ **{self.label}** set to {role.mention}."
            ),
            view=None,
        )


class ConfigRoleSelectView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
        setting: str,
        label: str,
    ):
        super().__init__(
            timeout=300
        )

        self.add_item(
            ConfigRoleSelect(
                cog=cog,
                owner_id=owner_id,
                guild_id=guild_id,
                setting=setting,
                label=label,
            )
        )


class ConfigChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
        setting: str,
        label: str,
        channel_types: list[discord.ChannelType],
    ):
        super().__init__(
            placeholder=f"Choose the {label}",
            min_values=1,
            max_values=1,
            channel_types=channel_types,
        )

        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.setting = setting
        self.label = label

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message(
                "❌ This channel picker isn't for you.",
                ephemeral=True,
            )

        guild = interaction.guild

        if (
            guild is None
            or guild.id != self.guild_id
        ):
            return await interaction.response.send_message(
                "❌ I couldn't find this server.",
                ephemeral=True,
            )

        channel = self.values[0]

        try:
            await self.cog._save_channel_setting(
                guild.id,
                self.setting,
                channel.id,
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't save that channel.",
                ephemeral=True,
            )

        self.view.stop()

        await interaction.response.edit_message(
            content=(
                f"✅ **{self.label}** set to <#{channel.id}>."
            ),
            view=None,
        )


class ConfigChannelSelectView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
        setting: str,
        label: str,
        channel_types: list[discord.ChannelType],
    ):
        super().__init__(
            timeout=300
        )

        self.add_item(
            ConfigChannelSelect(
                cog=cog,
                owner_id=owner_id,
                guild_id=guild_id,
                setting=setting,
                label=label,
                channel_types=channel_types,
            )
        )


class VerificationMessageModal(
    discord.ui.Modal,
    title="Verification Welcome Message",
):

    message = discord.ui.TextInput(
        label="Message",
        placeholder=(
            "Welcome {mention}! You are now verified in {server}."
        ),
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1500,
    )

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
        current_message: str | None = None,
    ):
        super().__init__()

        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id

        self.message.default = (
            current_message
            or DEFAULT_VERIFICATION_MESSAGE
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message(
                "❌ This modal isn't for you.",
                ephemeral=True,
            )

        value = str(
            self.message.value
        ).strip()

        await self.cog._set_verification_message(
            self.guild_id,
            value,
        )

        await interaction.response.send_message(
            (
                "✅ Verification welcome message saved.\n\n"
                "Available placeholders:\n"
                "`{mention}` `{display_name}` `{username}` `{server}`"
            ),
            ephemeral=True,
        )


class RoleConfigView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
    ):
        super().__init__(
            timeout=600
        )

        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        return await self.cog._panel_interaction_check(
            interaction,
            self.owner_id,
            self.guild_id,
        )

    @discord.ui.button(
        label="Admin Role",
        emoji="👑",
        style=discord.ButtonStyle.danger,
    )
    async def admin_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._send_role_picker(
            interaction,
            self.owner_id,
            self.guild_id,
            "admin_role",
            "Admin Role",
        )

    @discord.ui.button(
        label="Mod Role",
        emoji="🛡️",
        style=discord.ButtonStyle.primary,
    )
    async def mod_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._send_role_picker(
            interaction,
            self.owner_id,
            self.guild_id,
            "mod_role",
            "Mod Role",
        )

    @discord.ui.button(
        label="Member Role",
        emoji="👤",
        style=discord.ButtonStyle.success,
    )
    async def member_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._send_role_picker(
            interaction,
            self.owner_id,
            self.guild_id,
            "member_role",
            "Member Role",
        )

    @discord.ui.button(
        label="Verified Role",
        emoji="✅",
        style=discord.ButtonStyle.secondary,
    )
    async def verified_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._send_role_picker(
            interaction,
            self.owner_id,
            self.guild_id,
            "verified_role",
            "Verified Role",
        )

    @discord.ui.button(
        label="Close",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.stop()

        await interaction.response.edit_message(
            content="✅ Role configuration closed.",
            embed=None,
            view=None,
        )


class ChannelConfigView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
    ):
        super().__init__(
            timeout=600
        )

        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        return await self.cog._panel_interaction_check(
            interaction,
            self.owner_id,
            self.guild_id,
        )

    @discord.ui.button(
        label="Log Channel",
        emoji="📋",
        style=discord.ButtonStyle.primary,
    )
    async def log_channel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._send_channel_picker(
            interaction,
            self.owner_id,
            self.guild_id,
            "log_channel",
            "Log Channel",
            [
                discord.ChannelType.text,
            ],
        )

    @discord.ui.button(
        label="Relationships",
        emoji="💞",
        style=discord.ButtonStyle.primary,
    )
    async def relationship_channel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._send_channel_picker(
            interaction,
            self.owner_id,
            self.guild_id,
            "relationship_channel",
            "Relationship Channel",
            [
                discord.ChannelType.text,
            ],
        )

    @discord.ui.button(
        label="Ticket Category",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
    )
    async def ticket_category(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._send_channel_picker(
            interaction,
            self.owner_id,
            self.guild_id,
            "ticket_category",
            "Ticket Category",
            [
                discord.ChannelType.category,
            ],
        )

    @discord.ui.button(
        label="Member Profiles",
        emoji="🌸",
        style=discord.ButtonStyle.primary,
    )
    async def intro_channel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._send_channel_picker(
            interaction,
            self.owner_id,
            self.guild_id,
            "intro_channel",
            "Member Profiles Channel",
            [
                discord.ChannelType.text,
            ],
        )

    @discord.ui.button(
        label="Close",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.stop()

        await interaction.response.edit_message(
            content="✅ Channel configuration closed.",
            embed=None,
            view=None,
        )


class VerificationConfigView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
    ):
        super().__init__(
            timeout=600
        )

        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        return await self.cog._panel_interaction_check(
            interaction,
            self.owner_id,
            self.guild_id,
        )

    async def build_embed(
        self,
        guild: discord.Guild,
    ):
        settings = (
            await self.cog._get_settings(
                guild.id
            )
        )

        verified_role_id = (
            settings.get("verified_role")
            if settings
            else None
        )

        channel_id = (
            settings.get("verification_channel")
            if settings
            else None
        )

        message = (
            settings.get("verification_message")
            if settings
            else None
        )

        role_text = (
            f"<@&{verified_role_id}>"
            if verified_role_id
            else "Not configured"
        )

        channel_text = (
            f"<#{channel_id}>"
            if channel_id
            else "Disabled / not configured"
        )

        embed = discord.Embed(
            title="✅ Verification Configuration",
            colour=discord.Colour.green(),
        )

        embed.add_field(
            name="Verified Role",
            value=role_text,
            inline=False,
        )

        embed.add_field(
            name="Welcome Channel",
            value=channel_text,
            inline=False,
        )

        embed.add_field(
            name="Welcome Message",
            value=(
                message
                or DEFAULT_VERIFICATION_MESSAGE
            )[:1000],
            inline=False,
        )

        embed.add_field(
            name="/verify",
            value=(
                "Public command. A member can use `/verify` "
                "to give themselves the configured Verified role."
            ),
            inline=False,
        )

        return embed

    @discord.ui.button(
        label="Verified Role",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def verified_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._send_role_picker(
            interaction,
            self.owner_id,
            self.guild_id,
            "verified_role",
            "Verified Role",
        )

    @discord.ui.button(
        label="Welcome Channel",
        emoji="💬",
        style=discord.ButtonStyle.primary,
    )
    async def welcome_channel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._send_channel_picker(
            interaction,
            self.owner_id,
            self.guild_id,
            "verification_channel",
            "Verification Welcome Channel",
            [
                discord.ChannelType.text,
            ],
        )

    @discord.ui.button(
        label="Welcome Message",
        emoji="✏️",
        style=discord.ButtonStyle.primary,
    )
    async def welcome_message(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        settings = await self.cog._get_settings(
            self.guild_id
        )

        current = (
            settings.get("verification_message")
            if settings
            else None
        )

        await interaction.response.send_modal(
            VerificationMessageModal(
                cog=self.cog,
                owner_id=self.owner_id,
                guild_id=self.guild_id,
                current_message=current,
            )
        )

    @discord.ui.button(
        label="Preview",
        emoji="👀",
        style=discord.ButtonStyle.secondary,
    )
    async def preview(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        settings = await self.cog._get_settings(
            self.guild_id
        )

        template = (
            settings.get("verification_message")
            if settings
            else None
        ) or DEFAULT_VERIFICATION_MESSAGE

        preview = render_verification_message(
            template,
            interaction.user,
        )

        await interaction.response.send_message(
            preview,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Disable Welcome",
        emoji="🔕",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def disable_welcome(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog._set_verification_channel(
            self.guild_id,
            None,
        )

        await interaction.response.send_message(
            "✅ Verification welcome messages are disabled.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Close",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.stop()

        await interaction.response.edit_message(
            content="✅ Verification configuration closed.",
            embed=None,
            view=None,
        )


class ConfigPanelView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
        owner_id: int,
        guild_id: int,
    ):
        super().__init__(
            timeout=900
        )

        self.cog = cog
        self.owner_id = owner_id
        self.guild_id = guild_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        return await self.cog._panel_interaction_check(
            interaction,
            self.owner_id,
            self.guild_id,
        )

    async def build_embed(
        self,
        guild: discord.Guild,
    ):
        settings = await self.cog._get_settings(
            guild.id
        )

        if not settings:
            settings = {}

        def role_value(
            key: str,
        ):
            role_id = settings.get(
                key
            )

            return (
                f"<@&{role_id}>"
                if role_id
                else "Not configured"
            )

        def channel_value(
            key: str,
        ):
            channel_id = settings.get(
                key
            )

            return (
                f"<#{channel_id}>"
                if channel_id
                else "Not configured"
            )

        auto_roles = (
            await self.cog._get_auto_role_ids(
                guild.id
            )
        )

        embed = discord.Embed(
            title="⚙️ Server Configuration",
            description=(
                "Use the buttons below to manage the bot's "
                "server settings."
            ),
            colour=discord.Colour.blurple(),
        )

        embed.add_field(
            name="Command Roles",
            value=(
                f"👑 Admin: {role_value('admin_role')}\n"
                f"🛡️ Mod: {role_value('mod_role')}\n"
                f"👤 Member: {role_value('member_role')}"
            ),
            inline=False,
        )

        embed.add_field(
            name="Verification",
            value=(
                f"✅ Role: {role_value('verified_role')}\n"
                f"💬 Welcome: {channel_value('verification_channel')}"
            ),
            inline=False,
        )

        embed.add_field(
            name="Join Auto Roles",
            value=f"🎭 **{len(auto_roles)}** saved",
            inline=True,
        )

        embed.add_field(
            name="Channels",
            value=(
                f"📋 Logs: {channel_value('log_channel')}\n"
                f"💞 Relationships: {channel_value('relationship_channel')}\n"
                f"🌸 Member Profiles: {channel_value('intro_channel')}"
            ),
            inline=False,
        )

        ticket_category = settings.get(
            "ticket_category"
        )

        embed.add_field(
            name="Tickets",
            value=(
                f"🎫 Category: <#{ticket_category}>"
                if ticket_category
                else "🎫 Category: Not configured"
            ),
            inline=False,
        )

        embed.set_footer(
            text=(
                "Existing /setup and specialist setup commands "
                "still work too."
            )
        )

        return embed

    @discord.ui.button(
        label="Roles",
        emoji="🛡️",
        style=discord.ButtonStyle.primary,
    )
    async def roles(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "🛡️ **Command Role Configuration**",
            view=RoleConfigView(
                cog=self.cog,
                owner_id=self.owner_id,
                guild_id=self.guild_id,
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Auto Roles",
        emoji="🎭",
        style=discord.ButtonStyle.success,
    )
    async def auto_roles(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild = interaction.guild

        panel = AutoRolePanelView(
            cog=self.cog,
            owner_id=self.owner_id,
            guild_id=self.guild_id,
        )

        embed = await panel.build_embed(
            guild
        )

        await interaction.response.send_message(
            embed=embed,
            view=panel,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Verification",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def verification(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild = interaction.guild

        panel = VerificationConfigView(
            cog=self.cog,
            owner_id=self.owner_id,
            guild_id=self.guild_id,
        )

        embed = await panel.build_embed(
            guild
        )

        await interaction.response.send_message(
            embed=embed,
            view=panel,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Channels",
        emoji="📁",
        style=discord.ButtonStyle.primary,
    )
    async def channels(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "📁 **Channel Configuration**",
            view=ChannelConfigView(
                cog=self.cog,
                owner_id=self.owner_id,
                guild_id=self.guild_id,
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Refresh",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def refresh(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild = interaction.guild

        await interaction.response.edit_message(
            embed=(
                await self.build_embed(
                    guild
                )
            ),
            view=self,
        )

    @discord.ui.button(
        label="Close",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.stop()

        await interaction.response.edit_message(
            content="✅ Configuration panel closed.",
            embed=None,
            view=None,
        )


# ==================================================
# SETUP COG
# ==================================================

class SetupCog(commands.Cog):

    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot

    # ==================================================
    # AUTO ROLE DATABASE
    # ==================================================

    async def cog_load(self):
        db_obj = getattr(
            self.bot,
            "db",
            None,
        )

        if (
            not db_obj
            or not callable(
                getattr(
                    db_obj,
                    "execute",
                    None,
                )
            )
        ):
            return

        # This mirrors database.run_migrations so the panel is safe
        # even if this cog is loaded independently during development.
        await db_obj.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_auto_role_entries (
                guild_id BIGINT NOT NULL,
                role_id BIGINT NOT NULL,
                PRIMARY KEY (
                    guild_id,
                    role_id
                )
            )
            """
        )

        await db_obj.execute(
            """
            ALTER TABLE guild_settings
            ADD COLUMN IF NOT EXISTS verification_channel BIGINT
            """
        )

        await db_obj.execute(
            """
            ALTER TABLE guild_settings
            ADD COLUMN IF NOT EXISTS verification_message TEXT
            """
        )

        await db_obj.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'guild_auto_roles'
                      AND column_name = 'auto_role_1'
                ) THEN
                    INSERT INTO guild_auto_role_entries (
                        guild_id,
                        role_id
                    )
                    SELECT
                        guild_id,
                        roles.role_id
                    FROM guild_auto_roles
                    CROSS JOIN LATERAL UNNEST(
                        ARRAY[
                            auto_role_1,
                            auto_role_2,
                            auto_role_3
                        ]
                    ) AS roles(role_id)
                    WHERE roles.role_id IS NOT NULL
                    ON CONFLICT (
                        guild_id,
                        role_id
                    )
                    DO NOTHING;
                END IF;
            END
            $$;
            """
        )

    async def _get_auto_role_ids(
        self,
        guild_id: int,
    ) -> list[int]:

        db_obj = getattr(
            self.bot,
            "db",
            None,
        )

        if not db_obj:
            return []

        helper = getattr(
            db_obj,
            "get_guild_auto_roles",
            None,
        )

        if callable(helper):
            return await helper(
                guild_id
            )

        rows = await db_obj.fetch(
            """
            SELECT role_id
            FROM guild_auto_role_entries
            WHERE guild_id = $1
            ORDER BY role_id
            """,
            guild_id,
        )

        return [
            row["role_id"]
            for row in rows
        ]

    async def _add_auto_role_ids(
        self,
        guild_id: int,
        role_ids: list[int],
    ):
        db_obj = getattr(
            self.bot,
            "db",
            None,
        )

        if not db_obj:
            return

        helper = getattr(
            db_obj,
            "add_guild_auto_roles",
            None,
        )

        if callable(helper):
            await helper(
                guild_id,
                role_ids,
            )
            return

        await db_obj.execute(
            """
            INSERT INTO guild_auto_role_entries (
                guild_id,
                role_id
            )
            SELECT
                $1,
                roles.role_id
            FROM UNNEST(
                $2::BIGINT[]
            ) AS roles(role_id)
            ON CONFLICT (
                guild_id,
                role_id
            )
            DO NOTHING
            """,
            guild_id,
            role_ids,
        )

    async def _remove_auto_role_ids(
        self,
        guild_id: int,
        role_ids: list[int],
    ):
        db_obj = getattr(
            self.bot,
            "db",
            None,
        )

        if not db_obj:
            return

        helper = getattr(
            db_obj,
            "remove_guild_auto_roles",
            None,
        )

        if callable(helper):
            await helper(
                guild_id,
                role_ids,
            )
            return

        await db_obj.execute(
            """
            DELETE FROM guild_auto_role_entries
            WHERE guild_id = $1
              AND role_id = ANY(
                  $2::BIGINT[]
              )
            """,
            guild_id,
            role_ids,
        )

    async def _clear_auto_role_ids(
        self,
        guild_id: int,
    ):
        db_obj = getattr(
            self.bot,
            "db",
            None,
        )

        if not db_obj:
            return

        helper = getattr(
            db_obj,
            "clear_guild_auto_roles",
            None,
        )

        if callable(helper):
            await helper(
                guild_id
            )
            return

        await db_obj.execute(
            """
            DELETE FROM guild_auto_role_entries
            WHERE guild_id = $1
            """,
            guild_id,
        )

    # ==================================================
    # CONFIG PANEL HELPERS
    # ==================================================

    async def _get_settings(
        self,
        guild_id: int,
    ):
        db_obj = getattr(
            self.bot,
            "db",
            None,
        )

        if not db_obj:
            return None

        return await db_obj.get_guild_settings(
            guild_id
        )

    async def _panel_interaction_check(
        self,
        interaction: discord.Interaction,
        owner_id: int,
        guild_id: int,
    ) -> bool:
        if interaction.user.id != owner_id:
            await interaction.response.send_message(
                "❌ This configuration panel isn't for you.",
                ephemeral=True,
            )
            return False

        guild = interaction.guild

        if (
            guild is None
            or guild.id != guild_id
        ):
            await interaction.response.send_message(
                "❌ I couldn't find this server.",
                ephemeral=True,
            )
            return False

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need Discord Administrator permission.",
                ephemeral=True,
            )
            return False

        return True

    async def _save_role_setting(
        self,
        guild_id: int,
        setting: str,
        role_id: int,
    ):
        db_obj = self.bot.db

        if setting == "admin_role":
            await db_obj.upsert_guild_settings(
                guild_id=guild_id,
                admin_role_id=role_id,
            )

        elif setting == "mod_role":
            await db_obj.upsert_guild_settings(
                guild_id=guild_id,
                mod_role_id=role_id,
            )

        elif setting == "member_role":
            await db_obj.upsert_guild_settings(
                guild_id=guild_id,
                member_role_id=role_id,
            )

        elif setting == "verified_role":
            helper = getattr(
                db_obj,
                "set_verified_role",
                None,
            )

            if callable(helper):
                await helper(
                    guild_id,
                    role_id,
                )
            else:
                await db_obj.upsert_guild_settings(
                    guild_id=guild_id,
                    verified_role_id=role_id,
                )

        else:
            raise ValueError(
                "Unknown role setting."
            )

    async def _save_channel_setting(
        self,
        guild_id: int,
        setting: str,
        channel_id: int,
    ):
        db_obj = self.bot.db

        if setting == "log_channel":
            await db_obj.upsert_guild_settings(
                guild_id=guild_id,
                log_channel_id=channel_id,
            )

        elif setting == "relationship_channel":
            await db_obj.upsert_guild_settings(
                guild_id=guild_id,
                marriage_channel_id=channel_id,
                relationship_channel_id=channel_id,
            )

        elif setting == "ticket_category":
            await db_obj.upsert_guild_settings(
                guild_id=guild_id,
                ticket_category_id=channel_id,
            )

        elif setting == "intro_channel":
            await db_obj.upsert_guild_settings(
                guild_id=guild_id,
                intro_channel_id=channel_id,
            )

        elif setting == "verification_channel":
            await self._set_verification_channel(
                guild_id,
                channel_id,
            )

        else:
            raise ValueError(
                "Unknown channel setting."
            )

    async def _set_verification_channel(
        self,
        guild_id: int,
        channel_id: int | None,
    ):
        db_obj = self.bot.db

        helper = getattr(
            db_obj,
            "set_verification_channel",
            None,
        )

        if callable(helper):
            await helper(
                guild_id,
                channel_id,
            )
            return

        await db_obj.execute(
            """
            INSERT INTO guild_settings (
                guild_id,
                verification_channel
            )
            VALUES ($1, $2)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                verification_channel = EXCLUDED.verification_channel
            """,
            guild_id,
            channel_id,
        )

    async def _set_verification_message(
        self,
        guild_id: int,
        message: str | None,
    ):
        db_obj = self.bot.db

        helper = getattr(
            db_obj,
            "set_verification_message",
            None,
        )

        if callable(helper):
            await helper(
                guild_id,
                message,
            )
            return

        await db_obj.execute(
            """
            INSERT INTO guild_settings (
                guild_id,
                verification_message
            )
            VALUES ($1, $2)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                verification_message = EXCLUDED.verification_message
            """,
            guild_id,
            message,
        )

    async def _send_role_picker(
        self,
        interaction: discord.Interaction,
        owner_id: int,
        guild_id: int,
        setting: str,
        label: str,
    ):
        await interaction.response.send_message(
            f"Choose the **{label}** below.",
            view=ConfigRoleSelectView(
                cog=self,
                owner_id=owner_id,
                guild_id=guild_id,
                setting=setting,
                label=label,
            ),
            ephemeral=True,
        )

    async def _send_channel_picker(
        self,
        interaction: discord.Interaction,
        owner_id: int,
        guild_id: int,
        setting: str,
        label: str,
        channel_types: list[discord.ChannelType],
    ):
        await interaction.response.send_message(
            f"Choose the **{label}** below.",
            view=ConfigChannelSelectView(
                cog=self,
                owner_id=owner_id,
                guild_id=guild_id,
                setting=setting,
                label=label,
                channel_types=channel_types,
            ),
            ephemeral=True,
        )

    # ==================================================
    # AUTO ROLES ON MEMBER JOIN
    # ==================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member: discord.Member,
    ):
        if member.bot:
            return

        try:
            role_ids = (
                await self._get_auto_role_ids(
                    member.guild.id
                )
            )

            if not role_ids:
                return

            bot_member = (
                member.guild.me
                or member.guild.get_member(
                    self.bot.user.id
                )
            )

            if bot_member is None:
                return

            roles_to_add = []

            for role_id in role_ids:

                role = member.guild.get_role(
                    role_id
                )

                if role is None:
                    continue

                if role == member.guild.default_role:
                    continue

                if role.managed:
                    continue

                if role >= bot_member.top_role:
                    continue

                if role.permissions.administrator:
                    continue

                roles_to_add.append(
                    role
                )

            if roles_to_add:
                await member.add_roles(
                    *roles_to_add,
                    reason="Server setup join Auto Roles",
                )

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            traceback.print_exc()

        except Exception:
            traceback.print_exc()

    # ==================================================
    # /CONFIG
    # ==================================================

    @app_commands.command(
        name="config",
        description="Open the server configuration panel.",
    )
    @app_commands.default_permissions(
        administrator=True
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def config_command(
        self,
        interaction: discord.Interaction,
    ):
        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True,
            )

        panel = ConfigPanelView(
            cog=self,
            owner_id=interaction.user.id,
            guild_id=guild.id,
        )

        embed = await panel.build_embed(
            guild
        )

        await interaction.response.send_message(
            embed=embed,
            view=panel,
            ephemeral=True,
        )

    # ==================================================
    # /SETUP
    # ==================================================

    @app_commands.command(
        name="setup",
        description=(
            "Run initial server setup "
            "(roles, logs, tickets, relationships)"
        ),
    )
    @app_commands.describe(
        log_channel="Channel to send setup logs to",
        admin_role="Role to treat as server admin",
        mod_role="Role for moderators and ticket staff",
        member_role="Role for normal/verified members",
        ticket_category="Category where ticket channels will be created",
        marriage_channel="Channel for marriage/relationships posts",
        enforce_only_post=(
            "If true, restrict posting to the selected marriage channel"
        ),
    )
    @app_commands.default_permissions(
        administrator=True
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def setup_command(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None = None,
        admin_role: discord.Role | None = None,
        mod_role: discord.Role | None = None,
        member_role: discord.Role | None = None,
        ticket_category: discord.CategoryChannel | None = None,
        marriage_channel: discord.TextChannel | None = None,
        enforce_only_post: bool | None = None,
    ):
        await interaction.response.send_message(
            (
                "🔧 Setup started — running in background.\n"
                "When it finishes, the **Auto Roles panel** "
                "will appear below."
            ),
            ephemeral=True,
        )

        self.bot.loop.create_task(
            self._run_setup_background(
                interaction=interaction,
                log_channel=log_channel,
                admin_role=admin_role,
                mod_role=mod_role,
                member_role=member_role,
                ticket_category=ticket_category,
                marriage_channel=marriage_channel,
                enforce_only_post=enforce_only_post,
            )
        )

    async def _run_setup_background(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None,
        admin_role: discord.Role | None,
        mod_role: discord.Role | None,
        member_role: discord.Role | None,
        ticket_category: discord.CategoryChannel | None,
        marriage_channel: discord.TextChannel | None,
        enforce_only_post: bool | None,
    ):
        try:
            await asyncio.wait_for(
                self._do_setup_work(
                    interaction=interaction,
                    log_channel=log_channel,
                    admin_role=admin_role,
                    mod_role=mod_role,
                    member_role=member_role,
                    ticket_category=ticket_category,
                    marriage_channel=marriage_channel,
                    enforce_only_post=enforce_only_post,
                ),
                timeout=180.0,
            )

            guild = interaction.guild

            if guild is None:
                return await interaction.followup.send(
                    "✅ Setup completed successfully.",
                    ephemeral=True,
                )

            panel = AutoRolePanelView(
                cog=self,
                owner_id=interaction.user.id,
                guild_id=guild.id,
            )

            embed = await panel.build_embed(
                guild
            )

            await interaction.followup.send(
                "✅ **Setup completed successfully.**",
                embed=embed,
                view=panel,
                ephemeral=True,
            )

        except asyncio.TimeoutError:
            await interaction.followup.send(
                (
                    "⚠️ Setup timed out. "
                    "Check bot permissions and try again."
                ),
                ephemeral=True,
            )

        except Exception as e:
            traceback.print_exc()

            await interaction.followup.send(
                f"❌ Setup failed: {e}",
                ephemeral=True,
            )

    async def _do_setup_work(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None,
        admin_role: discord.Role | None,
        mod_role: discord.Role | None,
        member_role: discord.Role | None,
        ticket_category: discord.CategoryChannel | None,
        marriage_channel: discord.TextChannel | None,
        enforce_only_post: bool | None,
    ):
        async def log(
            msg: str,
        ):
            if log_channel:
                try:
                    await log_channel.send(
                        msg
                    )
                except Exception:
                    pass

        await log(
            "🔧 Setup: starting."
        )

        guild = interaction.guild

        if guild is None:
            await log(
                "⚠️ No guild context found; aborting setup."
            )
            return

        # --------------------------------------------------
        # LOAD EXISTING SETTINGS
        # --------------------------------------------------

        existing_settings = None

        try:
            db_obj = getattr(
                self.bot,
                "db",
                None,
            )

            if (
                db_obj
                and callable(
                    getattr(
                        db_obj,
                        "get_guild_settings",
                        None,
                    )
                )
            ):
                existing_settings = (
                    await db_obj.get_guild_settings(
                        guild.id
                    )
                )

        except Exception:
            traceback.print_exc()

        # --------------------------------------------------
        # ADMIN ROLE
        # --------------------------------------------------

        if admin_role is None:

            if existing_settings:
                saved_admin_id = (
                    existing_settings.get(
                        "admin_role"
                    )
                )

                if saved_admin_id:
                    admin_role = (
                        guild.get_role(
                            saved_admin_id
                        )
                    )

            if (
                admin_role is None
                and not existing_settings
            ):
                admin_role = discord.utils.get(
                    guild.roles,
                    name="Admin",
                )

                if admin_role is None:
                    try:
                        admin_role = (
                            await guild.create_role(
                                name="Admin",
                                reason=(
                                    "Setup: creating admin role"
                                ),
                            )
                        )

                        await log(
                            "✅ Created role: Admin"
                        )

                    except Exception:
                        await log(
                            (
                                "⚠️ Failed to create Admin role "
                                "(missing permissions)."
                            )
                        )

        if admin_role:
            await log(
                f"✅ Admin role: {admin_role.name}"
            )

        # --------------------------------------------------
        # MOD ROLE
        # --------------------------------------------------

        if mod_role is None:

            if existing_settings:
                saved_mod_id = (
                    existing_settings.get(
                        "mod_role"
                    )
                    or existing_settings.get(
                        "staff_role"
                    )
                )

                if saved_mod_id:
                    mod_role = (
                        guild.get_role(
                            saved_mod_id
                        )
                    )

            if (
                mod_role is None
                and not existing_settings
            ):
                mod_role = (
                    discord.utils.get(
                        guild.roles,
                        name="Mod",
                    )
                    or discord.utils.get(
                        guild.roles,
                        name="Moderator",
                    )
                    or discord.utils.get(
                        guild.roles,
                        name="Staff",
                    )
                )

        if mod_role:
            await log(
                f"✅ Mod role: {mod_role.name}"
            )

        # --------------------------------------------------
        # MEMBER ROLE
        # --------------------------------------------------

        if member_role is None:

            if existing_settings:
                saved_member_id = (
                    existing_settings.get(
                        "member_role"
                    )
                )

                if saved_member_id:
                    member_role = (
                        guild.get_role(
                            saved_member_id
                        )
                    )

            if (
                member_role is None
                and not existing_settings
            ):
                member_role = (
                    discord.utils.get(
                        guild.roles,
                        name="Member",
                    )
                    or discord.utils.get(
                        guild.roles,
                        name="Members",
                    )
                    or discord.utils.get(
                        guild.roles,
                        name="Verified",
                    )
                )

        if member_role:
            await log(
                f"✅ Member role: {member_role.name}"
            )

        # --------------------------------------------------
        # MARRIAGE / RELATIONSHIPS CHANNEL
        # --------------------------------------------------

        if marriage_channel is None:
            await log(
                (
                    "ℹ️ Marriage/relationships channel "
                    "left unchanged."
                )
            )

        else:
            await log(
                (
                    "✅ Marriage channel set to: "
                    f"#{marriage_channel.name}"
                )
            )

            if enforce_only_post is True:
                try:
                    everyone = (
                        guild.default_role
                    )

                    bot_member = (
                        guild.me
                        or guild.get_member(
                            self.bot.user.id
                        )
                    )

                    await marriage_channel.set_permissions(
                        everyone,
                        send_messages=False,
                        reason=(
                            "Setup: restrict marriage channel"
                        ),
                    )

                    if admin_role:
                        await marriage_channel.set_permissions(
                            admin_role,
                            send_messages=True,
                            reason=(
                                "Setup: allow admin role to post"
                            ),
                        )

                    if mod_role:
                        await marriage_channel.set_permissions(
                            mod_role,
                            send_messages=True,
                            reason=(
                                "Setup: allow mod role to post"
                            ),
                        )

                    if bot_member:
                        await marriage_channel.set_permissions(
                            bot_member,
                            send_messages=True,
                            reason=(
                                "Setup: allow bot to post"
                            ),
                        )

                    await log(
                        (
                            "🔒 Enforced posting restrictions on "
                            f"#{marriage_channel.name}."
                        )
                    )

                except Exception:
                    traceback.print_exc()

                    await log(
                        (
                            "⚠️ Failed to enforce posting restrictions on "
                            f"#{marriage_channel.name}. "
                            "Check bot permissions (Manage Channels)."
                        )
                    )

            elif enforce_only_post is False:
                await log(
                    (
                        "ℹ️ Marriage-channel posting restriction "
                        "saved as disabled."
                    )
                )

        # --------------------------------------------------
        # SAVE SETTINGS TO DATABASE
        # --------------------------------------------------

        try:
            db_obj = getattr(
                self.bot,
                "db",
                None,
            )

            if (
                db_obj
                and callable(
                    getattr(
                        db_obj,
                        "upsert_guild_settings",
                        None,
                    )
                )
            ):
                await db_obj.upsert_guild_settings(
                    guild_id=guild.id,
                    log_channel_id=(
                        log_channel.id
                        if log_channel
                        else None
                    ),
                    admin_role_id=(
                        admin_role.id
                        if admin_role
                        else None
                    ),
                    mod_role_id=(
                        mod_role.id
                        if mod_role
                        else None
                    ),
                    member_role_id=(
                        member_role.id
                        if member_role
                        else None
                    ),
                    ticket_category_id=(
                        ticket_category.id
                        if ticket_category
                        else None
                    ),
                    marriage_channel_id=(
                        marriage_channel.id
                        if marriage_channel
                        else None
                    ),
                    relationship_channel_id=(
                        marriage_channel.id
                        if marriage_channel
                        else None
                    ),
                    enforce_only_post=(
                        enforce_only_post
                    ),
                )

                await log(
                    "✅ Saved guild settings to database."
                )

            else:
                await log(
                    (
                        "ℹ️ Database upsert helper not available; "
                        "settings not persisted."
                    )
                )

        except Exception:
            traceback.print_exc()

            await log(
                "⚠️ Failed to save guild settings to database."
            )

        await log(
            "🔧 Setup finished (best-effort)."
        )


async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        SetupCog(bot)
    )
