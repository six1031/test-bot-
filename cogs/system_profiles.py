import traceback
import discord

from discord.ext import commands
from discord import app_commands

from database.system_profiles import (
    init_system_profile_tables,
    set_system_profile_channel,
    get_system_profile_settings,
    save_system_profile,
    get_system_profile,
    set_system_profile_message,
    get_alter_profiles,
)


# ==================================================
# HELPERS
# ==================================================

def clean_value(value):
    if value is None:
        return "Not set"

    value = str(value).strip()

    return value or "Not set"


def safe_text(value, limit=1000):
    value = clean_value(value)

    if len(value) > limit:
        return value[:limit - 3] + "..."

    return value


# ==================================================
# BUILD SYSTEM PROFILE
# ==================================================

def build_system_profile_embed(
    member: discord.Member,
    profile: dict,
    alter_count: int = 0,
):

    system_name = clean_value(
        profile.get("system_name")
    )

    embed = discord.Embed(
        title=(
            f"🌸 {system_name}"
        ),
        description=(
            "✨ **SYSTEM PROFILE** ✨"
        ),
        colour=discord.Colour.blurple(),
    )

    embed.set_author(
        name=(
            f"{member.display_name}'s System"
        ),
        icon_url=(
            member.display_avatar.url
        ),
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.add_field(
        name="🌷 Collective Name",
        value=safe_text(
            profile.get("collective_name")
        ),
        inline=True,
    )

    embed.add_field(
        name="💗 Collective Pronouns",
        value=safe_text(
            profile.get("collective_pronouns")
        ),
        inline=True,
    )

    embed.add_field(
        name="👥 Approx. System Size",
        value=safe_text(
            profile.get("system_size")
        ),
        inline=True,
    )

    embed.add_field(
        name="🌙 System Label / Type",
        value=safe_text(
            profile.get("system_type")
        ),
        inline=False,
    )

    embed.add_field(
        name="🌸 Frequent Fronters",
        value=safe_text(
            profile.get("frequent_fronters")
        ),
        inline=False,
    )

    embed.add_field(
        name="🎨 Shared Interests",
        value=safe_text(
            profile.get("shared_interests")
        ),
        inline=False,
    )

    embed.add_field(
        name="💬 Communication Preferences",
        value=safe_text(
            profile.get(
                "communication_preferences"
            )
        ),
        inline=False,
    )

    embed.add_field(
        name="🛡️ Boundaries",
        value=safe_text(
            profile.get("boundaries")
        ),
        inline=False,
    )

    embed.add_field(
        name="💌 DM Status",
        value=safe_text(
            profile.get("dm_status")
        ),
        inline=True,
    )

    embed.add_field(
        name="🌼 Alter Profiles",
        value=(
            f"**{alter_count}** saved"
        ),
        inline=True,
    )

    embed.add_field(
        name="✨ Extra",
        value=safe_text(
            profile.get("extra")
        ),
        inline=False,
    )

    embed.set_footer(
        text=(
            "Use the alter buttons below "
            "to browse individual profiles."
        )
    )

    return embed


# ==================================================
# STEP 1
# BASIC SYSTEM INFORMATION
# ==================================================

class SystemBasicModal(
    discord.ui.Modal
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        existing: dict | None = None,
    ):

        super().__init__(
            title="System Profile"
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.existing = existing or {}

        self.system_name = discord.ui.TextInput(
            label="System Name",
            placeholder=(
                "What is your system called?"
            ),
            required=True,
            max_length=100,
            default=(
                self.existing.get(
                    "system_name"
                )
                or ""
            ),
        )

        self.collective_name = discord.ui.TextInput(
            label="Collective Name / Nickname",
            placeholder=(
                "Optional"
            ),
            required=False,
            max_length=100,
            default=(
                self.existing.get(
                    "collective_name"
                )
                or ""
            ),
        )

        self.collective_pronouns = discord.ui.TextInput(
            label="Collective Pronouns",
            placeholder=(
                "Example: they/them"
            ),
            required=False,
            max_length=100,
            default=(
                self.existing.get(
                    "collective_pronouns"
                )
                or ""
            ),
        )

        self.system_size = discord.ui.TextInput(
            label="Approx. System Size",
            placeholder=(
                "Optional — example: 5, 10+, unknown"
            ),
            required=False,
            max_length=50,
            default=(
                self.existing.get(
                    "system_size"
                )
                or ""
            ),
        )

        self.system_type = discord.ui.TextInput(
            label="System Label / Type",
            placeholder=(
                "Optional — use whatever terminology you prefer"
            ),
            required=False,
            max_length=150,
            default=(
                self.existing.get(
                    "system_type"
                )
                or ""
            ),
        )

        self.add_item(
            self.system_name
        )

        self.add_item(
            self.collective_name
        )

        self.add_item(
            self.collective_pronouns
        )

        self.add_item(
            self.system_size
        )

        self.add_item(
            self.system_type
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        data = dict(
            self.existing
        )

        data.update(
            {
                "system_name":
                    str(
                        self.system_name.value
                    ).strip(),

                "collective_name":
                    str(
                        self.collective_name.value
                    ).strip(),

                "collective_pronouns":
                    str(
                        self.collective_pronouns.value
                    ).strip(),

                "system_size":
                    str(
                        self.system_size.value
                    ).strip(),

                "system_type":
                    str(
                        self.system_type.value
                    ).strip(),
            }
        )

        view = SystemDMStatusView(
            bot=self.bot,
            guild_id=self.guild_id,
            user_id=self.user_id,
            data=data,
        )

        await interaction.response.send_message(
            view.status_text(),
            view=view,
            ephemeral=True,
        )


# ==================================================
# STEP 2
# DM STATUS
# ==================================================

class SystemDMStatusView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        data: dict,
    ):

        super().__init__(
            timeout=600
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.data = data

        self.dm_select = discord.ui.Select(
            placeholder=(
                "Choose the system's DM status"
            ),
            options=[
                discord.SelectOption(
                    label="DMs Open",
                    value="🟢 DMs Open",
                ),

                discord.SelectOption(
                    label="Ask to DM",
                    value="🟡 Ask to DM",
                ),

                discord.SelectOption(
                    label="DMs Closed",
                    value="🔴 DMs Closed",
                ),
            ],
        )

        self.dm_select.callback = (
            self.dm_callback
        )

        self.add_item(
            self.dm_select
        )

    def status_text(self):

        return (
            "🌸 **System Profile — DM Status**\n\n"

            f"**DM Status:** "
            f"{clean_value(self.data.get('dm_status'))}\n\n"

            "Choose an option, then press **Next**."
        )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):

        if (
            interaction.user.id
            != self.user_id
        ):

            await interaction.response.send_message(
                (
                    "❌ This system profile "
                    "setup isn't for you."
                ),
                ephemeral=True,
            )

            return False

        return True

    async def dm_callback(
        self,
        interaction: discord.Interaction,
    ):

        self.data["dm_status"] = (
            self.dm_select.values[0]
        )

        await interaction.response.edit_message(
            content=self.status_text(),
            view=self,
        )

    @discord.ui.button(
        label="Next",
        emoji="➡️",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.data.get(
            "dm_status"
        ):

            return await interaction.response.send_message(
                (
                    "❌ Choose a DM status first."
                ),
                ephemeral=True,
            )

        await interaction.response.send_modal(
            SystemDetailsModal(
                bot=self.bot,
                guild_id=self.guild_id,
                user_id=self.user_id,
                data=self.data,
            )
        )


# ==================================================
# STEP 3
# SYSTEM DETAILS
# ==================================================

class SystemDetailsModal(
    discord.ui.Modal
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        data: dict,
    ):

        super().__init__(
            title="System Profile Details"
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.data = data

        self.frequent_fronters = (
            discord.ui.TextInput(
                label="Frequent Fronters",
                placeholder=(
                    "Optional — names of frequent fronters"
                ),
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=500,
                default=(
                    data.get(
                        "frequent_fronters"
                    )
                    or ""
                ),
            )
        )

        self.shared_interests = (
            discord.ui.TextInput(
                label="Shared Interests",
                placeholder=(
                    "Things the system commonly enjoys"
                ),
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=500,
                default=(
                    data.get(
                        "shared_interests"
                    )
                    or ""
                ),
            )
        )

        self.communication_preferences = (
            discord.ui.TextInput(
                label="Communication Preferences",
                placeholder=(
                    "How do you prefer people to interact with you?"
                ),
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=700,
                default=(
                    data.get(
                        "communication_preferences"
                    )
                    or ""
                ),
            )
        )

        self.boundaries = (
            discord.ui.TextInput(
                label="Boundaries",
                placeholder=(
                    "Anything people should be aware of"
                ),
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=700,
                default=(
                    data.get(
                        "boundaries"
                    )
                    or ""
                ),
            )
        )

        self.extra = (
            discord.ui.TextInput(
                label="Extra",
                placeholder=(
                    "Anything else you'd like to share"
                ),
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=700,
                default=(
                    data.get(
                        "extra"
                    )
                    or ""
                ),
            )
        )

        self.add_item(
            self.frequent_fronters
        )

        self.add_item(
            self.shared_interests
        )

        self.add_item(
            self.communication_preferences
        )

        self.add_item(
            self.boundaries
        )

        self.add_item(
            self.extra
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        self.data.update(
            {
                "frequent_fronters":
                    str(
                        self.frequent_fronters.value
                    ).strip(),

                "shared_interests":
                    str(
                        self.shared_interests.value
                    ).strip(),

                "communication_preferences":
                    str(
                        self.communication_preferences.value
                    ).strip(),

                "boundaries":
                    str(
                        self.boundaries.value
                    ).strip(),

                "extra":
                    str(
                        self.extra.value
                    ).strip(),
            }
        )

        guild = (
            self.bot.get_guild(
                self.guild_id
            )
        )

        if guild is None:

            return await interaction.response.send_message(
                "❌ I couldn't find the server.",
                ephemeral=True,
            )

        member = guild.get_member(
            self.user_id
        )

        if member is None:

            return await interaction.response.send_message(
                (
                    "❌ I couldn't find your "
                    "member account."
                ),
                ephemeral=True,
            )

        existing_profile = None

        try:

            existing_profile = (
                await get_system_profile(
                    guild.id,
                    member.id,
                )
            )

        except Exception:
            pass

        alter_count = 0

        if existing_profile:

            try:

                alters = (
                    await get_alter_profiles(
                        existing_profile["id"]
                    )
                )

                alter_count = len(
                    alters
                )

            except Exception:
                alter_count = 0

        embed = build_system_profile_embed(
            member,
            self.data,
            alter_count,
        )

        view = SystemProfilePreviewView(
            bot=self.bot,
            guild_id=self.guild_id,
            user_id=self.user_id,
            data=self.data,
        )

        await interaction.response.send_message(
            (
                "🌸 **System Profile Preview**\n\n"
                "Check everything below, "
                "then press **Save System Profile**."
            ),
            embed=embed,
            view=view,
            ephemeral=True,
        )


# ==================================================
# STEP 4
# SAVE / PREVIEW
# ==================================================

class SystemProfilePreviewView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        data: dict,
    ):

        super().__init__(
            timeout=600
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.data = data

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):

        if (
            interaction.user.id
            != self.user_id
        ):

            await interaction.response.send_message(
                (
                    "❌ This system profile "
                    "isn't yours."
                ),
                ephemeral=True,
            )

            return False

        return True

    @discord.ui.button(
        label="Save System Profile",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def save_profile(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        guild = self.bot.get_guild(
            self.guild_id
        )

        if guild is None:

            return await interaction.followup.send(
                "❌ I couldn't find the server.",
                ephemeral=True,
            )

        member = guild.get_member(
            self.user_id
        )

        if member is None:

            return await interaction.followup.send(
                (
                    "❌ I couldn't find your "
                    "member account."
                ),
                ephemeral=True,
            )

        # --------------------------------------------------
        # GET CHANNEL SETTINGS
        # --------------------------------------------------

        try:

            settings = (
                await get_system_profile_settings(
                    guild.id
                )
            )

        except Exception:

            traceback.print_exc()

            return await interaction.followup.send(
                (
                    "❌ I couldn't load the "
                    "System Profile settings."
                ),
                ephemeral=True,
            )

        if (
            not settings
            or not settings.get(
                "profile_channel_id"
            )
        ):

            return await interaction.followup.send(
                (
                    "❌ No System Profiles channel "
                    "has been configured."
                ),
                ephemeral=True,
            )

        channel = guild.get_channel(
            settings[
                "profile_channel_id"
            ]
        )

        if channel is None:

            return await interaction.followup.send(
                (
                    "❌ The configured System "
                    "Profiles channel no longer exists."
                ),
                ephemeral=True,
            )

        # --------------------------------------------------
        # OLD PROFILE
        # --------------------------------------------------

        try:

            old_profile = (
                await get_system_profile(
                    guild.id,
                    member.id,
                )
            )

        except Exception:

            old_profile = None

        old_message_id = (
            old_profile.get(
                "profile_message_id"
            )
            if old_profile
            else None
        )

        # --------------------------------------------------
        # SAVE DATABASE PROFILE
        # --------------------------------------------------

        try:

            system_profile_id = (
                await save_system_profile(
                    guild_id=guild.id,
                    user_id=member.id,

                    system_name=(
                        self.data.get(
                            "system_name"
                        )
                    ),

                    collective_name=(
                        self.data.get(
                            "collective_name"
                        )
                    ),

                    collective_pronouns=(
                        self.data.get(
                            "collective_pronouns"
                        )
                    ),

                    system_size=(
                        self.data.get(
                            "system_size"
                        )
                    ),

                    system_type=(
                        self.data.get(
                            "system_type"
                        )
                    ),

                    frequent_fronters=(
                        self.data.get(
                            "frequent_fronters"
                        )
                    ),

                    shared_interests=(
                        self.data.get(
                            "shared_interests"
                        )
                    ),

                    communication_preferences=(
                        self.data.get(
                            "communication_preferences"
                        )
                    ),

                    boundaries=(
                        self.data.get(
                            "boundaries"
                        )
                    ),

                    dm_status=(
                        self.data.get(
                            "dm_status"
                        )
                    ),

                    extra=(
                        self.data.get(
                            "extra"
                        )
                    ),
                )
            )

        except Exception:

            traceback.print_exc()

            return await interaction.followup.send(
                (
                    "❌ I couldn't save "
                    "your System Profile."
                ),
                ephemeral=True,
            )

        # --------------------------------------------------
        # COUNT ALTER PROFILES
        # --------------------------------------------------

        try:

            alters = (
                await get_alter_profiles(
                    system_profile_id
                )
            )

            alter_count = len(
                alters
            )

        except Exception:

            alter_count = 0

        profile_data = dict(
            self.data
        )

        profile_data["id"] = (
            system_profile_id
        )

        embed = build_system_profile_embed(
            member,
            profile_data,
            alter_count,
        )

        posted = False

        # --------------------------------------------------
        # UPDATE EXISTING MESSAGE
        # --------------------------------------------------

        if old_message_id:

            try:

                old_message = (
                    await channel.fetch_message(
                        old_message_id
                    )
                )

                await old_message.edit(
                    embed=embed
                )

                posted = True

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
            ):

                posted = False

        # --------------------------------------------------
        # CREATE NEW MESSAGE
        # --------------------------------------------------

        if not posted:

            try:

                message = await channel.send(
                    embed=embed
                )

                await set_system_profile_message(
                    system_profile_id,
                    message.id,
                )

                posted = True

            except (
                discord.Forbidden,
                discord.HTTPException,
            ):

                traceback.print_exc()

        # --------------------------------------------------
        # DISABLE PREVIEW BUTTONS
        # --------------------------------------------------

        for child in self.children:
            child.disabled = True

        try:

            await interaction.message.edit(
                view=self
            )

        except discord.HTTPException:
            pass

        # --------------------------------------------------
        # RESULT
        # --------------------------------------------------

        if posted:

            result = (
                "✅ **System Profile saved!**\n"
                f"🌸 Posted in {channel.mention}."
            )

        else:

            result = (
                "⚠️ Your System Profile was saved, "
                "but I couldn't post it in the "
                "System Profiles channel."
            )

        await interaction.followup.send(
            result,
            ephemeral=True,
        )

        self.stop()

    @discord.ui.button(
        label="Cancel",
        emoji="✖️",
        style=discord.ButtonStyle.danger,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        self.stop()

        await interaction.response.edit_message(
            content=(
                "❌ System Profile setup cancelled."
            ),
            embed=None,
            view=None,
        )


# ==================================================
# SYSTEM PROFILE COG
# ==================================================

class SystemProfiles(
    commands.Cog
):

    systemprofile = app_commands.Group(
        name="systemprofile",
        description=(
            "Create and manage system profiles."
        ),
    )

    def __init__(
        self,
        bot,
    ):

        self.bot = bot

    # ==================================================
    # PERMISSION HELPERS
    # ==================================================

    async def get_server_roles(
        self,
        guild: discord.Guild,
    ):

        settings = (
            await self.bot.db
            .get_guild_settings(
                guild.id
            )
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

    async def is_admin(
        self,
        interaction: discord.Interaction,
    ):

        guild = interaction.guild
        member = interaction.user

        if (
            guild is None
            or not isinstance(
                member,
                discord.Member,
            )
        ):
            return False

        if member.guild_permissions.administrator:
            return True

        admin_role, _, _ = (
            await self.get_server_roles(
                guild
            )
        )

        return bool(
            admin_role
            and admin_role in member.roles
        )

    async def has_member_access(
        self,
        interaction: discord.Interaction,
    ):

        guild = interaction.guild
        member = interaction.user

        if (
            guild is None
            or not isinstance(
                member,
                discord.Member,
            )
        ):
            return False

        if member.guild_permissions.administrator:
            return True

        admin_role, mod_role, member_role = (
            await self.get_server_roles(
                guild
            )
        )

        return any(
            role and role in member.roles
            for role in (
                admin_role,
                mod_role,
                member_role,
            )
        )

    # ==================================================
    # DATABASE STARTUP
    # ==================================================

    async def cog_load(self):

        try:

            await init_system_profile_tables()

            print(
                "✅ System profile database ready."
            )

        except Exception as e:

            traceback.print_exc()

            print(
                (
                    "❌ System profile database "
                    f"setup failed: {e}"
                )
            )

    # ==================================================
    # /SYSTEMPROFILE CONFIGURE
    # ==================================================

    @systemprofile.command(
        name="configure",
        description=(
            "Choose where system profiles are posted."
        ),
    )
    @app_commands.describe(
        channel=(
            "Channel where system profiles are posted"
        ),
    )
    async def configure(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):

        if not await self.is_admin(
            interaction
        ):

            return await interaction.response.send_message(
                (
                    "❌ Only the configured "
                    "**Admin role** can use "
                    "`/systemprofile configure`."
                ),
                ephemeral=True,
            )

        bot_member = (
            interaction.guild.me
        )

        permissions = (
            channel.permissions_for(
                bot_member
            )
        )

        if not (
            permissions.view_channel
            and permissions.send_messages
            and permissions.embed_links
        ):

            return await interaction.response.send_message(
                (
                    "❌ I need **View Channel**, "
                    "**Send Messages**, and "
                    "**Embed Links** in that channel."
                ),
                ephemeral=True,
            )

        try:

            await set_system_profile_channel(
                interaction.guild.id,
                channel.id,
            )

        except Exception:

            traceback.print_exc()

            return await interaction.response.send_message(
                (
                    "❌ I couldn't save "
                    "that channel."
                ),
                ephemeral=True,
            )

        await interaction.response.send_message(
            (
                "✅ **System Profiles configured!**\n\n"
                f"Profiles will be posted in "
                f"{channel.mention}."
            ),
            ephemeral=True,
        )

    # ==================================================
    # /SYSTEMPROFILE CHANNEL
    # ==================================================

    @systemprofile.command(
        name="channel",
        description=(
            "Show the System Profiles channel."
        ),
    )
    async def show_channel(
        self,
        interaction: discord.Interaction,
    ):

        if not await self.has_member_access(
            interaction
        ):

            return await interaction.response.send_message(
                (
                    "❌ You need the configured "
                    "**Member, Mod, or Admin role** "
                    "to use this command."
                ),
                ephemeral=True,
            )

        settings = (
            await get_system_profile_settings(
                interaction.guild.id
            )
        )

        if (
            not settings
            or not settings.get(
                "profile_channel_id"
            )
        ):

            return await interaction.response.send_message(
                (
                    "⚠️ No System Profiles "
                    "channel is configured."
                ),
                ephemeral=True,
            )

        await interaction.response.send_message(
            (
                "🌸 System Profiles channel: "
                f"<#{settings['profile_channel_id']}>"
            ),
            ephemeral=True,
        )

    # ==================================================
    # /SYSTEMPROFILE SETUP
    # ==================================================

    @systemprofile.command(
        name="setup",
        description=(
            "Create your System Profile."
        ),
    )
    async def setup_profile(
        self,
        interaction: discord.Interaction,
    ):

        if not await self.has_member_access(
            interaction
        ):

            return await interaction.response.send_message(
                (
                    "❌ You need the configured "
                    "**Member, Mod, or Admin role** "
                    "to create a System Profile."
                ),
                ephemeral=True,
            )

        # --------------------------------------------------
        # CHECK CONFIG
        # --------------------------------------------------

        try:

            settings = (
                await get_system_profile_settings(
                    interaction.guild.id
                )
            )

        except Exception:

            traceback.print_exc()

            return await interaction.response.send_message(
                (
                    "❌ I couldn't load "
                    "System Profile settings."
                ),
                ephemeral=True,
            )

        if (
            not settings
            or not settings.get(
                "profile_channel_id"
            )
        ):

            return await interaction.response.send_message(
                (
                    "⚠️ An admin needs to run "
                    "`/systemprofile configure` first."
                ),
                ephemeral=True,
            )

        # --------------------------------------------------
        # LOAD EXISTING PROFILE
        # --------------------------------------------------

        try:

            existing = (
                await get_system_profile(
                    interaction.guild.id,
                    interaction.user.id,
                )
            )

        except Exception:

            existing = None

        # --------------------------------------------------
        # OPEN FORM
        # --------------------------------------------------

        await interaction.response.send_modal(
            SystemBasicModal(
                bot=self.bot,
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                existing=existing,
            )
        )

    # ==================================================
    # /SYSTEMPROFILE EDIT
    # ==================================================

    @systemprofile.command(
        name="edit",
        description=(
            "Edit your System Profile."
        ),
    )
    async def edit_profile(
        self,
        interaction: discord.Interaction,
    ):

        if not await self.has_member_access(
            interaction
        ):

            return await interaction.response.send_message(
                (
                    "❌ You need the configured "
                    "**Member, Mod, or Admin role** "
                    "to edit a System Profile."
                ),
                ephemeral=True,
            )

        try:

            existing = (
                await get_system_profile(
                    interaction.guild.id,
                    interaction.user.id,
                )
            )

        except Exception:

            traceback.print_exc()

            existing = None

        if not existing:

            return await interaction.response.send_message(
                (
                    "❌ You don't have a "
                    "System Profile yet.\n"
                    "Use `/systemprofile setup`."
                ),
                ephemeral=True,
            )

        await interaction.response.send_modal(
            SystemBasicModal(
                bot=self.bot,
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                existing=existing,
            )
        )

    # ==================================================
    # /SYSTEMPROFILE VIEW
    # ==================================================

    @systemprofile.command(
        name="view",
        description=(
            "View a System Profile."
        ),
    )
    @app_commands.describe(
        user=(
            "System member to view"
        ),
    )
    async def view_profile(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):

        if not await self.has_member_access(
            interaction
        ):

            return await interaction.response.send_message(
                (
                    "❌ You need the configured "
                    "**Member, Mod, or Admin role** "
                    "to view System Profiles."
                ),
                ephemeral=True,
            )

        target = (
            user
            or interaction.user
        )

        try:

            profile = (
                await get_system_profile(
                    interaction.guild.id,
                    target.id,
                )
            )

        except Exception:

            traceback.print_exc()

            profile = None

        if not profile:

            return await interaction.response.send_message(
                (
                    "❌ That member doesn't "
                    "have a System Profile."
                ),
                ephemeral=True,
            )

        try:

            alters = (
                await get_alter_profiles(
                    profile["id"]
                )
            )

            alter_count = len(
                alters
            )

        except Exception:

            alter_count = 0

        embed = build_system_profile_embed(
            target,
            profile,
            alter_count,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


# ==================================================
# LOAD COG
# ==================================================

async def setup(bot):

    await bot.add_cog(
        SystemProfiles(bot)
    )
