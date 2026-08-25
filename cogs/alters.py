import traceback
import discord

from discord.ext import commands
from discord import app_commands

from database.system_profiles import (
    get_system_profile,
    get_system_profile_by_id,
    get_system_profile_settings,
    add_alter_profile,
    get_alter_profile,
    get_alter_profiles,
    update_alter_field,
    delete_alter_profile,
)

from cogs.system_profiles import (
    build_system_profile_embed,
)


# ==================================================
# HELPERS
# ==================================================

def clean_value(value):

    if value is None:
        return "Not set"

    value = str(value).strip()

    return value or "Not set"


def safe_text(
    value,
    limit=1000,
):

    value = clean_value(
        value
    )

    if len(value) > limit:

        return (
            value[:limit - 3]
            + "..."
        )

    return value


async def alter_belongs_to_user(
    guild_id: int,
    user_id: int,
    alter_id: int,
):

    profile = await get_system_profile(
        guild_id,
        user_id,
    )

    if not profile:
        return None, None

    alter = await get_alter_profile(
        alter_id
    )

    if not alter:
        return profile, None

    if (
        alter["system_profile_id"]
        != profile["id"]
    ):

        return profile, None

    return profile, alter


# ==================================================
# ALTER PROFILE EMBED
# ==================================================

def build_alter_embed(
    alter: dict,
    page: int | None = None,
    total: int | None = None,
):

    name = clean_value(
        alter.get("name")
    )

    proxy = (
        alter.get("proxy_emoji")
        or "🌸"
    )

    embed = discord.Embed(
        title=f"{proxy} {name}",
        description="✨ **ALTER PROFILE** ✨",
        colour=discord.Colour.blurple(),
    )

    embed.add_field(
        name="🌷 Nickname(s)",
        value=safe_text(
            alter.get("nicknames")
        ),
        inline=True,
    )

    embed.add_field(
        name="💗 Pronouns",
        value=safe_text(
            alter.get("pronouns")
        ),
        inline=True,
    )

    embed.add_field(
        name="🎂 Age / Age Range",
        value=safe_text(
            alter.get("age")
        ),
        inline=True,
    )

    embed.add_field(
        name="🌈 Gender",
        value=safe_text(
            alter.get("gender")
        ),
        inline=True,
    )

    embed.add_field(
        name="🌙 System Role",
        value=safe_text(
            alter.get("system_role")
        ),
        inline=True,
    )

    embed.add_field(
        name="✨ Species / Identity",
        value=safe_text(
            alter.get(
                "species_identity"
            )
        ),
        inline=True,
    )

    embed.add_field(
        name="📖 Source / Introject Info",
        value=safe_text(
            alter.get(
                "source_info"
            )
        ),
        inline=False,
    )

    embed.add_field(
        name="🎨 Hobbies / Interests",
        value=safe_text(
            alter.get("hobbies")
        ),
        inline=False,
    )

    embed.add_field(
        name="💚 Likes",
        value=safe_text(
            alter.get("likes")
        ),
        inline=False,
    )

    embed.add_field(
        name="💔 Dislikes",
        value=safe_text(
            alter.get("dislikes")
        ),
        inline=False,
    )

    embed.add_field(
        name="💌 DM Status",
        value=safe_text(
            alter.get("dm_status")
        ),
        inline=True,
    )

    embed.add_field(
        name="💬 Interaction Status",
        value=safe_text(
            alter.get(
                "interaction_status"
            )
        ),
        inline=True,
    )

    embed.add_field(
        name="🌸 Frequent Fronter",
        value=(
            "Yes"
            if alter.get(
                "frequent_fronter"
            )
            else "No"
        ),
        inline=True,
    )

    embed.add_field(
        name="🛡️ Boundaries",
        value=safe_text(
            alter.get("boundaries")
        ),
        inline=False,
    )

    embed.add_field(
        name="🚫 DNI",
        value=safe_text(
            alter.get("dni")
        ),
        inline=False,
    )

    embed.add_field(
        name="🧸 About Me",
        value=safe_text(
            alter.get("about_me")
        ),
        inline=False,
    )

    if (
        page is not None
        and total is not None
    ):

        embed.set_footer(
            text=f"Alter {page} of {total}"
        )

    else:

        embed.set_footer(
            text="Alter profile"
        )

    return embed


# ==================================================
# ALTER BROWSER
# ==================================================

class AlterBrowserView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        viewer_id: int,
        system_profile_id: int,
        alters: list[dict],
        current_index: int = 0,
    ):

        super().__init__(
            timeout=600
        )

        self.bot = bot
        self.viewer_id = viewer_id
        self.system_profile_id = (
            system_profile_id
        )
        self.alters = alters
        self.current_index = (
            current_index
        )

        self.update_buttons()

    def current_alter(self):

        return self.alters[
            self.current_index
        ]

    def update_buttons(self):

        total = len(
            self.alters
        )

        self.page_button.label = (
            f"{self.current_index + 1}/{total}"
        )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):

        if (
            interaction.user.id
            != self.viewer_id
        ):

            await interaction.response.send_message(
                (
                    "❌ Open the alter browser "
                    "yourself using "
                    "**Browse Alters**."
                ),
                ephemeral=True,
            )

            return False

        return True

    @discord.ui.button(
        label="Previous",
        emoji="◀️",
        style=discord.ButtonStyle.secondary,
    )
    async def previous_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        self.current_index -= 1

        if self.current_index < 0:

            self.current_index = (
                len(self.alters)
                - 1
            )

        self.update_buttons()

        await interaction.response.edit_message(
            embed=build_alter_embed(
                self.current_alter(),
                self.current_index + 1,
                len(self.alters),
            ),
            view=self,
        )

    @discord.ui.button(
        label="1/1",
        style=discord.ButtonStyle.primary,
        disabled=True,
    )
    async def page_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        pass

    @discord.ui.button(
        label="Next",
        emoji="▶️",
        style=discord.ButtonStyle.secondary,
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        self.current_index += 1

        if (
            self.current_index
            >= len(self.alters)
        ):

            self.current_index = 0

        self.update_buttons()

        await interaction.response.edit_message(
            embed=build_alter_embed(
                self.current_alter(),
                self.current_index + 1,
                len(self.alters),
            ),
            view=self,
        )

    @discord.ui.button(
        label="System Profile",
        emoji="🌸",
        style=discord.ButtonStyle.success,
        row=1,
    )
    async def system_profile_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        try:

            profile = (
                await get_system_profile_by_id(
                    self.system_profile_id
                )
            )

        except Exception:

            traceback.print_exc()
            profile = None

        if not profile:

            return await interaction.response.send_message(
                (
                    "❌ I couldn't load "
                    "that System Profile."
                ),
                ephemeral=True,
            )

        guild = interaction.guild

        if guild is None:
            return

        member = guild.get_member(
            profile["user_id"]
        )

        if member is None:

            try:

                member = (
                    await guild.fetch_member(
                        profile["user_id"]
                    )
                )

            except Exception:

                member = None

        if member is None:

            return await interaction.response.send_message(
                (
                    "❌ I couldn't find "
                    "the system owner."
                ),
                ephemeral=True,
            )

        try:

            alters = (
                await get_alter_profiles(
                    self.system_profile_id
                )
            )

        except Exception:

            alters = []

        embed = (
            build_system_profile_embed(
                member,
                profile,
                len(alters),
            )
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self,
        )

    @discord.ui.button(
        label="Close",
        emoji="✖️",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def close_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        self.stop()

        await interaction.response.edit_message(
            content="🌸 Alter browser closed.",
            embed=None,
            view=None,
        )


# ==================================================
# PUBLIC SYSTEM PROFILE BROWSE BUTTON
# ==================================================

class SystemAlterButtonView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        system_profile_id: int,
    ):

        super().__init__(
            timeout=None
        )

        self.bot = bot
        self.system_profile_id = (
            system_profile_id
        )

        button = discord.ui.Button(
            label="Browse Alters",
            emoji="🌸",
            style=discord.ButtonStyle.primary,
            custom_id=(
                f"system_alters:"
                f"{system_profile_id}"
            ),
        )

        button.callback = (
            self.browse_alters
        )

        self.add_item(
            button
        )

    async def browse_alters(
        self,
        interaction: discord.Interaction,
    ):

        try:

            alters = (
                await get_alter_profiles(
                    self.system_profile_id
                )
            )

        except Exception:

            traceback.print_exc()

            return await interaction.response.send_message(
                (
                    "❌ I couldn't load "
                    "the alter profiles."
                ),
                ephemeral=True,
            )

        if not alters:

            return await interaction.response.send_message(
                (
                    "🌸 This system doesn't "
                    "have any alter profiles yet."
                ),
                ephemeral=True,
            )

        browser = AlterBrowserView(
            bot=self.bot,
            viewer_id=interaction.user.id,
            system_profile_id=(
                self.system_profile_id
            ),
            alters=alters,
        )

        await interaction.response.send_message(
            embed=build_alter_embed(
                alters[0],
                1,
                len(alters),
            ),
            view=browser,
            ephemeral=True,
        )


# ==================================================
# REFRESH PUBLIC SYSTEM PROFILE
# ==================================================

async def refresh_system_profile_message(
    bot,
    guild: discord.Guild,
    profile: dict,
):

    try:

        settings = (
            await get_system_profile_settings(
                guild.id
            )
        )

        if not settings:
            return

        channel_id = settings.get(
            "profile_channel_id"
        )

        if not channel_id:
            return

        channel = guild.get_channel(
            channel_id
        )

        if channel is None:
            return

        message_id = profile.get(
            "profile_message_id"
        )

        if not message_id:
            return

        member = guild.get_member(
            profile["user_id"]
        )

        if member is None:

            try:

                member = (
                    await guild.fetch_member(
                        profile["user_id"]
                    )
                )

            except Exception:
                return

        alters = (
            await get_alter_profiles(
                profile["id"]
            )
        )

        message = (
            await channel.fetch_message(
                message_id
            )
        )

        await message.edit(
            embed=(
                build_system_profile_embed(
                    member,
                    profile,
                    len(alters),
                )
            ),
            view=(
                SystemAlterButtonView(
                    bot,
                    profile["id"],
                )
            ),
        )

    except Exception:

        traceback.print_exc()


# ==================================================
# PROXY EMOJI OPTIONS
# ==================================================

COMMON_PROXY_EMOJIS = [
    ("Flower", "🌸"),
    ("Teddy", "🧸"),
    ("Paw", "🐾"),
    ("Moon", "🌙"),
    ("Star", "⭐"),
    ("Sparkles", "✨"),
    ("Pink Heart", "💗"),
    ("Purple Heart", "💜"),
    ("Blue Heart", "💙"),
    ("Green Heart", "💚"),
    ("Red Heart", "❤️"),
    ("Butterfly", "🦋"),
    ("Rose", "🌹"),
    ("Sunflower", "🌻"),
    ("Mushroom", "🍄"),
    ("Strawberry", "🍓"),
    ("Cherry", "🍒"),
    ("Cat", "🐱"),
    ("Fox", "🦊"),
    ("Wolf", "🐺"),
    ("Bunny", "🐰"),
    ("Frog", "🐸"),
    ("Dragon", "🐉"),
    ("Ghost", "👻"),
]


# ==================================================
# ALTER EMOJI SELECTOR
# ==================================================

class AlterEmojiSelectView(
    discord.ui.View
):

    PAGE_SIZE = 24

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        system_profile_id: int,
        data: dict,
        alter_id: int | None = None,
    ):

        super().__init__(
            timeout=600
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id

        self.system_profile_id = (
            system_profile_id
        )

        self.data = data
        self.alter_id = alter_id

        self.page = 0
        self.emoji_items = []

        # --------------------------------------------------
        # NORMAL EMOJIS
        # --------------------------------------------------

        for label, emoji in COMMON_PROXY_EMOJIS:

            self.emoji_items.append(
                {
                    "label": label,
                    "value": (
                        f"unicode:{emoji}"
                    ),
                    "emoji": emoji,
                    "text": emoji,
                }
            )

        # --------------------------------------------------
        # SERVER CUSTOM EMOJIS
        # --------------------------------------------------

        guild = self.bot.get_guild(
            guild_id
        )

        if guild:

            for emoji in guild.emojis:

                self.emoji_items.append(
                    {
                        "label": (
                            emoji.name[:100]
                        ),
                        "value": (
                            f"custom:{emoji.id}"
                        ),
                        "emoji": emoji,
                        "text": str(emoji),
                    }
                )

        self.build_select()

    # ==================================================
    # TOTAL PAGES
    # ==================================================

    def total_pages(self):

        if not self.emoji_items:
            return 1

        return (
            (
                len(self.emoji_items)
                - 1
            )
            // self.PAGE_SIZE
        ) + 1

    # ==================================================
    # BUILD SELECT
    # ==================================================

    def build_select(self):

        # Remove existing dropdown first
        for item in list(
            self.children
        ):

            if isinstance(
                item,
                discord.ui.Select,
            ):

                self.remove_item(
                    item
                )

        start = (
            self.page
            * self.PAGE_SIZE
        )

        end = (
            start
            + self.PAGE_SIZE
        )

        page_items = (
            self.emoji_items[
                start:end
            ]
        )

        options = [
            discord.SelectOption(
                label="No Emoji",
                value="none",
                emoji="🚫",
                description=(
                    "Don't use a proxy emoji"
                ),
            )
        ]

        for item in page_items:

            try:

                options.append(
                    discord.SelectOption(
                        label=(
                            item["label"][:100]
                        ),
                        value=item["value"],
                        emoji=item["emoji"],
                    )
                )

            except Exception:
                continue

        select = discord.ui.Select(
            placeholder=(
                "Choose a proxy emoji"
            ),
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

        select.callback = (
            self.emoji_selected
        )

        self.add_item(
            select
        )

        self.update_buttons()

    # ==================================================
    # BUTTON STATE
    # ==================================================

    def update_buttons(self):

        total = self.total_pages()

        self.page_number.label = (
            f"{self.page + 1}/{total}"
        )

        self.previous_page.disabled = (
            total <= 1
        )

        self.next_page.disabled = (
            total <= 1
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
            != self.user_id
        ):

            await interaction.response.send_message(
                (
                    "❌ This emoji picker "
                    "isn't for you."
                ),
                ephemeral=True,
            )

            return False

        return True

    # ==================================================
    # EMOJI SELECTED
    # ==================================================

    async def emoji_selected(
        self,
        interaction: discord.Interaction,
    ):

        select = next(
            (
                child
                for child
                in self.children

                if isinstance(
                    child,
                    discord.ui.Select,
                )
            ),
            None,
        )

        if select is None:
            return

        selected = (
            select.values[0]
        )

        if selected == "none":

            self.data[
                "proxy_emoji"
            ] = ""

        else:

            found = None

            for item in self.emoji_items:

                if (
                    item["value"]
                    == selected
                ):

                    found = item
                    break

            if found:

                self.data[
                    "proxy_emoji"
                ] = found["text"]

        self.stop()

        await interaction.response.send_modal(
            AlterIdentityModal(
                bot=self.bot,
                guild_id=self.guild_id,
                user_id=self.user_id,
                system_profile_id=(
                    self.system_profile_id
                ),
                data=self.data,
                alter_id=self.alter_id,
            )
        )

    # ==================================================
    # PREVIOUS PAGE
    # ==================================================

    @discord.ui.button(
        label="Previous",
        emoji="◀️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def previous_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        total = self.total_pages()

        self.page -= 1

        if self.page < 0:

            self.page = (
                total - 1
            )

        self.build_select()

        await interaction.response.edit_message(
            content=(
                "🌸 **Choose a Proxy Emoji**\n\n"
                "Choose a normal emoji or "
                "one of the server's custom emojis."
            ),
            view=self,
        )

    # ==================================================
    # PAGE NUMBER
    # ==================================================

    @discord.ui.button(
        label="1/1",
        style=discord.ButtonStyle.primary,
        disabled=True,
        row=1,
    )
    async def page_number(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        pass

    # ==================================================
    # NEXT PAGE
    # ==================================================

    @discord.ui.button(
        label="Next",
        emoji="▶️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def next_page(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        total = self.total_pages()

        self.page += 1

        if self.page >= total:
            self.page = 0

        self.build_select()

        await interaction.response.edit_message(
            content=(
                "🌸 **Choose a Proxy Emoji**\n\n"
                "Choose a normal emoji or "
                "one of the server's custom emojis."
            ),
            view=self,
        )


# ==================================================
# ALTER BASIC FORM
# ==================================================

class AlterBasicModal(
    discord.ui.Modal
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        system_profile_id: int,
        existing: dict | None = None,
        alter_id: int | None = None,
    ):

        super().__init__(
            title=(
                "Edit Alter - Basics"
                if alter_id
                else "Alter Profile - Basics"
            )
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id

        self.system_profile_id = (
            system_profile_id
        )

        self.existing = dict(
            existing or {}
        )

        self.alter_id = alter_id

        self.name_input = (
            discord.ui.TextInput(
                label="Name",
                placeholder=(
                    "What name do they use?"
                ),
                required=True,
                max_length=100,
                default=(
                    self.existing.get(
                        "name"
                    )
                    or ""
                ),
            )
        )

        self.nicknames = (
            discord.ui.TextInput(
                label="Nickname(s)",
                placeholder="Optional",
                required=False,
                max_length=150,
                default=(
                    self.existing.get(
                        "nicknames"
                    )
                    or ""
                ),
            )
        )

        self.pronouns = (
            discord.ui.TextInput(
                label="Pronouns",
                placeholder=(
                    "Example: she/her, they/them"
                ),
                required=False,
                max_length=100,
                default=(
                    self.existing.get(
                        "pronouns"
                    )
                    or ""
                ),
            )
        )

        self.age = (
            discord.ui.TextInput(
                label="Age / Age Range",
                placeholder="Optional",
                required=False,
                max_length=100,
                default=(
                    self.existing.get(
                        "age"
                    )
                    or ""
                ),
            )
        )

        self.add_item(
            self.name_input
        )

        self.add_item(
            self.nicknames
        )

        self.add_item(
            self.pronouns
        )

        self.add_item(
            self.age
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
                "name":
                    str(
                        self.name_input.value
                    ).strip(),

                "nicknames":
                    str(
                        self.nicknames.value
                    ).strip(),

                "pronouns":
                    str(
                        self.pronouns.value
                    ).strip(),

                "age":
                    str(
                        self.age.value
                    ).strip(),
            }
        )

        view = AlterEmojiSelectView(
            bot=self.bot,
            guild_id=self.guild_id,
            user_id=self.user_id,
            system_profile_id=(
                self.system_profile_id
            ),
            data=data,
            alter_id=self.alter_id,
        )

        current = data.get(
            "proxy_emoji"
        )

        if current:

            message = (
                "🌸 **Choose a Proxy Emoji**\n\n"
                f"Current emoji: {current}\n\n"
                "Choose a normal emoji or "
                "one of the server's custom emojis."
            )

        else:

            message = (
                "🌸 **Choose a Proxy Emoji**\n\n"
                "Choose a normal emoji or "
                "one of the server's custom emojis."
            )

        await interaction.response.send_message(
            message,
            view=view,
            ephemeral=True,
        )


# ==================================================
# ALTER IDENTITY FORM
# ==================================================

class AlterIdentityModal(
    discord.ui.Modal
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        system_profile_id: int,
        data: dict,
        alter_id: int | None = None,
    ):

        super().__init__(
            title=(
                "Edit Alter - Identity"
                if alter_id
                else "Alter Profile - Identity"
            )
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id

        self.system_profile_id = (
            system_profile_id
        )

        self.data = data
        self.alter_id = alter_id

        self.gender = (
            discord.ui.TextInput(
                label="Gender",
                placeholder="Optional",
                required=False,
                max_length=100,
                default=(
                    data.get("gender")
                    or ""
                ),
            )
        )

        self.system_role = (
            discord.ui.TextInput(
                label="Role in the System",
                placeholder="Optional",
                required=False,
                max_length=150,
                default=(
                    data.get(
                        "system_role"
                    )
                    or ""
                ),
            )
        )

        self.species_identity = (
            discord.ui.TextInput(
                label="Species / Identity",
                placeholder="Optional",
                required=False,
                max_length=150,
                default=(
                    data.get(
                        "species_identity"
                    )
                    or ""
                ),
            )
        )

        self.source_info = (
            discord.ui.TextInput(
                label="Source / Introject Info",
                placeholder="Optional",
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=500,
                default=(
                    data.get(
                        "source_info"
                    )
                    or ""
                ),
            )
        )

        self.hobbies = (
            discord.ui.TextInput(
                label="Hobbies / Interests",
                placeholder=(
                    "What do they enjoy doing?"
                ),
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=500,
                default=(
                    data.get("hobbies")
                    or ""
                ),
            )
        )

        self.add_item(
            self.gender
        )

        self.add_item(
            self.system_role
        )

        self.add_item(
            self.species_identity
        )

        self.add_item(
            self.source_info
        )

        self.add_item(
            self.hobbies
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        self.data.update(
            {
                "gender":
                    str(
                        self.gender.value
                    ).strip(),

                "system_role":
                    str(
                        self.system_role.value
                    ).strip(),

                "species_identity":
                    str(
                        self.species_identity.value
                    ).strip(),

                "source_info":
                    str(
                        self.source_info.value
                    ).strip(),

                "hobbies":
                    str(
                        self.hobbies.value
                    ).strip(),
            }
        )

        view = AlterSocialChoicesView(
            bot=self.bot,
            guild_id=self.guild_id,
            user_id=self.user_id,
            system_profile_id=(
                self.system_profile_id
            ),
            data=self.data,
            alter_id=self.alter_id,
        )

        await interaction.response.send_message(
            view.status_text(),
            view=view,
            ephemeral=True,
        )


# ==================================================
# ALTER SOCIAL CHOICES
# ==================================================

class AlterSocialChoicesView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        system_profile_id: int,
        data: dict,
        alter_id: int | None = None,
    ):

        super().__init__(
            timeout=600
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id

        self.system_profile_id = (
            system_profile_id
        )

        self.data = data
        self.alter_id = alter_id

        self.dm_select = discord.ui.Select(
            placeholder="Choose DM status",
            row=0,
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

        self.interaction_select = (
            discord.ui.Select(
                placeholder=(
                    "Choose interaction status"
                ),
                row=1,
                options=[
                    discord.SelectOption(
                        label="Interactions Open",
                        value=(
                            "🟢 Interactions Open"
                        ),
                    ),
                    discord.SelectOption(
                        label="Ask First",
                        value="🟡 Ask First",
                    ),
                    discord.SelectOption(
                        label="Limited",
                        value="🟠 Limited",
                    ),
                    discord.SelectOption(
                        label="Do Not Interact",
                        value=(
                            "🔴 Do Not Interact"
                        ),
                    ),
                ],
            )
        )

        self.frontal_select = (
            discord.ui.Select(
                placeholder=(
                    "Frequent fronter?"
                ),
                row=2,
                options=[
                    discord.SelectOption(
                        label="Yes",
                        value="yes",
                    ),
                    discord.SelectOption(
                        label="No",
                        value="no",
                    ),
                ],
            )
        )

        self.dm_select.callback = (
            self.dm_callback
        )

        self.interaction_select.callback = (
            self.interaction_callback
        )

        self.frontal_select.callback = (
            self.frontal_callback
        )

        self.add_item(
            self.dm_select
        )

        self.add_item(
            self.interaction_select
        )

        self.add_item(
            self.frontal_select
        )

    def status_text(self):

        if (
            "frequent_fronter"
            not in self.data
        ):

            frequent = "Not set"

        elif self.data.get(
            "frequent_fronter"
        ):

            frequent = "Yes"

        else:

            frequent = "No"

        return (
            "🌸 **Alter Profile — Interaction**\n\n"

            f"**DM Status:** "
            f"{clean_value(self.data.get('dm_status'))}\n"

            f"**Interaction Status:** "
            f"{clean_value(self.data.get('interaction_status'))}\n"

            f"**Frequent Fronter:** "
            f"{frequent}\n\n"

            "Choose all three, then press **Next**."
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
                    "❌ This alter profile "
                    "isn't yours."
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

    async def interaction_callback(
        self,
        interaction: discord.Interaction,
    ):

        self.data[
            "interaction_status"
        ] = (
            self.interaction_select
            .values[0]
        )

        await interaction.response.edit_message(
            content=self.status_text(),
            view=self,
        )

    async def frontal_callback(
        self,
        interaction: discord.Interaction,
    ):

        self.data[
            "frequent_fronter"
        ] = (
            self.frontal_select
            .values[0]
            == "yes"
        )

        await interaction.response.edit_message(
            content=self.status_text(),
            view=self,
        )

    @discord.ui.button(
        label="Next",
        emoji="➡️",
        style=discord.ButtonStyle.primary,
        row=3,
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        missing = []

        if not self.data.get(
            "dm_status"
        ):

            missing.append(
                "DM Status"
            )

        if not self.data.get(
            "interaction_status"
        ):

            missing.append(
                "Interaction Status"
            )

        if (
            "frequent_fronter"
            not in self.data
        ):

            missing.append(
                "Frequent Fronter"
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
            AlterFinalModal(
                bot=self.bot,
                guild_id=self.guild_id,
                user_id=self.user_id,
                system_profile_id=(
                    self.system_profile_id
                ),
                data=self.data,
                alter_id=self.alter_id,
            )
        )


# ==================================================
# ALTER FINAL FORM
# ==================================================

class AlterFinalModal(
    discord.ui.Modal
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        system_profile_id: int,
        data: dict,
        alter_id: int | None = None,
    ):

        super().__init__(
            title=(
                "Edit Alter - About"
                if alter_id
                else "Alter Profile - About"
            )
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id

        self.system_profile_id = (
            system_profile_id
        )

        self.data = data
        self.alter_id = alter_id

        self.likes = (
            discord.ui.TextInput(
                label="Likes",
                placeholder=(
                    "Things they like"
                ),
                required=False,
                style=discord.TextStyle.paragraph,
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
                    "Things they dislike"
                ),
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=500,
                default=(
                    data.get("dislikes")
                    or ""
                ),
            )
        )

        self.boundaries = (
            discord.ui.TextInput(
                label="Boundaries",
                placeholder=(
                    "Interaction boundaries"
                ),
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=700,
                default=(
                    data.get("boundaries")
                    or ""
                ),
            )
        )

        self.dni = (
            discord.ui.TextInput(
                label="DNI",
                placeholder=(
                    "Do not interact if..."
                ),
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=700,
                default=(
                    data.get("dni")
                    or ""
                ),
            )
        )

        self.about_me = (
            discord.ui.TextInput(
                label="About Me",
                placeholder=(
                    "Anything else they'd like to share"
                ),
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=700,
                default=(
                    data.get(
                        "about_me"
                    )
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
            self.boundaries
        )

        self.add_item(
            self.dni
        )

        self.add_item(
            self.about_me
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

                "boundaries":
                    str(
                        self.boundaries.value
                    ).strip(),

                "dni":
                    str(
                        self.dni.value
                    ).strip(),

                "about_me":
                    str(
                        self.about_me.value
                    ).strip(),
            }
        )

        view = AlterPreviewView(
            bot=self.bot,
            guild_id=self.guild_id,
            user_id=self.user_id,
            system_profile_id=(
                self.system_profile_id
            ),
            data=self.data,
            alter_id=self.alter_id,
        )

        await interaction.response.send_message(
            (
                "🌸 **Alter Profile Preview**\n\n"
                "Check everything below, "
                "then press **Save Alter**."
            ),
            embed=build_alter_embed(
                self.data
            ),
            view=view,
            ephemeral=True,
        )


# ==================================================
# ALTER PREVIEW / SAVE
# ==================================================

class AlterPreviewView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        system_profile_id: int,
        data: dict,
        alter_id: int | None = None,
    ):

        super().__init__(
            timeout=600
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id

        self.system_profile_id = (
            system_profile_id
        )

        self.data = data
        self.alter_id = alter_id

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
                    "❌ This alter profile "
                    "isn't yours."
                ),
                ephemeral=True,
            )

            return False

        return True

    @discord.ui.button(
        label="Save Alter",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def save_alter(
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

        try:

            profile = (
                await get_system_profile(
                    self.guild_id,
                    self.user_id,
                )
            )

        except Exception:

            traceback.print_exc()
            profile = None

        if (
            not profile
            or profile["id"]
            != self.system_profile_id
        ):

            return await interaction.followup.send(
                (
                    "❌ I couldn't find "
                    "your System Profile."
                ),
                ephemeral=True,
            )

        # ==================================================
        # EDIT EXISTING ALTER
        # ==================================================

        if self.alter_id:

            try:

                current = (
                    await get_alter_profile(
                        self.alter_id
                    )
                )

                if (
                    not current
                    or current[
                        "system_profile_id"
                    ]
                    != self.system_profile_id
                ):

                    return await interaction.followup.send(
                        (
                            "❌ That alter profile "
                            "doesn't belong to you."
                        ),
                        ephemeral=True,
                    )

                editable_fields = [
                    "name",
                    "nicknames",
                    "pronouns",
                    "gender",
                    "age",
                    "system_role",
                    "species_identity",
                    "source_info",
                    "proxy_emoji",
                    "likes",
                    "dislikes",
                    "hobbies",
                    "dm_status",
                    "interaction_status",
                    "boundaries",
                    "dni",
                    "frequent_fronter",
                    "about_me",
                ]

                for field in editable_fields:

                    await update_alter_field(
                        self.alter_id,
                        field,
                        self.data.get(
                            field
                        ),
                    )

                saved_alter_id = (
                    self.alter_id
                )

                action_text = "updated"

            except Exception:

                traceback.print_exc()

                return await interaction.followup.send(
                    (
                        "❌ I couldn't update "
                        "the alter profile."
                    ),
                    ephemeral=True,
                )

        # ==================================================
        # ADD NEW ALTER
        # ==================================================

        else:

            try:

                saved_alter_id = (
                    await add_alter_profile(
                        system_profile_id=(
                            self.system_profile_id
                        ),

                        name=(
                            self.data.get(
                                "name"
                            )
                        ),

                        nicknames=(
                            self.data.get(
                                "nicknames"
                            )
                        ),

                        pronouns=(
                            self.data.get(
                                "pronouns"
                            )
                        ),

                        gender=(
                            self.data.get(
                                "gender"
                            )
                        ),

                        age=(
                            self.data.get(
                                "age"
                            )
                        ),

                        system_role=(
                            self.data.get(
                                "system_role"
                            )
                        ),

                        species_identity=(
                            self.data.get(
                                "species_identity"
                            )
                        ),

                        source_info=(
                            self.data.get(
                                "source_info"
                            )
                        ),

                        proxy_emoji=(
                            self.data.get(
                                "proxy_emoji"
                            )
                        ),

                        likes=(
                            self.data.get(
                                "likes"
                            )
                        ),

                        dislikes=(
                            self.data.get(
                                "dislikes"
                            )
                        ),

                        hobbies=(
                            self.data.get(
                                "hobbies"
                            )
                        ),

                        dm_status=(
                            self.data.get(
                                "dm_status"
                            )
                        ),

                        interaction_status=(
                            self.data.get(
                                "interaction_status"
                            )
                        ),

                        boundaries=(
                            self.data.get(
                                "boundaries"
                            )
                        ),

                        dni=(
                            self.data.get(
                                "dni"
                            )
                        ),

                        frequent_fronter=(
                            self.data.get(
                                "frequent_fronter",
                                False,
                            )
                        ),

                        about_me=(
                            self.data.get(
                                "about_me"
                            )
                        ),
                    )
                )

                action_text = "added"

            except Exception:

                traceback.print_exc()

                return await interaction.followup.send(
                    (
                        "❌ I couldn't save "
                        "the alter profile."
                    ),
                    ephemeral=True,
                )

        # --------------------------------------------------
        # REFRESH PUBLIC SYSTEM PROFILE
        # --------------------------------------------------

        await refresh_system_profile_message(
            self.bot,
            guild,
            profile,
        )

        # --------------------------------------------------
        # DISABLE PREVIEW
        # --------------------------------------------------

        for child in self.children:

            child.disabled = True

        try:

            await interaction.message.edit(
                view=self
            )

        except discord.HTTPException:
            pass

        alters = (
            await get_alter_profiles(
                self.system_profile_id
            )
        )

        await interaction.followup.send(
            (
                f"✅ **{self.data.get('name')}** "
                f"has been {action_text}!\n\n"
                f"Alter ID: `{saved_alter_id}`\n"
                f"System now has "
                f"**{len(alters)}** alter profile(s)."
            ),
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
                "❌ Alter profile cancelled."
            ),
            embed=None,
            view=None,
        )


# ==================================================
# DELETE ALTER CONFIRMATION
# ==================================================

class DeleteAlterConfirmView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        guild_id: int,
        user_id: int,
        profile: dict,
        alter: dict,
    ):

        super().__init__(
            timeout=120
        )

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.profile = profile
        self.alter = alter

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
                    "❌ This confirmation "
                    "isn't for you."
                ),
                ephemeral=True,
            )

            return False

        return True

    @discord.ui.button(
        label="Delete Alter",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
    )
    async def confirm_delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            await delete_alter_profile(
                self.alter["id"]
            )

        except Exception:

            traceback.print_exc()

            return await interaction.followup.send(
                (
                    "❌ I couldn't delete "
                    "the alter profile."
                ),
                ephemeral=True,
            )

        guild = self.bot.get_guild(
            self.guild_id
        )

        if guild:

            await refresh_system_profile_message(
                self.bot,
                guild,
                self.profile,
            )

        self.stop()

        try:

            await interaction.message.edit(
                content=(
                    f"🗑️ **{self.alter['name']}** "
                    "has been removed from "
                    "the System Profile."
                ),
                embed=None,
                view=None,
            )

        except discord.HTTPException:
            pass

        await interaction.followup.send(
            (
                f"✅ **{self.alter['name']}** "
                "was deleted."
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Cancel",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel_delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        self.stop()

        await interaction.response.edit_message(
            content="✅ Nothing was deleted.",
            embed=None,
            view=None,
        )


# ==================================================
# ALTER COG
# ==================================================

class Alters(
    commands.Cog
):

    alter = app_commands.Group(
        name="alter",
        description=(
            "Create and manage alter profiles."
        ),
    )

    def __init__(
        self,
        bot,
    ):

        self.bot = bot

    # ==================================================
    # RESTORE BROWSE BUTTONS AFTER REDEPLOY
    # ==================================================

    async def cog_load(self):

        try:

            rows = (
                await self.bot.db.fetch(
                    """
                    SELECT
                        id,
                        profile_message_id

                    FROM system_profiles

                    WHERE profile_message_id
                        IS NOT NULL
                    """
                )
            )

        except Exception as e:

            print(
                (
                    "⚠️ Couldn't restore "
                    "System Profile buttons: "
                    f"{e}"
                )
            )

            return

        restored = 0

        for row in rows:

            try:

                self.bot.add_view(
                    SystemAlterButtonView(
                        self.bot,
                        row["id"],
                    ),
                    message_id=(
                        row[
                            "profile_message_id"
                        ]
                    ),
                )

                restored += 1

            except Exception as e:

                print(
                    (
                        "⚠️ Couldn't restore "
                        f"System Profile "
                        f"{row['id']}: {e}"
                    )
                )

        print(
            (
                f"🌸 Restored {restored} "
                "System Profile alter browser(s)."
            )
        )

    # ==================================================
    # /ALTER ADD
    # ==================================================

    @alter.command(
        name="add",
        description=(
            "Add an alter to your System Profile."
        ),
    )
    async def add_alter(
        self,
        interaction: discord.Interaction,
    ):

        try:

            profile = (
                await get_system_profile(
                    interaction.guild.id,
                    interaction.user.id,
                )
            )

        except Exception:

            traceback.print_exc()
            profile = None

        if not profile:

            return await interaction.response.send_message(
                (
                    "❌ You need a "
                    "System Profile first.\n\n"
                    "Use `/systemprofile setup`."
                ),
                ephemeral=True,
            )

        await interaction.response.send_modal(
            AlterBasicModal(
                bot=self.bot,
                guild_id=(
                    interaction.guild.id
                ),
                user_id=(
                    interaction.user.id
                ),
                system_profile_id=(
                    profile["id"]
                ),
            )
        )

    # ==================================================
    # /ALTER LIST
    # ==================================================

    @alter.command(
        name="list",
        description=(
            "List your saved alter profiles."
        ),
    )
    async def list_alters(
        self,
        interaction: discord.Interaction,
    ):

        try:

            profile = (
                await get_system_profile(
                    interaction.guild.id,
                    interaction.user.id,
                )
            )

        except Exception:

            traceback.print_exc()
            profile = None

        if not profile:

            return await interaction.response.send_message(
                (
                    "❌ You don't have "
                    "a System Profile."
                ),
                ephemeral=True,
            )

        alters = (
            await get_alter_profiles(
                profile["id"]
            )
        )

        if not alters:

            return await interaction.response.send_message(
                (
                    "🌸 You haven't added "
                    "any alter profiles yet.\n\n"
                    "Use `/alter add`."
                ),
                ephemeral=True,
            )

        lines = []

        for number, alter in enumerate(
            alters,
            start=1,
        ):

            proxy = (
                alter.get(
                    "proxy_emoji"
                )
                or "🌸"
            )

            lines.append(
                (
                    f"**{number}.** "
                    f"{proxy} "
                    f"**{alter['name']}** "
                    f"— ID `{alter['id']}`"
                )
            )

        embed = discord.Embed(
            title="🌸 Your Alter Profiles",
            description="\n".join(
                lines
            ),
            colour=discord.Colour.blurple(),
        )

        embed.set_footer(
            text=(
                f"{len(alters)} "
                "alter profile(s)"
            )
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # ==================================================
    # /ALTER EDIT
    # ==================================================

    @alter.command(
        name="edit",
        description=(
            "Edit one of your alter profiles."
        ),
    )
    @app_commands.describe(
        alter_id=(
            "Alter ID shown by /alter list"
        ),
    )
    async def edit_alter(
        self,
        interaction: discord.Interaction,
        alter_id: int,
    ):

        try:

            profile, alter = (
                await alter_belongs_to_user(
                    interaction.guild.id,
                    interaction.user.id,
                    alter_id,
                )
            )

        except Exception:

            traceback.print_exc()

            return await interaction.response.send_message(
                (
                    "❌ I couldn't load "
                    "that alter profile."
                ),
                ephemeral=True,
            )

        if not profile:

            return await interaction.response.send_message(
                (
                    "❌ You don't have "
                    "a System Profile."
                ),
                ephemeral=True,
            )

        if not alter:

            return await interaction.response.send_message(
                (
                    "❌ I couldn't find an alter "
                    "with that ID on your system.\n\n"
                    "Use `/alter list` to "
                    "check the ID."
                ),
                ephemeral=True,
            )

        await interaction.response.send_modal(
            AlterBasicModal(
                bot=self.bot,
                guild_id=(
                    interaction.guild.id
                ),
                user_id=(
                    interaction.user.id
                ),
                system_profile_id=(
                    profile["id"]
                ),
                existing=alter,
                alter_id=alter_id,
            )
        )

    # ==================================================
    # /ALTER REMOVE
    # ==================================================

    @alter.command(
        name="remove",
        description=(
            "Remove an alter from your System Profile."
        ),
    )
    @app_commands.describe(
        alter_id=(
            "Alter ID shown by /alter list"
        ),
    )
    async def remove_alter(
        self,
        interaction: discord.Interaction,
        alter_id: int,
    ):

        try:

            profile, alter = (
                await alter_belongs_to_user(
                    interaction.guild.id,
                    interaction.user.id,
                    alter_id,
                )
            )

        except Exception:

            traceback.print_exc()

            return await interaction.response.send_message(
                (
                    "❌ I couldn't load "
                    "that alter profile."
                ),
                ephemeral=True,
            )

        if not profile:

            return await interaction.response.send_message(
                (
                    "❌ You don't have "
                    "a System Profile."
                ),
                ephemeral=True,
            )

        if not alter:

            return await interaction.response.send_message(
                (
                    "❌ I couldn't find an alter "
                    "with that ID on your system.\n\n"
                    "Use `/alter list` to "
                    "check the ID."
                ),
                ephemeral=True,
            )

        embed = build_alter_embed(
            alter
        )

        embed.title = (
            f"⚠️ Delete {alter['name']}?"
        )

        embed.description = (
            "This will permanently remove "
            "this alter profile from the system.\n\n"
            "**This cannot be undone.**"
        )

        view = DeleteAlterConfirmView(
            bot=self.bot,
            guild_id=(
                interaction.guild.id
            ),
            user_id=(
                interaction.user.id
            ),
            profile=profile,
            alter=alter,
        )

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )


# ==================================================
# LOAD COG
# ==================================================

async def setup(bot):

    await bot.add_cog(
        Alters(bot)
    )
