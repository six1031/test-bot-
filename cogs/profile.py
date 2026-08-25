import traceback
import discord

from discord.ext import commands
from discord import app_commands


# ==================================================
# HELPERS
# ==================================================

def clean_value(value):
    if value is None:
        return "Not set"

    value = str(value).strip()
    return value or "Not set"


def build_profile_embed(member: discord.Member, profile: dict):
    nickname = clean_value(profile.get("nickname"))

    embed = discord.Embed(
        title=f"+:ꔫ:﹤{nickname}﹥:ꔫ:+ﾟ",
        description=(
            f"⋆ ˚｡⋆୨୧˚ **Age:** {clean_value(profile.get('age'))}\n\n"
            f"⋆ ˚｡⋆୨୧˚ **Gender:** {clean_value(profile.get('gender'))}\n\n"
            f"⋆ ˚｡⋆୨୧˚ **Pronouns:** {clean_value(profile.get('pronouns'))}\n\n"
            f"⋆ ˚｡⋆୨୧˚ **Sexuality:** {clean_value(profile.get('sexuality'))}\n\n"
            f"⋆ ˚｡⋆୨୧˚ **Language(s):** {clean_value(profile.get('languages'))}\n\n"
            f"⋆ ˚｡⋆୨୧˚ **Relationship Status:** "
            f"{clean_value(profile.get('relationship_status'))}\n\n"
            f"⋆ ˚｡⋆୨୧˚ **Likes:** {clean_value(profile.get('likes'))}\n\n"
            f"⋆ ˚｡⋆୨୧˚ **Dislikes:** {clean_value(profile.get('dislikes'))}\n\n"
            f"⋆ ˚｡⋆୨୧˚ **DNI if:** {clean_value(profile.get('dni'))}\n\n"
            f"⋆ ˚｡⋆୨୧˚ **DM Status:** {clean_value(profile.get('dm_status'))}\n\n"
            f"⋆ ˚｡⋆୨୧˚ **Extra:** {clean_value(profile.get('extra'))}"
        ),
    )

    embed.set_author(
        name=f"Profile for {nickname}",
        icon_url=member.display_avatar.url,
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.set_footer(
        text="Member profile"
    )

    return embed


# ==================================================
# STEP 1 - BASIC INFO
# ==================================================

class BasicProfileModal(
    discord.ui.Modal,
    title="Create Your Profile",
):

    nickname = discord.ui.TextInput(
        label="Name / nickname",
        placeholder="What would you like us to call you?",
        required=True,
        max_length=32,
    )

    age = discord.ui.TextInput(
        label="Age",
        placeholder="Your age",
        required=True,
        max_length=3,
    )

    pronouns = discord.ui.TextInput(
        label="Pronouns",
        placeholder="Example: she/her, he/him, they/them",
        required=False,
        max_length=50,
    )

    sexuality = discord.ui.TextInput(
        label="Sexuality",
        placeholder="Optional - leave blank if you prefer",
        required=False,
        max_length=80,
    )

    languages = discord.ui.TextInput(
        label="Language(s)",
        placeholder="Example: English, Spanish",
        required=False,
        max_length=100,
    )

    def __init__(
        self,
        bot,
        user_id: int,
        existing: dict | None = None,
    ):
        super().__init__()

        self.bot = bot
        self.user_id = user_id
        self.existing = existing or {}

        self.nickname.default = (
            self.existing.get("nickname")
            or ""
        )

        self.age.default = (
            self.existing.get("age")
            or ""
        )

        self.pronouns.default = (
            self.existing.get("pronouns")
            or ""
        )

        self.sexuality.default = (
            self.existing.get("sexuality")
            or ""
        )

        self.languages.default = (
            self.existing.get("languages")
            or ""
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
                "nickname":
                    str(
                        self.nickname.value
                    ).strip(),

                "age":
                    str(
                        self.age.value
                    ).strip(),

                "pronouns":
                    str(
                        self.pronouns.value
                    ).strip(),

                "sexuality":
                    str(
                        self.sexuality.value
                    ).strip(),

                "languages":
                    str(
                        self.languages.value
                    ).strip(),
            }
        )

        view = ProfileChoicesView(
            bot=self.bot,
            user_id=self.user_id,
            data=data,
        )

        await interaction.response.send_message(
            view.status_text(),
            view=view,
            ephemeral=True,
        )


# ==================================================
# STEP 2 - DROPDOWN CHOICES
# ==================================================

class ProfileChoicesView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        user_id: int,
        data: dict,
    ):
        super().__init__(
            timeout=600
        )

        self.bot = bot
        self.user_id = user_id
        self.data = data

        # --------------------------------------------------
        # GENDER
        # --------------------------------------------------

        self.gender_select = discord.ui.Select(
            placeholder="Choose your gender",
            options=[
                discord.SelectOption(
                    label="Woman",
                    value="Woman",
                ),
                discord.SelectOption(
                    label="Man",
                    value="Man",
                ),
                discord.SelectOption(
                    label="Non-binary",
                    value="Non-binary",
                ),
                discord.SelectOption(
                    label="Genderfluid",
                    value="Genderfluid",
                ),
                discord.SelectOption(
                    label="Agender",
                    value="Agender",
                ),
                discord.SelectOption(
                    label="Other / self describe",
                    value="Other",
                ),
                discord.SelectOption(
                    label="Prefer not to say",
                    value="Prefer not to say",
                ),
            ],
        )

        # --------------------------------------------------
        # RELATIONSHIP STATUS
        # --------------------------------------------------

        self.relationship_select = discord.ui.Select(
            placeholder="Choose your relationship status",
            options=[
                discord.SelectOption(
                    label="Single",
                    value="Single",
                ),
                discord.SelectOption(
                    label="Taken",
                    value="Taken",
                ),
                discord.SelectOption(
                    label="Married",
                    value="Married",
                ),
                discord.SelectOption(
                    label="It's complicated",
                    value="It's complicated",
                ),
                discord.SelectOption(
                    label="Not looking",
                    value="Not looking",
                ),
                discord.SelectOption(
                    label="Prefer not to say",
                    value="Prefer not to say",
                ),
            ],
        )

        # --------------------------------------------------
        # DM STATUS
        # --------------------------------------------------

        self.dm_select = discord.ui.Select(
            placeholder="Choose your DM status",
            options=[
                discord.SelectOption(
                    label="DMs Open",
                    value="🟢 DMs Open",
                ),
                discord.SelectOption(
                    label="Ask First",
                    value="🟡 Ask First",
                ),
                discord.SelectOption(
                    label="DMs Closed",
                    value="🔴 DMs Closed",
                ),
            ],
        )

        self.gender_select.callback = (
            self.gender_callback
        )

        self.relationship_select.callback = (
            self.relationship_callback
        )

        self.dm_select.callback = (
            self.dm_callback
        )

        self.add_item(
            self.gender_select
        )

        self.add_item(
            self.relationship_select
        )

        self.add_item(
            self.dm_select
        )

    def status_text(
        self,
    ):

        return (
            "🌸 **Profile setup — choices**\n\n"

            f"**Gender:** "
            f"{clean_value(self.data.get('gender'))}\n"

            f"**Relationship status:** "
            f"{clean_value(self.data.get('relationship_status'))}\n"

            f"**DM status:** "
            f"{clean_value(self.data.get('dm_status'))}\n\n"

            "Choose one option from each menu, "
            "then press **Next**."
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
                "❌ This profile setup is not for you.",
                ephemeral=True,
            )

            return False

        return True

    async def gender_callback(
        self,
        interaction: discord.Interaction,
    ):

        self.data["gender"] = (
            self.gender_select.values[0]
        )

        await interaction.response.edit_message(
            content=self.status_text(),
            view=self,
        )

    async def relationship_callback(
        self,
        interaction: discord.Interaction,
    ):

        self.data[
            "relationship_status"
        ] = self.relationship_select.values[0]

        await interaction.response.edit_message(
            content=self.status_text(),
            view=self,
        )

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
        style=discord.ButtonStyle.primary,
        emoji="➡️",
        row=3,
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        missing = []

        if not self.data.get(
            "gender"
        ):
            missing.append(
                "Gender"
            )

        if not self.data.get(
            "relationship_status"
        ):
            missing.append(
                "Relationship status"
            )

        if not self.data.get(
            "dm_status"
        ):
            missing.append(
                "DM status"
            )

        if missing:

            return await interaction.response.send_message(
                (
                    "❌ Please choose: "
                    + ", ".join(
                        missing
                    )
                ),
                ephemeral=True,
            )

        await interaction.response.send_modal(
            MoreProfileDetailsModal(
                bot=self.bot,
                user_id=self.user_id,
                data=self.data,
            )
        )


# ==================================================
# STEP 3 - EXTRA DETAILS
# ==================================================

class MoreProfileDetailsModal(
    discord.ui.Modal,
    title="Profile Details",
):

    custom_gender = discord.ui.TextInput(
        label="Custom gender",
        placeholder="Only fill this if you chose Other",
        required=False,
        max_length=80,
    )

    likes = discord.ui.TextInput(
        label="Likes",
        placeholder="Things you enjoy",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    dislikes = discord.ui.TextInput(
        label="Dislikes",
        placeholder="Things you dislike",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    dni = discord.ui.TextInput(
        label="DNI if...",
        placeholder="Who should not interact with you?",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    extra = discord.ui.TextInput(
        label="Extra",
        placeholder="Anything else you want people to know?",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=700,
    )

    def __init__(
        self,
        bot,
        user_id: int,
        data: dict,
    ):

        super().__init__()

        self.bot = bot
        self.user_id = user_id
        self.data = data

        self.likes.default = (
            data.get("likes")
            or ""
        )

        self.dislikes.default = (
            data.get("dislikes")
            or ""
        )

        self.dni.default = (
            data.get("dni")
            or ""
        )

        self.extra.default = (
            data.get("extra")
            or ""
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        if (
            self.data.get("gender")
            == "Other"
        ):

            custom_gender = str(
                self.custom_gender.value
            ).strip()

            self.data["gender"] = (
                custom_gender
                or "Other"
            )

        self.data.update(
            {
                "likes":
                    str(
                        self.likes.value
                    ).strip(),

                "dislikes":
                    str(
                        self.dislikes.value
                    ).strip(),

                "dni":
                    str(
                        self.dni.value
                    ).strip(),

                "extra":
                    str(
                        self.extra.value
                    ).strip(),
            }
        )

        member = (
            interaction.guild.get_member(
                self.user_id
            )
        )

        if member is None:

            return await interaction.response.send_message(
                "❌ I could not find your member account.",
                ephemeral=True,
            )

        embed = build_profile_embed(
            member,
            self.data,
        )

        view = ProfilePreviewView(
            bot=self.bot,
            user_id=self.user_id,
            data=self.data,
        )

        await interaction.response.send_message(
            (
                "🌸 **Profile preview**\n"
                "Check everything below, then press "
                "**Save Profile**."
            ),
            embed=embed,
            view=view,
            ephemeral=True,
        )


# ==================================================
# STEP 4 - PREVIEW AND SAVE
# ==================================================

class ProfilePreviewView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        user_id: int,
        data: dict,
    ):

        super().__init__(
            timeout=600
        )

        self.bot = bot
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
                "❌ This profile preview is not for you.",
                ephemeral=True,
            )

            return False

        return True

    # --------------------------------------------------
    # SAVE
    # --------------------------------------------------

    @discord.ui.button(
        label="Save Profile",
        style=discord.ButtonStyle.success,
        emoji="✅",
    )
    async def save_profile(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        guild = interaction.guild

        member = guild.get_member(
            self.user_id
        )

        if member is None:

            return await interaction.followup.send(
                "❌ I could not find your member account.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # LOAD SERVER SETTINGS
        # --------------------------------------------------

        try:

            settings = (
                await self.bot.db
                .get_guild_settings(
                    guild.id
                )
            )

        except Exception:

            traceback.print_exc()

            return await interaction.followup.send(
                "❌ I could not load the server profile settings.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # LOAD OLD PROFILE IF THEY HAVE ONE
        # --------------------------------------------------

        try:

            old_profile = (
                await self.bot.db
                .get_member_profile(
                    guild.id,
                    member.id,
                )
            )

        except Exception:

            old_profile = None

        old_message_id = None

        if old_profile:

            old_message_id = (
                old_profile.get(
                    "intro_message_id"
                )
            )

        nickname = (
            self.data.get(
                "nickname"
            )
        )

        # --------------------------------------------------
        # SAVE DATABASE PROFILE
        # --------------------------------------------------

        try:

            await self.bot.db.save_member_profile(
                guild_id=guild.id,
                user_id=member.id,
                nickname=nickname,
                age=self.data.get("age"),
                gender=self.data.get("gender"),
                pronouns=self.data.get("pronouns"),
                sexuality=self.data.get("sexuality"),
                languages=self.data.get("languages"),
                relationship_status=self.data.get(
                    "relationship_status"
                ),
                likes=self.data.get("likes"),
                dislikes=self.data.get("dislikes"),
                dni=self.data.get("dni"),
                dm_status=self.data.get("dm_status"),
                extra=self.data.get("extra"),
                intro_message_id=old_message_id,
                profile_complete=True,
            )

        except Exception:

            traceback.print_exc()

            return await interaction.followup.send(
                "❌ I could not save your profile.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # APPLY THEIR CHOSEN SERVER NICKNAME
        # --------------------------------------------------

        nickname_changed = True

        try:

            await member.edit(
                nick=nickname,
                reason="Member profile nickname",
            )

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):

            nickname_changed = False

        # --------------------------------------------------
        # INTRO CHANNEL
        # --------------------------------------------------

        intro_channel = None

        if settings:

            intro_channel_id = (
                settings.get(
                    "intro_channel"
                )
            )

            if intro_channel_id:

                intro_channel = (
                    guild.get_channel(
                        intro_channel_id
                    )
                )

        profile_embed = (
            build_profile_embed(
                member,
                self.data,
            )
        )

        intro_updated = False

        # --------------------------------------------------
        # UPDATE EXISTING INTRO IF POSSIBLE
        # --------------------------------------------------

        if intro_channel:

            if old_message_id:

                try:

                    old_message = (
                        await intro_channel
                        .fetch_message(
                            old_message_id
                        )
                    )

                    await old_message.edit(
                        embed=profile_embed
                    )

                    intro_updated = True

                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException,
                ):

                    intro_updated = False

            # --------------------------------------------------
            # OTHERWISE CREATE A NEW INTRO
            # --------------------------------------------------

            if not intro_updated:

                try:

                    new_message = (
                        await intro_channel.send(
                            embed=profile_embed
                        )
                    )

                    await (
                        self.bot.db
                        .set_profile_intro_message(
                            guild.id,
                            member.id,
                            new_message.id,
                        )
                    )

                    intro_updated = True

                except (
                    discord.Forbidden,
                    discord.HTTPException,
                ):

                    traceback.print_exc()

        # --------------------------------------------------
        # DISABLE BUTTONS
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

        result = (
            "✅ **Your profile has been saved!**"
        )

        if intro_updated:

            result += (
                "\n🌸 Your profile has been posted "
                "or updated in the intros channel."
            )

        else:

            result += (
                "\n⚠️ Your profile was saved, but I could "
                "not post it in the intros channel."
            )

        if nickname_changed:

            result += (
                f"\n🏷️ Your server nickname is now "
                f"**{nickname}**."
            )

        else:

            result += (
                "\n⚠️ Your preferred name was saved, "
                "but I could not change your server nickname."
            )

        await interaction.followup.send(
            result,
            ephemeral=True,
        )

        self.stop()

    # --------------------------------------------------
    # CANCEL
    # --------------------------------------------------

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        emoji="✖️",
    )
    async def cancel_profile(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=(
                "❌ Profile setup cancelled. "
                "Nothing was saved."
            ),
            embed=None,
            view=self,
        )

        self.stop()


# ==================================================
# PROFILE COG
# ==================================================

class Profiles(
    commands.Cog
):

    profile = app_commands.Group(
        name="profile",
        description=(
            "Create and manage your member profile."
        ),
    )

    def __init__(
        self,
        bot,
    ):

        self.bot = bot

    # ==================================================
    # /PROFILE CONFIGURE
    # ==================================================

    @profile.command(
        name="configure",
        description=(
            "Configure the server profile system."
        ),
    )
    @app_commands.describe(
        verified_role=(
            "Role given after ID verification"
        ),
        intro_channel=(
            "Channel where profiles are posted"
        ),
    )
    async def configure(
        self,
        interaction: discord.Interaction,
        verified_role: discord.Role,
        intro_channel: discord.TextChannel,
    ):

        if not (
            interaction.user
            .guild_permissions
            .manage_guild
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You need "
                        "**Manage Server** "
                        "to use this command."
                    ),
                    ephemeral=True,
                )
            )

        try:

            await self.bot.db.upsert_guild_settings(
                guild_id=(
                    interaction.guild.id
                ),
                verified_role_id=(
                    verified_role.id
                ),
                intro_channel_id=(
                    intro_channel.id
                ),
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I could not save "
                        "the profile configuration."
                    ),
                    ephemeral=True,
                )
            )

        await interaction.response.send_message(
            (
                "✅ **Profile system configured!**\n\n"
                f"**Verified role:** "
                f"{verified_role.mention}\n"
                f"**Intros channel:** "
                f"{intro_channel.mention}"
            ),
            ephemeral=True,
        )

    # ==================================================
    # /PROFILE SETUP
    # ==================================================

    @profile.command(
        name="setup",
        description=(
            "Create your member profile."
        ),
    )
    async def setup_profile(
        self,
        interaction: discord.Interaction,
    ):

        try:

            settings = (
                await self.bot.db
                .get_guild_settings(
                    interaction.guild.id
                )
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I could not load "
                        "the profile settings."
                    ),
                    ephemeral=True,
                )
            )

        if (
            not settings
            or not settings.get(
                "intro_channel"
            )
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "⚠️ The profile system "
                        "has not been configured yet.\n"
                        "An admin needs to run "
                        "`/profile configure` first."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # CHECK VERIFIED ROLE
        # --------------------------------------------------

        verified_role_id = (
            settings.get(
                "verified_role"
            )
        )

        if verified_role_id:

            verified_role = (
                interaction.guild
                .get_role(
                    verified_role_id
                )
            )

            if (
                verified_role
                and verified_role
                not in interaction.user.roles
            ):

                return await (
                    interaction.response
                    .send_message(
                        (
                            "❌ You need the configured "
                            "verified role before "
                            "creating a profile."
                        ),
                        ephemeral=True,
                    )
                )

        # --------------------------------------------------
        # PREFILL IF PROFILE EXISTS
        # --------------------------------------------------

        try:

            existing = (
                await self.bot.db
                .get_member_profile(
                    interaction.guild.id,
                    interaction.user.id,
                )
            )

        except Exception:

            existing = None

        await interaction.response.send_modal(
            BasicProfileModal(
                bot=self.bot,
                user_id=interaction.user.id,
                existing=existing,
            )
        )

    # ==================================================
    # /PROFILE EDIT
    # ==================================================

    @profile.command(
        name="edit",
        description=(
            "Edit your saved member profile."
        ),
    )
    async def edit_profile(
        self,
        interaction: discord.Interaction,
    ):

        try:

            existing = (
                await self.bot.db
                .get_member_profile(
                    interaction.guild.id,
                    interaction.user.id,
                )
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I could not load "
                        "your saved profile."
                    ),
                    ephemeral=True,
                )
            )

        if not existing:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You do not have "
                        "a saved profile yet.\n"
                        "Use `/profile setup` first."
                    ),
                    ephemeral=True,
                )
            )

        await interaction.response.send_modal(
            BasicProfileModal(
                bot=self.bot,
                user_id=interaction.user.id,
                existing=existing,
            )
        )

    # ==================================================
    # /PROFILE VIEW
    # ==================================================

    @profile.command(
        name="view",
        description=(
            "View a member's saved profile."
        ),
    )
    @app_commands.describe(
        user=(
            "Member whose profile you want to view"
        ),
    )
    async def view_profile(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):

        target = (
            user
            or interaction.user
        )

        try:

            profile = (
                await self.bot.db
                .get_member_profile(
                    interaction.guild.id,
                    target.id,
                )
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I could not load "
                        "that profile."
                    ),
                    ephemeral=True,
                )
            )

        if not profile:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ That member has not "
                        "created a profile yet."
                    ),
                    ephemeral=True,
                )
            )

        await interaction.response.send_message(
            embed=build_profile_embed(
                target,
                profile,
            ),
            ephemeral=True,
        )


# ==================================================
# LOAD COG
# ==================================================

async def setup(
    bot,
):

    await bot.add_cog(
        Profiles(
            bot
        )
    )
