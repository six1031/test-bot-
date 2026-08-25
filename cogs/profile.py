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


def private_response(interaction: discord.Interaction) -> bool:
    # Ephemeral replies are used inside the server.
    # DM interactions use normal replies.
    return interaction.guild is not None


async def get_guild_and_member(
    bot,
    guild_id: int,
    user_id: int,
):
    guild = bot.get_guild(guild_id)

    if guild is None:
        return None, None

    member = guild.get_member(user_id)

    if member is None:
        try:
            member = await guild.fetch_member(
                user_id
            )

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            member = None

    return guild, member


def build_profile_embed(
    member: discord.Member,
    profile: dict,
):
    nickname = clean_value(
        profile.get("nickname")
    )

    embed = discord.Embed(
        title=f"+:ꔫ:﹤{nickname}﹥:ꔫ:+ﾟ",
        description=(
            f"⋆ ˚｡⋆୨୧˚ **Age:** "
            f"{clean_value(profile.get('age'))}\n\n"

            f"⋆ ˚｡⋆୨୧˚ **Gender:** "
            f"{clean_value(profile.get('gender'))}\n\n"

            f"⋆ ˚｡⋆୨୧˚ **Pronouns:** "
            f"{clean_value(profile.get('pronouns'))}\n\n"

            f"⋆ ˚｡⋆୨୧˚ **Sexuality:** "
            f"{clean_value(profile.get('sexuality'))}\n\n"

            f"⋆ ˚｡⋆୨୧˚ **Language(s):** "
            f"{clean_value(profile.get('languages'))}\n\n"

            f"⋆ ˚｡⋆୨୧˚ **Relationship Status:** "
            f"{clean_value(profile.get('relationship_status'))}\n\n"

            f"⋆ ˚｡⋆୨୧˚ **Likes:** "
            f"{clean_value(profile.get('likes'))}\n\n"

            f"⋆ ˚｡⋆୨୧˚ **Dislikes:** "
            f"{clean_value(profile.get('dislikes'))}\n\n"

            f"⋆ ˚｡⋆୨୧˚ **DNI if:** "
            f"{clean_value(profile.get('dni'))}\n\n"

            f"⋆ ˚｡⋆୨୧˚ **DM Status:** "
            f"{clean_value(profile.get('dm_status'))}\n\n"

            f"⋆ ˚｡⋆୨୧˚ **Extra:** "
            f"{clean_value(profile.get('extra'))}"
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
            title="Create Your Profile"
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.existing = existing or {}

        self.nickname = discord.ui.TextInput(
            label="Name / nickname",
            placeholder=(
                "What would you like us to call you?"
            ),
            required=True,
            max_length=32,
            default=(
                self.existing.get("nickname")
                or ""
            ),
        )

        self.age = discord.ui.TextInput(
            label="Age",
            placeholder="Your age",
            required=True,
            max_length=3,
            default=(
                self.existing.get("age")
                or ""
            ),
        )

        self.pronouns = discord.ui.TextInput(
            label="Pronouns",
            placeholder=(
                "Example: she/her, he/him, they/them"
            ),
            required=False,
            max_length=50,
            default=(
                self.existing.get("pronouns")
                or ""
            ),
        )

        self.sexuality = discord.ui.TextInput(
            label="Sexuality",
            placeholder=(
                "Optional - leave blank if you prefer"
            ),
            required=False,
            max_length=80,
            default=(
                self.existing.get("sexuality")
                or ""
            ),
        )

        self.languages = discord.ui.TextInput(
            label="Language(s)",
            placeholder=(
                "Example: English, Spanish"
            ),
            required=False,
            max_length=100,
            default=(
                self.existing.get("languages")
                or ""
            ),
        )

        self.add_item(
            self.nickname
        )

        self.add_item(
            self.age
        )

        self.add_item(
            self.pronouns
        )

        self.add_item(
            self.sexuality
        )

        self.add_item(
            self.languages
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
            guild_id=self.guild_id,
            user_id=self.user_id,
            data=data,
        )

        await interaction.response.send_message(
            view.status_text(),
            view=view,
            ephemeral=(
                private_response(
                    interaction
                )
            ),
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

        # --------------------------------------------------
        # GENDER
        # --------------------------------------------------

        self.gender_select = (
            discord.ui.Select(
                placeholder=(
                    "Choose your gender"
                ),
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
                        label=(
                            "Other / self describe"
                        ),
                        value="Other",
                    ),

                    discord.SelectOption(
                        label=(
                            "Prefer not to say"
                        ),
                        value=(
                            "Prefer not to say"
                        ),
                    ),
                ],
            )
        )

        # --------------------------------------------------
        # RELATIONSHIP STATUS
        # --------------------------------------------------

        self.relationship_select = (
            discord.ui.Select(
                placeholder=(
                    "Choose your relationship status"
                ),
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
                        label=(
                            "It's complicated"
                        ),
                        value=(
                            "It's complicated"
                        ),
                    ),

                    discord.SelectOption(
                        label="Not looking",
                        value="Not looking",
                    ),

                    discord.SelectOption(
                        label=(
                            "Prefer not to say"
                        ),
                        value=(
                            "Prefer not to say"
                        ),
                    ),
                ],
            )
        )

        # --------------------------------------------------
        # DM STATUS
        # --------------------------------------------------

        self.dm_select = (
            discord.ui.Select(
                placeholder=(
                    "Choose your DM status"
                ),
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
            await (
                interaction.response
                .send_message(
                    (
                        "❌ This profile setup "
                        "is not for you."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
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

        await (
            interaction.response
            .edit_message(
                content=self.status_text(),
                view=self,
            )
        )

    async def relationship_callback(
        self,
        interaction: discord.Interaction,
    ):
        self.data[
            "relationship_status"
        ] = (
            self.relationship_select
            .values[0]
        )

        await (
            interaction.response
            .edit_message(
                content=self.status_text(),
                view=self,
            )
        )

    async def dm_callback(
        self,
        interaction: discord.Interaction,
    ):
        self.data["dm_status"] = (
            self.dm_select.values[0]
        )

        await (
            interaction.response
            .edit_message(
                content=self.status_text(),
                view=self,
            )
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
            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Please choose: "
                        + ", ".join(
                            missing
                        )
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        await (
            interaction.response
            .send_modal(
                MoreProfileDetailsModal(
                    bot=self.bot,
                    guild_id=(
                        self.guild_id
                    ),
                    user_id=(
                        self.user_id
                    ),
                    data=self.data,
                )
            )
        )


# ==================================================
# STEP 3 - EXTRA DETAILS
# ==================================================

class MoreProfileDetailsModal(
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
            title="Profile Details"
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.data = data

        self.custom_gender = (
            discord.ui.TextInput(
                label="Custom gender",
                placeholder=(
                    "Only fill this if you chose Other"
                ),
                required=False,
                max_length=80,
            )
        )

        self.likes = (
            discord.ui.TextInput(
                label="Likes",
                placeholder=(
                    "Things you enjoy"
                ),
                required=False,
                style=(
                    discord.TextStyle
                    .paragraph
                ),
                max_length=500,
                default=(
                    data.get("likes")
                    or ""
                ),
            )
        )

        self.dislikes = (
            discord.ui.TextInput(
                label="Dislikes",
                placeholder=(
                    "Things you dislike"
                ),
                required=False,
                style=(
                    discord.TextStyle
                    .paragraph
                ),
                max_length=500,
                default=(
                    data.get("dislikes")
                    or ""
                ),
            )
        )

        self.dni = (
            discord.ui.TextInput(
                label="DNI if...",
                placeholder=(
                    "Who should not interact with you?"
                ),
                required=False,
                style=(
                    discord.TextStyle
                    .paragraph
                ),
                max_length=500,
                default=(
                    data.get("dni")
                    or ""
                ),
            )
        )

        self.extra = (
            discord.ui.TextInput(
                label="Extra",
                placeholder=(
                    "Anything else you want people to know?"
                ),
                required=False,
                style=(
                    discord.TextStyle
                    .paragraph
                ),
                max_length=700,
                default=(
                    data.get("extra")
                    or ""
                ),
            )
        )

        self.add_item(
            self.custom_gender
        )

        self.add_item(
            self.likes
        )

        self.add_item(
            self.dislikes
        )

        self.add_item(
            self.dni
        )

        self.add_item(
            self.extra
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

        guild, member = (
            await get_guild_and_member(
                self.bot,
                self.guild_id,
                self.user_id,
            )
        )

        if (
            guild is None
            or member is None
        ):
            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I could not find your "
                        "server member account."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        embed = build_profile_embed(
            member,
            self.data,
        )

        view = ProfilePreviewView(
            bot=self.bot,
            guild_id=self.guild_id,
            user_id=self.user_id,
            data=self.data,
        )

        await (
            interaction.response
            .send_message(
                (
                    "🌸 **Profile preview**\n"
                    "Check everything below, "
                    "then press **Save Profile**."
                ),
                embed=embed,
                view=view,
                ephemeral=(
                    private_response(
                        interaction
                    )
                ),
            )
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
            await (
                interaction.response
                .send_message(
                    (
                        "❌ This profile preview "
                        "is not for you."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

            return False

        return True

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
        await (
            interaction.response
            .defer(
                thinking=True,
                ephemeral=(
                    private_response(
                        interaction
                    )
                ),
            )
        )

        guild, member = (
            await get_guild_and_member(
                self.bot,
                self.guild_id,
                self.user_id,
            )
        )

        if (
            guild is None
            or member is None
        ):
            return await (
                interaction.followup
                .send(
                    (
                        "❌ I could not find your "
                        "server member account."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        # --------------------------------------------------
        # SERVER SETTINGS
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

            return await (
                interaction.followup
                .send(
                    (
                        "❌ I could not load "
                        "the server profile settings."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        # --------------------------------------------------
        # OLD PROFILE
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

        old_message_id = (
            old_profile.get(
                "intro_message_id"
            )
            if old_profile
            else None
        )

        nickname = (
            self.data.get(
                "nickname"
            )
        )

        # --------------------------------------------------
        # SAVE PROFILE
        # --------------------------------------------------

        try:
            await (
                self.bot.db
                .save_member_profile(
                    guild_id=guild.id,
                    user_id=member.id,
                    nickname=nickname,
                    age=self.data.get(
                        "age"
                    ),
                    gender=self.data.get(
                        "gender"
                    ),
                    pronouns=self.data.get(
                        "pronouns"
                    ),
                    sexuality=self.data.get(
                        "sexuality"
                    ),
                    languages=self.data.get(
                        "languages"
                    ),
                    relationship_status=(
                        self.data.get(
                            "relationship_status"
                        )
                    ),
                    likes=self.data.get(
                        "likes"
                    ),
                    dislikes=self.data.get(
                        "dislikes"
                    ),
                    dni=self.data.get(
                        "dni"
                    ),
                    dm_status=self.data.get(
                        "dm_status"
                    ),
                    extra=self.data.get(
                        "extra"
                    ),
                    intro_message_id=(
                        old_message_id
                    ),
                    profile_complete=True,
                )
            )

        except Exception:
            traceback.print_exc()

            return await (
                interaction.followup
                .send(
                    (
                        "❌ I could not save "
                        "your profile."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        # --------------------------------------------------
        # APPLY SERVER NICKNAME
        # --------------------------------------------------

        nickname_changed = True

        try:
            await member.edit(
                nick=nickname,
                reason=(
                    "Member profile nickname"
                ),
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
        # UPDATE EXISTING PROFILE POST
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
            # CREATE NEW PROFILE POST
            # --------------------------------------------------

            if not intro_updated:

                try:
                    new_message = (
                        await intro_channel
                        .send(
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

        result = (
            "✅ **Your profile has been saved!**"
        )

        if intro_updated:
            result += (
                "\n🌸 Your profile has been "
                "posted or updated in the "
                "intros channel."
            )

        else:
            result += (
                "\n⚠️ Your profile was saved, "
                "but I could not post it in "
                "the intros channel."
            )

        if nickname_changed:
            result += (
                f"\n🏷️ Your server nickname "
                f"is now **{nickname}**."
            )

        else:
            result += (
                "\n⚠️ Your preferred name was "
                "saved, but I could not change "
                "your server nickname."
            )

        await (
            interaction.followup
            .send(
                result,
                ephemeral=(
                    private_response(
                        interaction
                    )
                ),
            )
        )

        self.stop()

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

        await (
            interaction.response
            .edit_message(
                content=(
                    "❌ Profile setup cancelled. "
                    "Nothing was saved."
                ),
                embed=None,
                view=self,
            )
        )

        self.stop()


# ==================================================
# DM CREATE PROFILE BUTTON
# ==================================================

class CreateProfileDMView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
    ):
        # Button remains active for 24 hours.
        # /profile setup is always available
        # as the backup.
        super().__init__(
            timeout=86400
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        if (
            interaction.user.id
            != self.user_id
        ):
            await (
                interaction.response
                .send_message(
                    (
                        "❌ This profile setup "
                        "button is not for you."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

            return False

        return True

    @discord.ui.button(
        label="Create My Profile",
        style=discord.ButtonStyle.primary,
        emoji="🌸",
    )
    async def create_profile(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild, member = (
            await get_guild_and_member(
                self.bot,
                self.guild_id,
                self.user_id,
            )
        )

        if (
            guild is None
            or member is None
        ):
            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I could not find you "
                        "in that server.\n"
                        "Please use `/profile setup` "
                        "inside the server."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        # --------------------------------------------------
        # CHECK SETTINGS / VERIFIED ROLE
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

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I could not load the "
                        "server profile settings.\n"
                        "Please use `/profile setup` "
                        "inside the server."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        verified_role_id = (
            settings.get(
                "verified_role"
            )
            if settings
            else None
        )

        if verified_role_id:

            verified_role = (
                guild.get_role(
                    verified_role_id
                )
            )

            if (
                verified_role
                and verified_role
                not in member.roles
            ):
                return await (
                    interaction.response
                    .send_message(
                        (
                            "❌ You no longer have "
                            "the configured "
                            "verified role."
                        ),
                        ephemeral=(
                            private_response(
                                interaction
                            )
                        ),
                    )
                )

        # --------------------------------------------------
        # EXISTING PROFILE
        # --------------------------------------------------

        try:
            existing = (
                await self.bot.db
                .get_member_profile(
                    guild.id,
                    member.id,
                )
            )

        except Exception:
            existing = None

        if (
            existing
            and existing.get(
                "profile_complete"
            )
        ):
            return await (
                interaction.response
                .send_message(
                    (
                        "🌸 You already have "
                        "a saved profile.\n"
                        "Use `/profile edit` "
                        "inside the server if "
                        "you want to change it."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        # --------------------------------------------------
        # OPEN PROFILE FORM FROM THE DM
        # --------------------------------------------------

        await (
            interaction.response
            .send_modal(
                BasicProfileModal(
                    bot=self.bot,
                    guild_id=guild.id,
                    user_id=member.id,
                    existing=existing,
                )
            )
        )


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
    # AUTOMATIC VERIFIED ROLE DETECTION
    #
    # This works whether the role was:
    #
    # - Added manually
    # - Added with /addrole
    # - Added by another bot
    #
    # As long as the member newly receives
    # the configured ID Verified role.
    # ==================================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ):
        if after.bot:
            return

        before_role_ids = {
            role.id
            for role
            in before.roles
        }

        after_role_ids = {
            role.id
            for role
            in after.roles
        }

        added_role_ids = (
            after_role_ids
            - before_role_ids
        )

        # Nothing was added.
        if not added_role_ids:
            return

        # --------------------------------------------------
        # LOAD PROFILE CONFIGURATION
        # --------------------------------------------------

        try:
            settings = (
                await self.bot.db
                .get_guild_settings(
                    after.guild.id
                )
            )

        except Exception:
            traceback.print_exc()
            return

        if not settings:
            return

        verified_role_id = (
            settings.get(
                "verified_role"
            )
        )

        if not verified_role_id:
            return

        # The role that changed wasn't the
        # configured ID Verified role.
        if (
            verified_role_id
            not in added_role_ids
        ):
            return

        # --------------------------------------------------
        # DON'T DM SOMEONE WHO ALREADY
        # COMPLETED THEIR PROFILE
        # --------------------------------------------------

        try:
            existing = (
                await self.bot.db
                .get_member_profile(
                    after.guild.id,
                    after.id,
                )
            )

        except Exception:
            existing = None

        if (
            existing
            and existing.get(
                "profile_complete"
            )
        ):
            return

        # --------------------------------------------------
        # CREATE DM BUTTON
        # --------------------------------------------------

        view = CreateProfileDMView(
            bot=self.bot,
            guild_id=after.guild.id,
            user_id=after.id,
        )

        embed = discord.Embed(
            title=(
                "🌸 You're verified!"
            ),
            description=(
                f"You've received the verified role "
                f"in **{after.guild.name}**.\n\n"

                "Press **Create My Profile** below "
                "to set up your member profile.\n\n"

                "Your chosen name will be saved and "
                "used by the bot for things like "
                "your relationship tree.\n\n"

                "If the button doesn't work, "
                "use `/profile setup` in the server."
            ),
        )

        # --------------------------------------------------
        # SEND DM
        # --------------------------------------------------

        try:
            await after.send(
                embed=embed,
                view=view,
            )

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            # Their DMs are probably closed.
            #
            # That's okay:
            # /profile setup still works
            # inside the server.
            pass

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
            await (
                self.bot.db
                .upsert_guild_settings(
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

        await (
            interaction.response
            .send_message(
                (
                    "✅ **Profile system configured!**\n\n"

                    f"**Verified role:** "
                    f"{verified_role.mention}\n"

                    f"**Intros channel:** "
                    f"{intro_channel.mention}"
                ),
                ephemeral=True,
            )
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
        guild = interaction.guild

        if guild is None:
            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Use this command "
                        "inside the server."
                    )
                )
            )

        # --------------------------------------------------
        # LOAD SETTINGS
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
                guild.get_role(
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
        # EXISTING PROFILE
        # --------------------------------------------------

        try:
            existing = (
                await self.bot.db
                .get_member_profile(
                    guild.id,
                    interaction.user.id,
                )
            )

        except Exception:
            existing = None

        # --------------------------------------------------
        # OPEN FORM
        # --------------------------------------------------

        await (
            interaction.response
            .send_modal(
                BasicProfileModal(
                    bot=self.bot,
                    guild_id=guild.id,
                    user_id=(
                        interaction.user.id
                    ),
                    existing=existing,
                )
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
        guild = interaction.guild

        if guild is None:
            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Use this command "
                        "inside the server."
                    )
                )
            )

        try:
            existing = (
                await self.bot.db
                .get_member_profile(
                    guild.id,
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

        await (
            interaction.response
            .send_modal(
                BasicProfileModal(
                    bot=self.bot,
                    guild_id=guild.id,
                    user_id=(
                        interaction.user.id
                    ),
                    existing=existing,
                )
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
        guild = interaction.guild

        if guild is None:
            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Use this command "
                        "inside the server."
                    )
                )
            )

        target = (
            user
            or interaction.user
        )

        try:
            profile = (
                await self.bot.db
                .get_member_profile(
                    guild.id,
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

        await (
            interaction.response
            .send_message(
                embed=(
                    build_profile_embed(
                        target,
                        profile,
                    )
                ),
                ephemeral=True,
            )
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
