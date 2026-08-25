import traceback
import discord

from discord.ext import commands
from discord import app_commands


# ==================================================
# PROFILE ROLE NAMES
# ==================================================

GENDER_ROLES = [
    "Male",
    "Female",
    "Nonbinary",
    "Genderfluid",
    "Genderless",
    "Questioning",
    "Other gender",
]

PRONOUN_ROLES = [
    "Any pronouns",
    "She/Her",
    "He/Him",
    "They/Them",
    "It/Its",
    "Please ask for my pronouns",
    "Other pronouns",
]

AGE_ROLES = [
    "18-21",
    "22-25",
    "26-30",
    "31+",
]

RELATIONSHIP_STATUS_ROLES = [
    "Single",
    "Taken",
    "Complicated",
]

RELATIONSHIP_STYLE_ROLES = [
    "monogamous",
    "Polyamorous",
]

DM_STATUS_ROLES = [
    "DMs Open",
    "Ask to DM",
    "DMs Closed",
]


# ==================================================
# HELPERS
# ==================================================

def clean_value(value):

    if value is None:
        return "Not set"

    value = str(value).strip()

    return value or "Not set"


def private_response(
    interaction: discord.Interaction,
):

    return interaction.guild is not None


def get_role_by_name(
    guild: discord.Guild,
    role_name: str,
):

    return discord.utils.get(
        guild.roles,
        name=role_name,
    )


def member_role_names(
    member: discord.Member,
):

    return {
        role.name
        for role in member.roles
    }


def get_age_role(
    age_value,
):

    try:
        age = int(
            str(age_value).strip()
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if 18 <= age <= 21:
        return "18-21"

    if 22 <= age <= 25:
        return "22-25"

    if 26 <= age <= 30:
        return "26-30"

    if age >= 31:
        return "31+"

    return None


def normalise_profile_data(
    profile: dict | None,
    member: discord.Member | None = None,
):

    data = dict(
        profile or {}
    )

    # --------------------------------------------------
    # OLD GENDER VALUES
    # --------------------------------------------------

    old_gender_map = {
        "Woman": "Female",
        "Man": "Male",
        "Non-binary": "Nonbinary",
        "Agender": "Genderless",
        "Other": "Other gender",
    }

    old_gender = data.get(
        "gender"
    )

    if old_gender in old_gender_map:

        data["gender"] = (
            old_gender_map[
                old_gender
            ]
        )

    # --------------------------------------------------
    # OLD RELATIONSHIP VALUES
    # --------------------------------------------------

    old_relationship_map = {
        "It's complicated":
            "Complicated",

        "Married":
            "Taken",
    }

    old_relationship = (
        data.get(
            "relationship_status"
        )
    )

    if (
        old_relationship
        in old_relationship_map
    ):

        data[
            "relationship_status"
        ] = old_relationship_map[
            old_relationship
        ]

    # --------------------------------------------------
    # OLD DM VALUES
    # --------------------------------------------------

    old_dm_map = {
        "🟢 DMs Open":
            "DMs Open",

        "🟡 Ask First":
            "Ask to DM",

        "🔴 DMs Closed":
            "DMs Closed",
    }

    old_dm = data.get(
        "dm_status"
    )

    if old_dm in old_dm_map:

        data["dm_status"] = (
            old_dm_map[
                old_dm
            ]
        )

    # --------------------------------------------------
    # USE CURRENT DISCORD ROLES AS DEFAULTS
    # --------------------------------------------------

    if member:

        current_roles = (
            member_role_names(
                member
            )
        )

        # Gender

        current_gender = [
            role
            for role
            in GENDER_ROLES
            if role in current_roles
        ]

        if current_gender:

            data["gender"] = (
                current_gender[0]
            )

        # Pronouns

        current_pronouns = [
            role
            for role
            in PRONOUN_ROLES
            if role in current_roles
        ]

        if current_pronouns:

            data["pronouns"] = (
                ", ".join(
                    current_pronouns
                )
            )

        # Relationship status

        current_status = [
            role
            for role
            in RELATIONSHIP_STATUS_ROLES
            if role in current_roles
        ]

        if current_status:

            data[
                "relationship_status"
            ] = current_status[0]

        # Relationship style

        current_style = [
            role
            for role
            in RELATIONSHIP_STYLE_ROLES
            if role in current_roles
        ]

        if current_style:

            data[
                "relationship_style"
            ] = current_style[0]

        # DM status

        current_dm = [
            role
            for role
            in DM_STATUS_ROLES
            if role in current_roles
        ]

        if current_dm:

            data[
                "dm_status"
            ] = current_dm[0]

    return data


async def get_guild_and_member(
    bot,
    guild_id: int,
    user_id: int,
):

    guild = bot.get_guild(
        guild_id
    )

    if guild is None:
        return None, None

    member = guild.get_member(
        user_id
    )

    if member is None:

        try:

            member = (
                await guild.fetch_member(
                    user_id
                )
            )

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):

            member = None

    return guild, member


# ==================================================
# ROLE MANAGEMENT
# ==================================================

async def replace_role_group(
    member: discord.Member,
    all_role_names: list[str],
    wanted_role_names: list[str],
):

    guild = member.guild

    wanted_role_names = [
        role_name
        for role_name
        in wanted_role_names
        if role_name
    ]

    current_group_roles = [
        role
        for role in member.roles
        if role.name
        in all_role_names
    ]

    roles_to_remove = [
        role
        for role
        in current_group_roles
        if (
            role.name
            not in wanted_role_names
            and not role.managed
        )
    ]

    roles_to_add = []

    missing_roles = []

    current_names = {
        role.name
        for role in member.roles
    }

    for role_name in wanted_role_names:

        if role_name in current_names:
            continue

        role = get_role_by_name(
            guild,
            role_name,
        )

        if role is None:

            missing_roles.append(
                role_name
            )

            continue

        if role.managed:

            missing_roles.append(
                role_name
            )

            continue

        roles_to_add.append(
            role
        )

    if roles_to_remove:

        await member.remove_roles(
            *roles_to_remove,
            reason=(
                "Profile role update"
            ),
        )

    if roles_to_add:

        await member.add_roles(
            *roles_to_add,
            reason=(
                "Profile role update"
            ),
        )

    return missing_roles


async def sync_profile_roles(
    member: discord.Member,
    data: dict,
):

    missing_roles = []

    failed_groups = []

    # --------------------------------------------------
    # AGE
    # --------------------------------------------------

    age_role = get_age_role(
        data.get("age")
    )

    try:

        missing_roles.extend(
            await replace_role_group(
                member,
                AGE_ROLES,
                (
                    [age_role]
                    if age_role
                    else []
                ),
            )
        )

    except (
        discord.Forbidden,
        discord.HTTPException,
    ):

        failed_groups.append(
            "Age"
        )

    # --------------------------------------------------
    # GENDER
    # --------------------------------------------------

    gender = data.get(
        "gender"
    )

    try:

        missing_roles.extend(
            await replace_role_group(
                member,
                GENDER_ROLES,
                (
                    [gender]
                    if gender
                    in GENDER_ROLES
                    else []
                ),
            )
        )

    except (
        discord.Forbidden,
        discord.HTTPException,
    ):

        failed_groups.append(
            "Gender"
        )

    # --------------------------------------------------
    # PRONOUNS
    # --------------------------------------------------

    pronoun_text = str(
        data.get(
            "pronouns"
        )
        or ""
    )

    selected_pronouns = [
        role_name
        for role_name
        in PRONOUN_ROLES
        if role_name
        in [
            item.strip()
            for item
            in pronoun_text.split(",")
        ]
    ]

    try:

        missing_roles.extend(
            await replace_role_group(
                member,
                PRONOUN_ROLES,
                selected_pronouns,
            )
        )

    except (
        discord.Forbidden,
        discord.HTTPException,
    ):

        failed_groups.append(
            "Pronouns"
        )

    # --------------------------------------------------
    # RELATIONSHIP STATUS
    # --------------------------------------------------

    relationship_status = (
        data.get(
            "relationship_status"
        )
    )

    try:

        missing_roles.extend(
            await replace_role_group(
                member,
                RELATIONSHIP_STATUS_ROLES,
                (
                    [
                        relationship_status
                    ]
                    if relationship_status
                    in RELATIONSHIP_STATUS_ROLES
                    else []
                ),
            )
        )

    except (
        discord.Forbidden,
        discord.HTTPException,
    ):

        failed_groups.append(
            "Relationship Status"
        )

    # --------------------------------------------------
    # RELATIONSHIP STYLE
    # --------------------------------------------------

    relationship_style = (
        data.get(
            "relationship_style"
        )
    )

    try:

        missing_roles.extend(
            await replace_role_group(
                member,
                RELATIONSHIP_STYLE_ROLES,
                (
                    [
                        relationship_style
                    ]
                    if relationship_style
                    in RELATIONSHIP_STYLE_ROLES
                    else []
                ),
            )
        )

    except (
        discord.Forbidden,
        discord.HTTPException,
    ):

        failed_groups.append(
            "Relationship Style"
        )

    # --------------------------------------------------
    # DM STATUS
    # --------------------------------------------------

    dm_status = data.get(
        "dm_status"
    )

    try:

        missing_roles.extend(
            await replace_role_group(
                member,
                DM_STATUS_ROLES,
                (
                    [dm_status]
                    if dm_status
                    in DM_STATUS_ROLES
                    else []
                ),
            )
        )

    except (
        discord.Forbidden,
        discord.HTTPException,
    ):

        failed_groups.append(
            "DM Status"
        )

    return {
        "missing_roles":
            list(
                dict.fromkeys(
                    missing_roles
                )
            ),

        "failed_groups":
            failed_groups,
    }


# ==================================================
# PROFILE EMBED
# ==================================================

def build_profile_embed(
    member: discord.Member,
    profile: dict,
):

    nickname = clean_value(
        profile.get(
            "nickname"
        )
    )

    embed = discord.Embed(
        title=(
            f"+:ꔫ:﹤{nickname}﹥:ꔫ:+ﾟ"
        ),
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

            f"⋆ ˚｡⋆୨୧˚ **Relationship Style:** "
            f"{clean_value(profile.get('relationship_style'))}\n\n"

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
        name=(
            f"Profile for {nickname}"
        ),
        icon_url=(
            member.display_avatar.url
        ),
    )

    embed.set_thumbnail(
        url=(
            member.display_avatar.url
        )
    )

    embed.set_footer(
        text="Member profile"
    )

    return embed


# ==================================================
# STEP 1 - BASIC DETAILS
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
        self.existing = (
            existing or {}
        )

        self.nickname = (
            discord.ui.TextInput(
                label=(
                    "Name / nickname"
                ),
                placeholder=(
                    "What would you like us to call you?"
                ),
                required=True,
                max_length=32,
                default=(
                    self.existing.get(
                        "nickname"
                    )
                    or ""
                ),
            )
        )

        self.age = (
            discord.ui.TextInput(
                label="Age",
                placeholder=(
                    "Your age"
                ),
                required=True,
                max_length=3,
                default=(
                    self.existing.get(
                        "age"
                    )
                    or ""
                ),
            )
        )

        self.sexuality = (
            discord.ui.TextInput(
                label="Sexuality",
                placeholder=(
                    "Optional"
                ),
                required=False,
                max_length=80,
                default=(
                    self.existing.get(
                        "sexuality"
                    )
                    or ""
                ),
            )
        )

        self.languages = (
            discord.ui.TextInput(
                label="Language(s)",
                placeholder=(
                    "Example: English, Spanish"
                ),
                required=False,
                max_length=100,
                default=(
                    self.existing.get(
                        "languages"
                    )
                    or ""
                ),
            )
        )

        self.add_item(
            self.nickname
        )

        self.add_item(
            self.age
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

        age_text = str(
            self.age.value
        ).strip()

        try:

            age_number = int(
                age_text
            )

        except ValueError:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Please enter your "
                        "age as a number."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        if (
            age_number < 18
            or age_number > 120
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Please enter a "
                        "valid age of 18 or older."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

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
                    age_text,

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

        view = (
            IdentityChoicesView(
                bot=self.bot,
                guild_id=self.guild_id,
                user_id=self.user_id,
                data=data,
            )
        )

        await (
            interaction.response
            .send_message(
                view.status_text(),
                view=view,
                ephemeral=(
                    private_response(
                        interaction
                    )
                ),
            )
        )


# ==================================================
# STEP 2 - IDENTITY
# ==================================================

class IdentityChoicesView(
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
                row=0,
                options=[
                    discord.SelectOption(
                        label="Male",
                        value="Male",
                    ),

                    discord.SelectOption(
                        label="Female",
                        value="Female",
                    ),

                    discord.SelectOption(
                        label="Nonbinary",
                        value="Nonbinary",
                    ),

                    discord.SelectOption(
                        label="Genderfluid",
                        value="Genderfluid",
                    ),

                    discord.SelectOption(
                        label="Genderless",
                        value="Genderless",
                    ),

                    discord.SelectOption(
                        label="Questioning",
                        value="Questioning",
                    ),

                    discord.SelectOption(
                        label="Other gender",
                        value="Other gender",
                    ),
                ],
            )
        )

        # --------------------------------------------------
        # PRONOUNS
        # --------------------------------------------------

        self.pronoun_select = (
            discord.ui.Select(
                placeholder=(
                    "Choose your pronouns"
                ),
                min_values=1,
                max_values=3,
                row=1,
                options=[
                    discord.SelectOption(
                        label="Any pronouns",
                        value="Any pronouns",
                    ),

                    discord.SelectOption(
                        label="She/Her",
                        value="She/Her",
                    ),

                    discord.SelectOption(
                        label="He/Him",
                        value="He/Him",
                    ),

                    discord.SelectOption(
                        label="They/Them",
                        value="They/Them",
                    ),

                    discord.SelectOption(
                        label="It/Its",
                        value="It/Its",
                    ),

                    discord.SelectOption(
                        label=(
                            "Please ask for my pronouns"
                        ),
                        value=(
                            "Please ask for my pronouns"
                        ),
                    ),

                    discord.SelectOption(
                        label="Other pronouns",
                        value="Other pronouns",
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
                row=2,
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
                        label="Complicated",
                        value="Complicated",
                    ),
                ],
            )
        )

        self.gender_select.callback = (
            self.gender_callback
        )

        self.pronoun_select.callback = (
            self.pronoun_callback
        )

        self.relationship_select.callback = (
            self.relationship_callback
        )

        self.add_item(
            self.gender_select
        )

        self.add_item(
            self.pronoun_select
        )

        self.add_item(
            self.relationship_select
        )

    def status_text(
        self,
    ):

        return (
            "🌸 **Profile setup — identity**\n\n"

            f"**Gender:** "
            f"{clean_value(self.data.get('gender'))}\n"

            f"**Pronouns:** "
            f"{clean_value(self.data.get('pronouns'))}\n"

            f"**Relationship Status:** "
            f"{clean_value(self.data.get('relationship_status'))}\n\n"

            "Choose your options, "
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
            self.gender_select
            .values[0]
        )

        await (
            interaction.response
            .edit_message(
                content=self.status_text(),
                view=self,
            )
        )

    async def pronoun_callback(
        self,
        interaction: discord.Interaction,
    ):

        self.data["pronouns"] = (
            ", ".join(
                self.pronoun_select
                .values
            )
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

    @discord.ui.button(
        label="Next",
        style=(
            discord.ButtonStyle.primary
        ),
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
            "pronouns"
        ):

            missing.append(
                "Pronouns"
            )

        if not self.data.get(
            "relationship_status"
        ):

            missing.append(
                "Relationship Status"
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

        view = (
            SocialChoicesView(
                bot=self.bot,
                guild_id=self.guild_id,
                user_id=self.user_id,
                data=self.data,
            )
        )

        await (
            interaction.response
            .edit_message(
                content=(
                    view.status_text()
                ),
                view=view,
            )
        )


# ==================================================
# STEP 3 - SOCIAL SETTINGS
# ==================================================

class SocialChoicesView(
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
        # RELATIONSHIP STYLE
        # --------------------------------------------------

        self.style_select = (
            discord.ui.Select(
                placeholder=(
                    "Choose relationship style"
                ),
                row=0,
                options=[
                    discord.SelectOption(
                        label="Monogamous",
                        value="monogamous",
                    ),

                    discord.SelectOption(
                        label="Polyamorous",
                        value="Polyamorous",
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
                row=1,
                options=[
                    discord.SelectOption(
                        label="DMs Open",
                        value="DMs Open",
                    ),

                    discord.SelectOption(
                        label="Ask to DM",
                        value="Ask to DM",
                    ),

                    discord.SelectOption(
                        label="DMs Closed",
                        value="DMs Closed",
                    ),
                ],
            )
        )

        self.style_select.callback = (
            self.style_callback
        )

        self.dm_select.callback = (
            self.dm_callback
        )

        self.add_item(
            self.style_select
        )

        self.add_item(
            self.dm_select
        )

    def status_text(
        self,
    ):

        return (
            "🌸 **Profile setup — social settings**\n\n"

            f"**Relationship Style:** "
            f"{clean_value(self.data.get('relationship_style'))}\n"

            f"**DM Status:** "
            f"{clean_value(self.data.get('dm_status'))}\n\n"

            "Choose both options, "
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

    async def style_callback(
        self,
        interaction: discord.Interaction,
    ):

        self.data[
            "relationship_style"
        ] = (
            self.style_select
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
        style=(
            discord.ButtonStyle.primary
        ),
        emoji="➡️",
        row=2,
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        missing = []

        if not self.data.get(
            "relationship_style"
        ):

            missing.append(
                "Relationship Style"
            )

        if not self.data.get(
            "dm_status"
        ):

            missing.append(
                "DM Status"
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
# STEP 4 - MORE DETAILS
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
                    "Anything else people should know?"
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
                        "❌ I could not find "
                        "your server account."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        embed = (
            build_profile_embed(
                member,
                self.data,
            )
        )

        view = (
            ProfilePreviewView(
                bot=self.bot,
                guild_id=self.guild_id,
                user_id=self.user_id,
                data=self.data,
            )
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
# STEP 5 - PREVIEW / SAVE
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
        style=(
            discord.ButtonStyle.success
        ),
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
                        "❌ I could not find "
                        "your server account."
                    ),
                    ephemeral=(
                        private_response(
                            interaction
                        )
                    ),
                )
            )

        # --------------------------------------------------
        # SETTINGS
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
        # SAVE DATABASE PROFILE
        #
        # relationship_style is currently represented by
        # the Discord role itself.
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
        # APPLY PROFILE ROLES
        # --------------------------------------------------

        role_result = {
            "missing_roles": [],
            "failed_groups": [],
        }

        try:

            role_result = (
                await sync_profile_roles(
                    member,
                    self.data,
                )
            )

        except Exception:

            traceback.print_exc()

            role_result[
                "failed_groups"
            ] = [
                "Profile roles"
            ]

        # --------------------------------------------------
        # SERVER NICKNAME
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
        # UPDATE EXISTING PROFILE
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
            # CREATE NEW PROFILE
            # --------------------------------------------------

            if not intro_updated:

                try:

                    new_message = (
                        await intro_channel
                        .send(
                            embed=(
                                profile_embed
                            )
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
                "\n🌸 Your member profile "
                "has been posted/updated."
            )

        else:

            result += (
                "\n⚠️ Your profile was saved, "
                "but I couldn't update the "
                "profile channel."
            )

        if nickname_changed:

            result += (
                f"\n🏷️ Your server nickname "
                f"is now **{nickname}**."
            )

        else:

            result += (
                "\n⚠️ I couldn't change "
                "your server nickname."
            )

        if not (
            role_result[
                "missing_roles"
            ]
            or role_result[
                "failed_groups"
            ]
        ):

            result += (
                "\n🎭 Your profile roles "
                "have been updated."
            )

        else:

            result += (
                "\n⚠️ Your profile saved, "
                "but some roles could not "
                "be updated."
            )

            if role_result[
                "missing_roles"
            ]:

                result += (
                    "\nMissing roles: `"
                    + "`, `".join(
                        role_result[
                            "missing_roles"
                        ]
                    )
                    + "`"
                )

            if role_result[
                "failed_groups"
            ]:

                result += (
                    "\nCheck my **Manage Roles** "
                    "permission and role position."
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
        style=(
            discord.ButtonStyle.danger
        ),
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
# VERIFIED DM BUTTON
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

            return False

        return True

    @discord.ui.button(
        label="Create My Profile",
        style=(
            discord.ButtonStyle.primary
        ),
        emoji="🌸",
        custom_id=(
            "create_member_profile"
        ),
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
                        "❌ I couldn't find "
                        "your server account. "
                        "Use `/profile setup` "
                        "inside the server."
                    )
                )
            )

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

        existing = (
            normalise_profile_data(
                existing,
                member,
            )
        )

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
    # VERIFIED ROLE DETECTION
    # ==================================================

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ):

        if after.bot:
            return

        before_roles = {
            role.id
            for role
            in before.roles
        }

        after_roles = {
            role.id
            for role
            in after.roles
        }

        added_roles = (
            after_roles
            - before_roles
        )

        if not added_roles:
            return

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

        if (
            not verified_role_id
            or verified_role_id
            not in added_roles
        ):

            return

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

        view = (
            CreateProfileDMView(
                bot=self.bot,
                guild_id=(
                    after.guild.id
                ),
                user_id=(
                    after.id
                ),
            )
        )

        embed = discord.Embed(
            title=(
                "🌸 You're verified!"
            ),
            description=(
                f"You've been verified in "
                f"**{after.guild.name}**!\n\n"

                "Press **Create My Profile** "
                "below to create your member "
                "profile and choose your roles.\n\n"

                "If you can't use the button, "
                "use `/profile setup` "
                "inside the server."
            ),
        )

        try:

            await after.send(
                embed=embed,
                view=view,
            )

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):

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
                        "**Manage Server**."
                    ),
                    ephemeral=True,
                )
            )

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

        await (
            interaction.response
            .send_message(
                (
                    "✅ **Profile system configured!**\n\n"

                    f"**Verified Role:** "
                    f"{verified_role.mention}\n"

                    f"**Profile Channel:** "
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
            return

        settings = (
            await self.bot.db
            .get_guild_settings(
                guild.id
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
                        "⚠️ An admin needs "
                        "to run `/profile configure` first."
                    ),
                    ephemeral=True,
                )
            )

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
                            "❌ You need the "
                            "verified role first."
                        ),
                        ephemeral=True,
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

            existing = None

        existing = (
            normalise_profile_data(
                existing,
                interaction.user,
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

            existing = None

        if not existing:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You don't have "
                        "a profile yet. "
                        "Use `/profile setup`."
                    ),
                    ephemeral=True,
                )
            )

        existing = (
            normalise_profile_data(
                existing,
                interaction.user,
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

            profile = None

        if not profile:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ That member hasn't "
                        "created a profile yet."
                    ),
                    ephemeral=True,
                )
            )

        profile = (
            normalise_profile_data(
                profile,
                target,
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
