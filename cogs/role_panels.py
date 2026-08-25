import traceback
import discord

from discord.ext import commands
from discord import app_commands

from database.role_panels import (
    init_role_panel_tables,
    create_role_panel,
    set_role_panel_message,
    add_role_panel_item,
    remove_role_panel_item,
    get_role_panel,
    get_role_panel_items,
    get_guild_role_panels,
    get_all_published_role_panels,
    update_role_panel_text,
    delete_role_panel,
)


# ==================================================
# SETTINGS
# ==================================================

MAX_PANEL_ROLES = 25


# ==================================================
# HELPERS
# ==================================================

def parse_emoji(emoji_text: str | None):
    if not emoji_text:
        return None

    emoji_text = emoji_text.strip()

    if not emoji_text:
        return None

    try:
        return discord.PartialEmoji.from_str(emoji_text)
    except Exception:
        return None


def role_is_dangerous(role: discord.Role):
    permissions = role.permissions

    return any(
        [
            permissions.administrator,
            permissions.manage_guild,
            permissions.manage_roles,
            permissions.manage_channels,
            permissions.kick_members,
            permissions.ban_members,
            permissions.moderate_members,
        ]
    )


def can_bot_manage_role(guild: discord.Guild, role: discord.Role):
    bot_member = guild.me

    if bot_member is None:
        return False

    if not bot_member.guild_permissions.manage_roles:
        return False

    if role.is_default():
        return False

    if role.managed:
        return False

    if role.position >= bot_member.top_role.position:
        return False

    return True


def build_panel_embed(panel: dict, items: list[dict], guild: discord.Guild):
    description_parts = []

    description = panel.get("description")

    if description:
        description_parts.append(description)

    description_parts.append(
        "Click a button below to **add or remove** that role."
    )

    description_parts.append("\n**Available Roles**")

    if not items:
        description_parts.append("No roles are currently available.")

    for item in items:
        role_id = item["role_id"]
        role = guild.get_role(role_id)

        emoji = item.get("emoji") or "▫️"

        if role:
            description_parts.append(
                f"{emoji} {role.mention}"
            )
        else:
            description_parts.append(
                f"{emoji} Deleted role (`{role_id}`)"
            )

    embed = discord.Embed(
        title=panel.get("title") or "Choose Your Roles",
        description="\n".join(description_parts),
        colour=discord.Colour.blurple(),
    )

    embed.set_footer(
        text="Click the same button again to remove the role."
    )

    return embed


async def fetch_panel_message(
    bot,
    panel: dict,
):
    guild = bot.get_guild(panel["guild_id"])

    if guild is None:
        return None, None, None

    channel_id = panel.get("channel_id")
    message_id = panel.get("message_id")

    if not channel_id or not message_id:
        return guild, None, None

    channel = guild.get_channel(channel_id)

    if not isinstance(channel, discord.TextChannel):
        return guild, None, None

    try:
        message = await channel.fetch_message(message_id)
    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException,
    ):
        message = None

    return guild, channel, message


async def refresh_published_panel(
    bot,
    panel_id: int,
):
    panel = await get_role_panel(panel_id)

    if not panel:
        return False, "Panel not found."

    items = await get_role_panel_items(panel_id)

    guild, channel, message = await fetch_panel_message(
        bot,
        panel,
    )

    if guild is None:
        return False, "Server is not available."

    if channel is None:
        return False, "Panel channel could not be found."

    if message is None:
        return False, "Panel message could not be found."

    embed = build_panel_embed(
        panel,
        items,
        guild,
    )

    view = RolePanelView(
        panel_id=panel_id,
        items=items,
        guild=guild,
    )

    try:
        await message.edit(
            embed=embed,
            view=view,
        )
    except (
        discord.Forbidden,
        discord.HTTPException,
    ):
        return False, "I could not edit the panel message."

    return True, None


# ==================================================
# ROLE TOGGLE BUTTON
# ==================================================

class RoleToggleButton(discord.ui.Button):
    def __init__(
        self,
        panel_id: int,
        role_id: int,
        role_name: str | None = None,
        emoji_text: str | None = None,
    ):
        self.panel_id = panel_id
        self.role_id = role_id

        label = role_name or f"Role {role_id}"
        label = label[:80]

        emoji = parse_emoji(emoji_text)

        try:
            super().__init__(
                label=label,
                style=discord.ButtonStyle.secondary,
                emoji=emoji,
                custom_id=f"rolepanel:{panel_id}:{role_id}",
            )
        except Exception:
            super().__init__(
                label=label,
                style=discord.ButtonStyle.secondary,
                custom_id=f"rolepanel:{panel_id}:{role_id}",
            )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "❌ This role button only works inside the server.",
                ephemeral=True,
            )

        member = interaction.user

        if not isinstance(member, discord.Member):
            return await interaction.response.send_message(
                "❌ I could not find your member account.",
                ephemeral=True,
            )

        role = guild.get_role(self.role_id)

        if role is None:
            return await interaction.response.send_message(
                "❌ That role no longer exists. Please tell a staff member.",
                ephemeral=True,
            )

        if role_is_dangerous(role):
            return await interaction.response.send_message(
                "❌ That role can no longer be self-assigned because it has moderation permissions.",
                ephemeral=True,
            )

        if not can_bot_manage_role(guild, role):
            return await interaction.response.send_message(
                (
                    f"❌ I can't manage **{role.name}**.\n"
                    "My bot role needs to be above it and I need **Manage Roles**."
                ),
                ephemeral=True,
            )

        if role in member.roles:
            try:
                await member.remove_roles(
                    role,
                    reason="Self role panel",
                )
            except (
                discord.Forbidden,
                discord.HTTPException,
            ):
                return await interaction.response.send_message(
                    f"❌ I couldn't remove **{role.name}**.",
                    ephemeral=True,
                )

            return await interaction.response.send_message(
                f"➖ Removed **{role.name}**.",
                ephemeral=True,
            )

        try:
            await member.add_roles(
                role,
                reason="Self role panel",
            )
        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            return await interaction.response.send_message(
                f"❌ I couldn't give you **{role.name}**.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            f"✅ Added **{role.name}**.",
            ephemeral=True,
        )


# ==================================================
# PUBLISHED PANEL VIEW
# ==================================================

class RolePanelView(discord.ui.View):
    def __init__(
        self,
        panel_id: int,
        items: list[dict],
        guild: discord.Guild | None = None,
    ):
        super().__init__(timeout=None)

        self.panel_id = panel_id

        for item in items[:MAX_PANEL_ROLES]:
            role_id = item["role_id"]
            role_name = None

            if guild:
                role = guild.get_role(role_id)

                if role:
                    role_name = role.name

            self.add_item(
                RoleToggleButton(
                    panel_id=panel_id,
                    role_id=role_id,
                    role_name=role_name,
                    emoji_text=item.get("emoji"),
                )
            )


# ==================================================
# SETUP - EMOJI MODAL
# ==================================================

class SetupRoleEmojiModal(discord.ui.Modal):
    def __init__(
        self,
        setup_view,
        role: discord.Role,
    ):
        super().__init__(
            title=f"Emoji for {role.name}"[:45]
        )

        self.setup_view = setup_view
        self.role = role

        self.emoji_input = discord.ui.TextInput(
            label="Emoji",
            placeholder="Example: 🌸 or <:name:123456>",
            required=False,
            max_length=100,
        )

        self.add_item(self.emoji_input)

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        emoji = str(self.emoji_input.value).strip()

        already_exists = self.role.id in self.setup_view.items

        self.setup_view.items[self.role.id] = {
            "role_id": self.role.id,
            "role_name": self.role.name,
            "emoji": emoji,
        }

        if not already_exists:
            self.setup_view.order.append(self.role.id)

        try:
            if self.setup_view.message:
                await self.setup_view.message.edit(
                    content=self.setup_view.summary_text(),
                    view=self.setup_view,
                )
        except discord.HTTPException:
            pass

        await interaction.response.send_message(
            f"✅ Added **{self.role.name}** to the draft panel.",
            ephemeral=True,
        )


# ==================================================
# SETUP WIZARD
# ==================================================

class RolePanelSetupView(discord.ui.View):
    def __init__(
        self,
        bot,
        guild_id: int,
        creator_id: int,
        channel_id: int,
        title: str,
        description: str,
    ):
        super().__init__(timeout=900)

        self.bot = bot
        self.guild_id = guild_id
        self.creator_id = creator_id
        self.channel_id = channel_id
        self.title = title
        self.description = description

        self.items = {}
        self.order = []
        self.message = None

        self.role_select = discord.ui.RoleSelect(
            placeholder="Select a role to add...",
            min_values=1,
            max_values=1,
            row=0,
        )

        self.role_select.callback = self.role_selected
        self.add_item(self.role_select)

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message(
                "❌ Only the admin creating this panel can use this setup.",
                ephemeral=True,
            )
            return False

        return True

    def summary_text(self):
        lines = [
            "🎭 **ROLE PANEL SETUP**",
            "",
            f"**Channel:** <#{self.channel_id}>",
            f"**Title:** {self.title}",
        ]

        if self.description:
            lines.extend(
                [
                    "",
                    f"**Description:** {self.description}",
                ]
            )

        lines.extend(
            [
                "",
                "**Roles:**",
            ]
        )

        if not self.order:
            lines.append("No roles added yet.")
        else:
            for number, role_id in enumerate(
                self.order,
                start=1,
            ):
                item = self.items[role_id]
                emoji = item["emoji"] or "▫️"

                lines.append(
                    f"{number}. {emoji} <@&{role_id}>"
                )

        lines.extend(
            [
                "",
                "Select a role above. I'll then ask which emoji you want on its button.",
                "",
                f"**{len(self.order)}/{MAX_PANEL_ROLES} roles**",
            ]
        )

        return "\n".join(lines)

    async def role_selected(
        self,
        interaction: discord.Interaction,
    ):
        role = self.role_select.values[0]
        guild = interaction.guild

        if guild is None:
            return

        if role.is_default():
            return await interaction.response.send_message(
                "❌ You can't add @everyone to a self-role panel.",
                ephemeral=True,
            )

        if role.managed:
            return await interaction.response.send_message(
                "❌ That role is managed by Discord or another integration.",
                ephemeral=True,
            )

        if role_is_dangerous(role):
            return await interaction.response.send_message(
                "❌ That role has moderation or management permissions, so it cannot be self-assigned.",
                ephemeral=True,
            )

        if not can_bot_manage_role(guild, role):
            return await interaction.response.send_message(
                (
                    f"❌ I can't manage **{role.name}**.\n\n"
                    "Move my bot role above that role first."
                ),
                ephemeral=True,
            )

        if (
            role.id not in self.items
            and len(self.order) >= MAX_PANEL_ROLES
        ):
            return await interaction.response.send_message(
                "❌ A Discord button panel can contain a maximum of 25 roles.",
                ephemeral=True,
            )

        await interaction.response.send_modal(
            SetupRoleEmojiModal(
                self,
                role,
            )
        )

    @discord.ui.button(
        label="Remove Last",
        emoji="↩️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def remove_last(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not self.order:
            return await interaction.response.send_message(
                "❌ There are no roles to remove.",
                ephemeral=True,
            )

        role_id = self.order.pop()
        item = self.items.pop(role_id)

        await interaction.response.edit_message(
            content=self.summary_text(),
            view=self,
        )

        await interaction.followup.send(
            f"➖ Removed **{item['role_name']}** from the draft.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Publish Panel",
        emoji="✅",
        style=discord.ButtonStyle.success,
        row=1,
    )
    async def publish(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not self.order:
            return await interaction.response.send_message(
                "❌ Add at least one role before publishing.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        channel = guild.get_channel(self.channel_id)

        if not isinstance(channel, discord.TextChannel):
            return await interaction.followup.send(
                "❌ I couldn't find the selected channel.",
                ephemeral=True,
            )

        panel_id = None

        try:
            panel_id = await create_role_panel(
                guild_id=guild.id,
                title=self.title,
                description=self.description or None,
                created_by=interaction.user.id,
            )

            for position, role_id in enumerate(self.order):
                item = self.items[role_id]

                await add_role_panel_item(
                    panel_id=panel_id,
                    role_id=role_id,
                    emoji=item["emoji"] or None,
                    position=position,
                )

            panel = await get_role_panel(panel_id)
            saved_items = await get_role_panel_items(panel_id)

            panel_view = RolePanelView(
                panel_id=panel_id,
                items=saved_items,
                guild=guild,
            )

            message = await channel.send(
                embed=build_panel_embed(
                    panel,
                    saved_items,
                    guild,
                ),
                view=panel_view,
            )

            await set_role_panel_message(
                panel_id=panel_id,
                channel_id=channel.id,
                message_id=message.id,
            )

            self.bot.add_view(
                RolePanelView(
                    panel_id=panel_id,
                    items=saved_items,
                    guild=guild,
                ),
                message_id=message.id,
            )

        except Exception as e:
            traceback.print_exc()

            if panel_id is not None:
                try:
                    await delete_role_panel(panel_id)
                except Exception:
                    pass

            return await interaction.followup.send(
                (
                    "❌ Something went wrong while publishing the panel.\n"
                    f"`{type(e).__name__}`"
                ),
                ephemeral=True,
            )

        self.stop()

        try:
            await interaction.message.edit(
                content=(
                    "✅ **Role panel published!**\n\n"
                    f"**Panel ID:** `{panel_id}`\n"
                    f"Posted in {channel.mention}."
                ),
                view=None,
            )
        except discord.HTTPException:
            pass

        await interaction.followup.send(
            (
                f"✅ Role panel `{panel_id}` published in "
                f"{channel.mention}."
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Cancel",
        emoji="✖️",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.stop()

        await interaction.response.edit_message(
            content="❌ Role panel setup cancelled.",
            view=None,
        )


# ==================================================
# SETUP - PANEL INFO MODAL
# ==================================================

class RolePanelInfoModal(discord.ui.Modal):
    def __init__(
        self,
        bot,
        guild_id: int,
        creator_id: int,
        channel_id: int,
    ):
        super().__init__(title="Create Role Panel")

        self.bot = bot
        self.guild_id = guild_id
        self.creator_id = creator_id
        self.channel_id = channel_id

        self.panel_title = discord.ui.TextInput(
            label="Panel title",
            placeholder="Example: 🌸 Choose Your Roles",
            required=True,
            max_length=100,
        )

        self.panel_description = discord.ui.TextInput(
            label="Description",
            placeholder="Example: Pick any roles that apply to you.",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1000,
        )

        self.add_item(self.panel_title)
        self.add_item(self.panel_description)

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        title = str(self.panel_title.value).strip()
        description = str(self.panel_description.value).strip()

        view = RolePanelSetupView(
            bot=self.bot,
            guild_id=self.guild_id,
            creator_id=self.creator_id,
            channel_id=self.channel_id,
            title=title,
            description=description,
        )

        await interaction.response.send_message(
            view.summary_text(),
            view=view,
            ephemeral=True,
        )

        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            view.message = None


# ==================================================
# EDIT - TEXT MODAL
# ==================================================

class EditPanelTextModal(discord.ui.Modal):
    def __init__(
        self,
        edit_view,
    ):
        super().__init__(title="Edit Role Panel")

        self.edit_view = edit_view
        panel = edit_view.panel

        self.panel_title = discord.ui.TextInput(
            label="Panel title",
            required=True,
            max_length=100,
            default=panel.get("title") or "",
        )

        self.panel_description = discord.ui.TextInput(
            label="Description",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1000,
            default=panel.get("description") or "",
        )

        self.add_item(self.panel_title)
        self.add_item(self.panel_description)

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        title = str(self.panel_title.value).strip()
        description = str(self.panel_description.value).strip()

        try:
            await update_role_panel_text(
                self.edit_view.panel_id,
                title,
                description or None,
            )

            self.edit_view.panel["title"] = title
            self.edit_view.panel["description"] = description or None

            ok, error = await refresh_published_panel(
                self.edit_view.bot,
                self.edit_view.panel_id,
            )

            if self.edit_view.message:
                await self.edit_view.message.edit(
                    content=self.edit_view.summary_text(),
                    view=self.edit_view,
                )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't update that panel.",
                ephemeral=True,
            )

        text = "✅ Panel title/description updated."

        if not ok:
            text += f"\n⚠️ The saved panel was updated, but the Discord message could not be refreshed: {error}"

        await interaction.response.send_message(
            text,
            ephemeral=True,
        )


# ==================================================
# EDIT - EMOJI MODAL
# ==================================================

class EditRoleEmojiModal(discord.ui.Modal):
    def __init__(
        self,
        edit_view,
        role: discord.Role,
    ):
        super().__init__(
            title=f"Role: {role.name}"[:45]
        )

        self.edit_view = edit_view
        self.role = role

        old_emoji = ""

        old_item = edit_view.items_by_role.get(role.id)

        if old_item:
            old_emoji = old_item.get("emoji") or ""

        self.emoji_input = discord.ui.TextInput(
            label="Button emoji",
            placeholder="Example: 🌸 or <:name:123456>",
            required=False,
            max_length=100,
            default=old_emoji,
        )

        self.add_item(self.emoji_input)

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        emoji = str(self.emoji_input.value).strip()

        existing = self.edit_view.items_by_role.get(self.role.id)

        if existing:
            position = existing.get("position", 0)
        else:
            if len(self.edit_view.items) >= MAX_PANEL_ROLES:
                return await interaction.response.send_message(
                    "❌ This panel already has 25 roles.",
                    ephemeral=True,
                )

            position = 0

            if self.edit_view.items:
                position = max(
                    item.get("position", 0)
                    for item in self.edit_view.items
                ) + 1

        try:
            await add_role_panel_item(
                panel_id=self.edit_view.panel_id,
                role_id=self.role.id,
                emoji=emoji or None,
                position=position,
            )

            await self.edit_view.reload_items()

            ok, error = await refresh_published_panel(
                self.edit_view.bot,
                self.edit_view.panel_id,
            )

            if self.edit_view.message:
                await self.edit_view.message.edit(
                    content=self.edit_view.summary_text(),
                    view=self.edit_view,
                )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't add/update that role.",
                ephemeral=True,
            )

        text = f"✅ **{self.role.name}** added/updated."

        if not ok:
            text += f"\n⚠️ Database saved, but the panel message could not refresh: {error}"

        await interaction.response.send_message(
            text,
            ephemeral=True,
        )


# ==================================================
# EDIT VIEW
# ==================================================

class RolePanelEditView(discord.ui.View):
    def __init__(
        self,
        bot,
        creator_id: int,
        panel: dict,
        items: list[dict],
    ):
        super().__init__(timeout=900)

        self.bot = bot
        self.creator_id = creator_id
        self.panel = panel
        self.panel_id = panel["id"]
        self.items = items
        self.items_by_role = {
            item["role_id"]: item
            for item in items
        }

        self.selected_role_id = None
        self.message = None

        self.role_select = discord.ui.RoleSelect(
            placeholder="Select a role to add, edit or remove...",
            min_values=1,
            max_values=1,
            row=0,
        )

        self.role_select.callback = self.role_selected
        self.add_item(self.role_select)

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message(
                "❌ Only the admin editing this panel can use these controls.",
                ephemeral=True,
            )
            return False

        return True

    async def reload_items(self):
        self.items = await get_role_panel_items(
            self.panel_id
        )

        self.items_by_role = {
            item["role_id"]: item
            for item in self.items
        }

    def summary_text(self):
        channel_id = self.panel.get("channel_id")
        message_id = self.panel.get("message_id")

        lines = [
            f"🎭 **EDIT ROLE PANEL `{self.panel_id}`**",
            "",
            f"**Title:** {self.panel.get('title')}",
            f"**Channel:** <#{channel_id}>" if channel_id else "**Channel:** Not published",
            f"**Message ID:** `{message_id}`" if message_id else "**Message ID:** Not published",
            "",
            "**Current Roles:**",
        ]

        if not self.items:
            lines.append("No roles are currently on this panel.")
        else:
            guild = self.bot.get_guild(self.panel["guild_id"])

            for number, item in enumerate(
                self.items,
                start=1,
            ):
                role_id = item["role_id"]
                emoji = item.get("emoji") or "▫️"

                role_name = None

                if guild:
                    role = guild.get_role(role_id)
                    if role:
                        role_name = role.name

                if role_name:
                    lines.append(
                        f"{number}. {emoji} **{role_name}**"
                    )
                else:
                    lines.append(
                        f"{number}. {emoji} Deleted role (`{role_id}`)"
                    )

        lines.extend(
            [
                "",
                f"**{len(self.items)}/{MAX_PANEL_ROLES} roles**",
                "",
                "Select a role above, then use **Add / Change Emoji** or **Remove Role**.",
            ]
        )

        if self.selected_role_id:
            lines.append(
                f"\n**Selected:** <@&{self.selected_role_id}>"
            )

        return "\n".join(lines)

    async def role_selected(
        self,
        interaction: discord.Interaction,
    ):
        role = self.role_select.values[0]
        self.selected_role_id = role.id

        await interaction.response.edit_message(
            content=self.summary_text(),
            view=self,
        )

    @discord.ui.button(
        label="Add / Change Emoji",
        emoji="✏️",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def add_or_edit_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not self.selected_role_id:
            return await interaction.response.send_message(
                "❌ Select a role first.",
                ephemeral=True,
            )

        guild = interaction.guild
        role = guild.get_role(self.selected_role_id)

        if role is None:
            return await interaction.response.send_message(
                "❌ That role no longer exists.",
                ephemeral=True,
            )

        if role.is_default():
            return await interaction.response.send_message(
                "❌ @everyone cannot be self-assigned.",
                ephemeral=True,
            )

        if role.managed:
            return await interaction.response.send_message(
                "❌ That role is managed by Discord or another integration.",
                ephemeral=True,
            )

        if role_is_dangerous(role):
            return await interaction.response.send_message(
                "❌ That role has moderation or management permissions.",
                ephemeral=True,
            )

        if not can_bot_manage_role(guild, role):
            return await interaction.response.send_message(
                (
                    f"❌ I can't manage **{role.name}**.\n"
                    "Move my bot role above it first."
                ),
                ephemeral=True,
            )

        if (
            role.id not in self.items_by_role
            and len(self.items) >= MAX_PANEL_ROLES
        ):
            return await interaction.response.send_message(
                "❌ This panel already has 25 roles.",
                ephemeral=True,
            )

        await interaction.response.send_modal(
            EditRoleEmojiModal(
                self,
                role,
            )
        )

    @discord.ui.button(
        label="Remove Role",
        emoji="➖",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def remove_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not self.selected_role_id:
            return await interaction.response.send_message(
                "❌ Select a role first.",
                ephemeral=True,
            )

        item = self.items_by_role.get(
            self.selected_role_id
        )

        if not item:
            return await interaction.response.send_message(
                "❌ That role is not on this panel.",
                ephemeral=True,
            )

        try:
            await remove_role_panel_item(
                self.panel_id,
                self.selected_role_id,
            )

            await self.reload_items()

            ok, error = await refresh_published_panel(
                self.bot,
                self.panel_id,
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't remove that role from the panel.",
                ephemeral=True,
            )

        self.selected_role_id = None

        await interaction.response.edit_message(
            content=self.summary_text(),
            view=self,
        )

        text = "➖ Role removed from the panel."

        if not ok:
            text += f"\n⚠️ Database saved, but the panel message could not refresh: {error}"

        await interaction.followup.send(
            text,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Edit Text",
        emoji="📝",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def edit_text(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(
            EditPanelTextModal(self)
        )

    @discord.ui.button(
        label="Refresh Panel",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        row=2,
    )
    async def refresh_panel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            await self.reload_items()

            ok, error = await refresh_published_panel(
                self.bot,
                self.panel_id,
            )

        except Exception:
            traceback.print_exc()

            return await interaction.followup.send(
                "❌ I couldn't refresh the panel.",
                ephemeral=True,
            )

        if self.message:
            try:
                await self.message.edit(
                    content=self.summary_text(),
                    view=self,
                )
            except discord.HTTPException:
                pass

        if ok:
            await interaction.followup.send(
                "✅ Role panel refreshed.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"⚠️ {error}",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Done",
        emoji="✅",
        style=discord.ButtonStyle.success,
        row=2,
    )
    async def done(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.stop()

        await interaction.response.edit_message(
            content=(
                f"✅ Finished editing role panel `{self.panel_id}`."
            ),
            view=None,
        )


# ==================================================
# ROLE PANEL COG
# ==================================================

class RolePanels(commands.Cog):
    rolepanel = app_commands.Group(
        name="rolepanel",
        description="Create and manage self-role panels.",
    )

    def __init__(self, bot):
        self.bot = bot

    # ==================================================
    # DATABASE + PERSISTENT VIEW RESTORE
    # ==================================================

    async def cog_load(self):
        await init_role_panel_tables()

        print("✅ Role panel database ready.")

        try:
            panels = await get_all_published_role_panels()
        except Exception as e:
            print(f"❌ Failed to load role panels: {e}")
            return

        restored = 0

        for panel in panels:
            try:
                panel_id = panel["id"]
                message_id = panel["message_id"]

                items = await get_role_panel_items(
                    panel_id
                )

                if not items:
                    continue

                view = RolePanelView(
                    panel_id=panel_id,
                    items=items,
                )

                self.bot.add_view(
                    view,
                    message_id=message_id,
                )

                restored += 1

            except Exception as e:
                print(
                    f"⚠️ Could not restore role panel {panel.get('id')}: {e}"
                )

        print(
            f"🎭 Restored {restored} persistent role panel(s)."
        )

    # ==================================================
    # /ROLEPANEL SETUP
    # ==================================================

    @rolepanel.command(
        name="setup",
        description="Create a self-assign role panel.",
    )
    @app_commands.describe(
        channel="Where should the role panel be posted?"
    )
    async def setup_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ You need Administrator permission to create role panels.",
                ephemeral=True,
            )

        bot_member = interaction.guild.me

        if (
            bot_member is None
            or not bot_member.guild_permissions.manage_roles
        ):
            return await interaction.response.send_message(
                "❌ I need the **Manage Roles** permission first.",
                ephemeral=True,
            )

        permissions = channel.permissions_for(bot_member)

        if not (
            permissions.send_messages
            and permissions.embed_links
        ):
            return await interaction.response.send_message(
                (
                    f"❌ I need **Send Messages** and **Embed Links** "
                    f"in {channel.mention}."
                ),
                ephemeral=True,
            )

        await interaction.response.send_modal(
            RolePanelInfoModal(
                bot=self.bot,
                guild_id=interaction.guild.id,
                creator_id=interaction.user.id,
                channel_id=channel.id,
            )
        )

    # ==================================================
    # /ROLEPANEL EDIT
    # ==================================================

    @rolepanel.command(
        name="edit",
        description="Edit an existing saved role panel.",
    )
    @app_commands.describe(
        panel_id="The panel ID shown by /rolepanel list"
    )
    async def edit_panel(
        self,
        interaction: discord.Interaction,
        panel_id: int,
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ You need Administrator permission to edit role panels.",
                ephemeral=True,
            )

        try:
            panel = await get_role_panel(panel_id)
        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't load that role panel.",
                ephemeral=True,
            )

        if not panel or panel["guild_id"] != interaction.guild.id:
            return await interaction.response.send_message(
                "❌ I couldn't find that role panel in this server.",
                ephemeral=True,
            )

        items = await get_role_panel_items(panel_id)

        view = RolePanelEditView(
            bot=self.bot,
            creator_id=interaction.user.id,
            panel=panel,
            items=items,
        )

        await interaction.response.send_message(
            view.summary_text(),
            view=view,
            ephemeral=True,
        )

        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            view.message = None

    # ==================================================
    # /ROLEPANEL LIST
    # ==================================================

    @rolepanel.command(
        name="list",
        description="List saved role panels in this server.",
    )
    async def list_panels(
        self,
        interaction: discord.Interaction,
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ You need Administrator permission to list role panels.",
                ephemeral=True,
            )

        try:
            panels = await get_guild_role_panels(
                interaction.guild.id
            )
        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't load the role panels.",
                ephemeral=True,
            )

        if not panels:
            return await interaction.response.send_message(
                "🎭 No role panels have been saved yet.",
                ephemeral=True,
            )

        lines = [
            "🎭 **Saved Role Panels**",
            "",
        ]

        for panel in panels:
            panel_id = panel["id"]
            title = panel.get("title") or "Untitled"
            channel_id = panel.get("channel_id")
            message_id = panel.get("message_id")

            if channel_id and message_id:
                link = (
                    f"https://discord.com/channels/"
                    f"{interaction.guild.id}/"
                    f"{channel_id}/"
                    f"{message_id}"
                )

                lines.append(
                    f"`{panel_id}` — **{title}** — <#{channel_id}> — [Open Panel]({link})"
                )
            else:
                lines.append(
                    f"`{panel_id}` — **{title}** — Not published"
                )

        await interaction.response.send_message(
            "\n".join(lines),
            ephemeral=True,
        )

    # ==================================================
    # /ROLEPANEL DELETE
    # ==================================================

    @rolepanel.command(
        name="delete",
        description="Delete a saved role panel.",
    )
    @app_commands.describe(
        panel_id="The panel ID shown by /rolepanel list",
        delete_message="Also delete the Discord panel message",
    )
    async def delete_panel_command(
        self,
        interaction: discord.Interaction,
        panel_id: int,
        delete_message: bool = True,
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ You need Administrator permission to delete role panels.",
                ephemeral=True,
            )

        try:
            panel = await get_role_panel(panel_id)
        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't load that role panel.",
                ephemeral=True,
            )

        if not panel or panel["guild_id"] != interaction.guild.id:
            return await interaction.response.send_message(
                "❌ I couldn't find that role panel in this server.",
                ephemeral=True,
            )

        message_deleted = False

        if delete_message:
            guild, channel, message = await fetch_panel_message(
                self.bot,
                panel,
            )

            if message:
                try:
                    await message.delete()
                    message_deleted = True
                except (
                    discord.Forbidden,
                    discord.HTTPException,
                ):
                    message_deleted = False

        try:
            await delete_role_panel(panel_id)
        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't delete that panel from the database.",
                ephemeral=True,
            )

        result = f"✅ Role panel `{panel_id}` deleted from the database."

        if delete_message:
            if message_deleted:
                result += "\n🗑️ The Discord panel message was deleted too."
            else:
                result += "\n⚠️ I couldn't delete the Discord message, or it was already gone."

        await interaction.response.send_message(
            result,
            ephemeral=True,
        )


# ==================================================
# LOAD COG
# ==================================================

async def setup(bot):
    await bot.add_cog(
        RolePanels(bot)
    )
