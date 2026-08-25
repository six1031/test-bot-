import traceback
import discord

from discord.ext import commands
from discord import app_commands

from database.role_panels import (
    init_role_panel_tables,
    create_role_panel,
    set_role_panel_message,
    add_role_panel_item,
    get_role_panel_items,
    get_all_published_role_panels,
    delete_role_panel,
)


# ==================================================
# SETTINGS
# ==================================================

MAX_PANEL_ROLES = 25


# ==================================================
# HELPERS
# ==================================================

def parse_emoji(
    emoji_text: str | None,
):

    if not emoji_text:
        return None

    emoji_text = emoji_text.strip()

    if not emoji_text:
        return None

    try:

        return discord.PartialEmoji.from_str(
            emoji_text
        )

    except Exception:

        return None


def role_is_dangerous(
    role: discord.Role,
):

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


def can_bot_manage_role(
    guild: discord.Guild,
    role: discord.Role,
):

    bot_member = guild.me

    if bot_member is None:
        return False

    if not (
        bot_member
        .guild_permissions
        .manage_roles
    ):
        return False

    if role.is_default():
        return False

    if role.managed:
        return False

    if (
        role.position
        >= bot_member.top_role.position
    ):
        return False

    return True


# ==================================================
# ROLE TOGGLE BUTTON
# ==================================================

class RoleToggleButton(
    discord.ui.Button
):

    def __init__(
        self,
        panel_id: int,
        role_id: int,
        role_name: str | None = None,
        emoji_text: str | None = None,
    ):

        self.panel_id = panel_id
        self.role_id = role_id

        label = (
            role_name
            or f"Role {role_id}"
        )

        # Discord button labels max at 80 chars.
        label = label[:80]

        emoji = parse_emoji(
            emoji_text
        )

        try:

            super().__init__(
                label=label,
                style=(
                    discord.ButtonStyle.secondary
                ),
                emoji=emoji,
                custom_id=(
                    f"rolepanel:"
                    f"{panel_id}:"
                    f"{role_id}"
                ),
            )

        except Exception:

            # If an old/custom emoji stops existing,
            # the role button should still work.
            super().__init__(
                label=label,
                style=(
                    discord.ButtonStyle.secondary
                ),
                custom_id=(
                    f"rolepanel:"
                    f"{panel_id}:"
                    f"{role_id}"
                ),
            )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        guild = interaction.guild

        if guild is None:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ This role button "
                        "only works inside the server."
                    ),
                    ephemeral=True,
                )
            )

        member = interaction.user

        if not isinstance(
            member,
            discord.Member,
        ):

            return await (
                interaction.response
                .send_message(
                    "❌ Could not find your member account.",
                    ephemeral=True,
                )
            )

        role = guild.get_role(
            self.role_id
        )

        if role is None:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ That role no longer exists. "
                        "Please tell a staff member."
                    ),
                    ephemeral=True,
                )
            )

        if not can_bot_manage_role(
            guild,
            role,
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        f"❌ I can't manage the "
                        f"**{role.name}** role.\n"
                        "My bot role needs to be above it."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # REMOVE ROLE
        # --------------------------------------------------

        if role in member.roles:

            try:

                await member.remove_roles(
                    role,
                    reason=(
                        "Self role panel"
                    ),
                )

            except (
                discord.Forbidden,
                discord.HTTPException,
            ):

                return await (
                    interaction.response
                    .send_message(
                        (
                            f"❌ I couldn't remove "
                            f"**{role.name}**."
                        ),
                        ephemeral=True,
                    )
                )

            return await (
                interaction.response
                .send_message(
                    (
                        f"➖ Removed "
                        f"**{role.name}**."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # ADD ROLE
        # --------------------------------------------------

        try:

            await member.add_roles(
                role,
                reason=(
                    "Self role panel"
                ),
            )

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        f"❌ I couldn't give you "
                        f"**{role.name}**."
                    ),
                    ephemeral=True,
                )
            )

        await (
            interaction.response
            .send_message(
                (
                    f"✅ Added "
                    f"**{role.name}**."
                ),
                ephemeral=True,
            )
        )


# ==================================================
# PUBLISHED ROLE PANEL VIEW
# ==================================================

class RolePanelView(
    discord.ui.View
):

    def __init__(
        self,
        panel_id: int,
        items: list[dict],
        guild: discord.Guild | None = None,
    ):

        super().__init__(
            timeout=None
        )

        self.panel_id = panel_id

        for item in items:

            role_id = item[
                "role_id"
            ]

            role_name = None

            if guild:

                role = guild.get_role(
                    role_id
                )

                if role:

                    role_name = (
                        role.name
                    )

            button = RoleToggleButton(
                panel_id=panel_id,
                role_id=role_id,
                role_name=role_name,
                emoji_text=(
                    item.get(
                        "emoji"
                    )
                ),
            )

            self.add_item(
                button
            )


# ==================================================
# EMOJI MODAL
# ==================================================

class RoleEmojiModal(
    discord.ui.Modal
):

    def __init__(
        self,
        setup_view,
        role: discord.Role,
    ):

        super().__init__(
            title=(
                f"Emoji for {role.name}"[:45]
            )
        )

        self.setup_view = setup_view
        self.role = role

        self.emoji_input = (
            discord.ui.TextInput(
                label="Emoji",
                placeholder=(
                    "Example: 🌸  or  <:name:123456>"
                ),
                required=False,
                max_length=100,
            )
        )

        self.add_item(
            self.emoji_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        emoji = str(
            self.emoji_input.value
        ).strip()

        # --------------------------------------------------
        # ADD OR UPDATE ROLE
        # --------------------------------------------------

        already_exists = (
            self.role.id
            in self.setup_view.items
        )

        self.setup_view.items[
            self.role.id
        ] = {
            "role_id":
                self.role.id,

            "role_name":
                self.role.name,

            "emoji":
                emoji,
        }

        if not already_exists:

            self.setup_view.order.append(
                self.role.id
            )

        # --------------------------------------------------
        # REFRESH ORIGINAL WIZARD
        # --------------------------------------------------

        try:

            if self.setup_view.message:

                await (
                    self.setup_view.message
                    .edit(
                        content=(
                            self.setup_view
                            .summary_text()
                        ),
                        view=(
                            self.setup_view
                        ),
                    )
                )

        except discord.HTTPException:

            pass

        await (
            interaction.response
            .send_message(
                (
                    f"✅ Added "
                    f"**{self.role.name}** "
                    f"to the panel."
                ),
                ephemeral=True,
            )
        )


# ==================================================
# SETUP WIZARD
# ==================================================

class RolePanelSetupView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        guild_id: int,
        creator_id: int,
        channel_id: int,
        title: str,
        description: str,
    ):

        super().__init__(
            timeout=900
        )

        self.bot = bot
        self.guild_id = guild_id
        self.creator_id = creator_id
        self.channel_id = channel_id

        self.title = title
        self.description = description

        self.items = {}
        self.order = []

        self.message = None

        # --------------------------------------------------
        # ROLE PICKER
        # --------------------------------------------------

        self.role_select = (
            discord.ui.RoleSelect(
                placeholder=(
                    "Select a role to add..."
                ),
                min_values=1,
                max_values=1,
                row=0,
            )
        )

        self.role_select.callback = (
            self.role_selected
        )

        self.add_item(
            self.role_select
        )

    # ==================================================
    # SECURITY
    # ==================================================

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):

        if (
            interaction.user.id
            != self.creator_id
        ):

            await (
                interaction.response
                .send_message(
                    (
                        "❌ Only the admin "
                        "creating this panel "
                        "can use this setup."
                    ),
                    ephemeral=True,
                )
            )

            return False

        return True

    # ==================================================
    # SUMMARY
    # ==================================================

    def summary_text(
        self,
    ):

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
                    f"**Description:** "
                    f"{self.description}",
                ]
            )

        lines.extend(
            [
                "",
                "**Roles:**",
            ]
        )

        if not self.order:

            lines.append(
                "No roles added yet."
            )

        else:

            for number, role_id in enumerate(
                self.order,
                start=1,
            ):

                item = self.items[
                    role_id
                ]

                emoji = (
                    item["emoji"]
                    or "▫️"
                )

                lines.append(
                    (
                        f"{number}. "
                        f"{emoji} "
                        f"<@&{role_id}>"
                    )
                )

        lines.extend(
            [
                "",
                (
                    "Select a role above. "
                    "I'll then ask which emoji "
                    "you want on its button."
                ),
                "",
                (
                    f"**{len(self.order)}"
                    f"/{MAX_PANEL_ROLES} roles**"
                ),
            ]
        )

        return "\n".join(
            lines
        )

    # ==================================================
    # ROLE SELECTED
    # ==================================================

    async def role_selected(
        self,
        interaction: discord.Interaction,
    ):

        role = (
            self.role_select
            .values[0]
        )

        guild = interaction.guild

        if guild is None:
            return

        # --------------------------------------------------
        # BLOCK @EVERYONE
        # --------------------------------------------------

        if role.is_default():

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You can't add "
                        "@everyone to a self-role panel."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # BLOCK BOT / INTEGRATION ROLES
        # --------------------------------------------------

        if role.managed:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ That role is managed "
                        "by Discord or another integration."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # BLOCK STAFF / DANGEROUS ROLES
        # --------------------------------------------------

        if role_is_dangerous(
            role
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ That role has moderation "
                        "or management permissions, "
                        "so I won't make it self-assignable."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # BOT MUST BE ABLE TO MANAGE IT
        # --------------------------------------------------

        if not can_bot_manage_role(
            guild,
            role,
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        f"❌ I can't manage "
                        f"**{role.name}**.\n\n"
                        "Move my bot role above "
                        "that role first."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # MAX 25
        # --------------------------------------------------

        if (
            role.id
            not in self.items
            and len(
                self.order
            ) >= MAX_PANEL_ROLES
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ A Discord button panel "
                        "can contain a maximum "
                        "of 25 roles."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # ASK FOR EMOJI
        # --------------------------------------------------

        await (
            interaction.response
            .send_modal(
                RoleEmojiModal(
                    self,
                    role,
                )
            )
        )

    # ==================================================
    # REMOVE LAST ROLE
    # ==================================================

    @discord.ui.button(
        label="Remove Last",
        emoji="↩️",
        style=(
            discord.ButtonStyle.secondary
        ),
        row=1,
    )
    async def remove_last(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.order:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ There are no roles "
                        "to remove."
                    ),
                    ephemeral=True,
                )
            )

        role_id = (
            self.order.pop()
        )

        item = self.items.pop(
            role_id
        )

        await (
            interaction.response
            .edit_message(
                content=(
                    self.summary_text()
                ),
                view=self,
            )
        )

        await (
            interaction.followup
            .send(
                (
                    f"➖ Removed "
                    f"**{item['role_name']}** "
                    f"from the draft."
                ),
                ephemeral=True,
            )
        )

    # ==================================================
    # PUBLISH
    # ==================================================

    @discord.ui.button(
        label="Publish Panel",
        emoji="✅",
        style=(
            discord.ButtonStyle.success
        ),
        row=1,
    )
    async def publish(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.order:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Add at least one role "
                        "before publishing."
                    ),
                    ephemeral=True,
                )
            )

        await (
            interaction.response
            .defer(
                ephemeral=True
            )
        )

        guild = interaction.guild

        channel = guild.get_channel(
            self.channel_id
        )

        if not isinstance(
            channel,
            discord.TextChannel,
        ):

            return await (
                interaction.followup
                .send(
                    (
                        "❌ I couldn't find "
                        "the selected channel."
                    ),
                    ephemeral=True,
                )
            )

        panel_id = None

        try:

            # --------------------------------------------------
            # CREATE DATABASE PANEL
            # --------------------------------------------------

            panel_id = (
                await create_role_panel(
                    guild_id=guild.id,
                    title=self.title,
                    description=(
                        self.description
                        or None
                    ),
                    created_by=(
                        interaction.user.id
                    ),
                )
            )

            # --------------------------------------------------
            # SAVE ROLES
            # --------------------------------------------------

            position = 0

            for role_id in self.order:

                item = self.items[
                    role_id
                ]

                await add_role_panel_item(
                    panel_id=panel_id,
                    role_id=role_id,
                    emoji=(
                        item["emoji"]
                        or None
                    ),
                    position=position,
                )

                position += 1

            # --------------------------------------------------
            # GET SAVED ITEMS
            # --------------------------------------------------

            saved_items = (
                await get_role_panel_items(
                    panel_id
                )
            )

            # --------------------------------------------------
            # BUILD PUBLIC EMBED
            # --------------------------------------------------

            description_parts = []

            if self.description:

                description_parts.append(
                    self.description
                )

            description_parts.append(
                (
                    "Click a button below to "
                    "**add or remove** that role."
                )
            )

            description_parts.append(
                "\n**Available Roles**"
            )

            for role_id in self.order:

                item = self.items[
                    role_id
                ]

                emoji = (
                    item["emoji"]
                    or "▫️"
                )

                description_parts.append(
                    (
                        f"{emoji} "
                        f"<@&{role_id}>"
                    )
                )

            embed = discord.Embed(
                title=self.title,
                description=(
                    "\n".join(
                        description_parts
                    )
                ),
                colour=(
                    discord.Colour.blurple()
                ),
            )

            embed.set_footer(
                text=(
                    "Click again to remove a role."
                )
            )

            # --------------------------------------------------
            # BUILD PERSISTENT BUTTONS
            # --------------------------------------------------

            panel_view = (
                RolePanelView(
                    panel_id=panel_id,
                    items=saved_items,
                    guild=guild,
                )
            )

            # --------------------------------------------------
            # SEND PANEL
            # --------------------------------------------------

            message = (
                await channel.send(
                    embed=embed,
                    view=panel_view,
                )
            )

            # --------------------------------------------------
            # SAVE MESSAGE + CHANNEL
            # --------------------------------------------------

            await set_role_panel_message(
                panel_id=panel_id,
                channel_id=channel.id,
                message_id=message.id,
            )

            # --------------------------------------------------
            # REGISTER IMMEDIATELY
            # --------------------------------------------------

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

                    await delete_role_panel(
                        panel_id
                    )

                except Exception:

                    pass

            return await (
                interaction.followup
                .send(
                    (
                        "❌ Something went wrong "
                        "while publishing the panel.\n"
                        f"`{type(e).__name__}`"
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # FINISH WIZARD
        # --------------------------------------------------

        self.stop()

        try:

            await (
                interaction.message
                .edit(
                    content=(
                        "✅ **Role panel published!**\n\n"
                        f"Posted in {channel.mention}."
                    ),
                    view=None,
                )
            )

        except discord.HTTPException:

            pass

        await (
            interaction.followup
            .send(
                (
                    f"✅ Role panel published "
                    f"in {channel.mention}."
                ),
                ephemeral=True,
            )
        )

    # ==================================================
    # CANCEL
    # ==================================================

    @discord.ui.button(
        label="Cancel",
        emoji="✖️",
        style=(
            discord.ButtonStyle.danger
        ),
        row=1,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        self.stop()

        await (
            interaction.response
            .edit_message(
                content=(
                    "❌ Role panel setup cancelled."
                ),
                view=None,
            )
        )


# ==================================================
# PANEL INFO MODAL
# ==================================================

class RolePanelInfoModal(
    discord.ui.Modal
):

    def __init__(
        self,
        bot,
        guild_id: int,
        creator_id: int,
        channel_id: int,
    ):

        super().__init__(
            title="Create Role Panel"
        )

        self.bot = bot
        self.guild_id = guild_id
        self.creator_id = creator_id
        self.channel_id = channel_id

        self.panel_title = (
            discord.ui.TextInput(
                label="Panel title",
                placeholder=(
                    "Example: 🌸 Choose Your Roles"
                ),
                required=True,
                max_length=100,
            )
        )

        self.panel_description = (
            discord.ui.TextInput(
                label="Description",
                placeholder=(
                    "Example: Pick any roles that apply to you."
                ),
                required=False,
                style=(
                    discord.TextStyle.paragraph
                ),
                max_length=1000,
            )
        )

        self.add_item(
            self.panel_title
        )

        self.add_item(
            self.panel_description
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        title = str(
            self.panel_title.value
        ).strip()

        description = str(
            self.panel_description.value
        ).strip()

        view = (
            RolePanelSetupView(
                bot=self.bot,
                guild_id=self.guild_id,
                creator_id=self.creator_id,
                channel_id=self.channel_id,
                title=title,
                description=description,
            )
        )

        await (
            interaction.response
            .send_message(
                view.summary_text(),
                view=view,
                ephemeral=True,
            )
        )

        try:

            view.message = (
                await interaction
                .original_response()
            )

        except discord.HTTPException:

            view.message = None


# ==================================================
# ROLE PANEL COG
# ==================================================

class RolePanels(
    commands.Cog
):

    rolepanel = app_commands.Group(
        name="rolepanel",
        description=(
            "Create and manage self-role panels."
        ),
    )

    def __init__(
        self,
        bot,
    ):

        self.bot = bot

    # ==================================================
    # DATABASE + PERSISTENT VIEW RESTORE
    # ==================================================

    async def cog_load(
        self,
    ):

        # --------------------------------------------------
        # ENSURE DATABASE TABLES
        # --------------------------------------------------

        await init_role_panel_tables()

        print(
            "✅ Role panel database ready."
        )

        # --------------------------------------------------
        # RESTORE PUBLISHED BUTTONS
        # --------------------------------------------------

        try:

            panels = (
                await get_all_published_role_panels()
            )

        except Exception as e:

            print(
                (
                    "❌ Failed to load "
                    f"role panels: {e}"
                )
            )

            return

        restored = 0

        for panel in panels:

            try:

                panel_id = (
                    panel["id"]
                )

                message_id = (
                    panel["message_id"]
                )

                items = (
                    await get_role_panel_items(
                        panel_id
                    )
                )

                if not items:
                    continue

                view = (
                    RolePanelView(
                        panel_id=panel_id,
                        items=items,
                    )
                )

                self.bot.add_view(
                    view,
                    message_id=message_id,
                )

                restored += 1

            except Exception as e:

                print(
                    (
                        "⚠️ Could not restore "
                        f"role panel "
                        f"{panel.get('id')}: {e}"
                    )
                )

        print(
            (
                f"🎭 Restored {restored} "
                f"persistent role panel(s)."
            )
        )

    # ==================================================
    # /ROLEPANEL SETUP
    # ==================================================

    @rolepanel.command(
        name="setup",
        description=(
            "Create a self-assign role panel."
        ),
    )
    @app_commands.describe(
        channel=(
            "Where should the role panel be posted?"
        )
    )
    async def setup_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):

        # --------------------------------------------------
        # ADMIN ONLY
        # --------------------------------------------------

        if not (
            interaction.user
            .guild_permissions
            .administrator
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You need Administrator "
                        "permission to create role panels."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # BOT PERMISSIONS
        # --------------------------------------------------

        bot_member = (
            interaction.guild.me
        )

        if (
            bot_member is None
            or not bot_member
            .guild_permissions
            .manage_roles
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I need the "
                        "**Manage Roles** permission first."
                    ),
                    ephemeral=True,
                )
            )

        permissions = (
            channel.permissions_for(
                bot_member
            )
        )

        if not (
            permissions.send_messages
            and permissions.embed_links
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        f"❌ I need **Send Messages** "
                        f"and **Embed Links** in "
                        f"{channel.mention}."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # OPEN PANEL DETAILS FORM
        # --------------------------------------------------

        await (
            interaction.response
            .send_modal(
                RolePanelInfoModal(
                    bot=self.bot,
                    guild_id=(
                        interaction.guild.id
                    ),
                    creator_id=(
                        interaction.user.id
                    ),
                    channel_id=(
                        channel.id
                    ),
                )
            )
        )


# ==================================================
# LOAD COG
# ==================================================

async def setup(
    bot,
):

    await bot.add_cog(
        RolePanels(
            bot
        )
    )
