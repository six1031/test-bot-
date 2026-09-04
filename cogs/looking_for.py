# cogs/looking_for.py

import discord
from discord.ext import commands
from discord import app_commands

from database.database import db

from database.looking_for import (
    get_looking_for_settings,
    save_looking_for_settings,
    set_looking_for_category_channel,
    get_all_looking_for_category_channels,
    get_looking_for_category_channel,

    create_looking_for_post,
    get_looking_for_post,
    get_active_looking_for_post,
    get_user_looking_for_posts,
    publish_looking_for_post,
    update_looking_for_post_field,
    close_looking_for_post,
    delete_looking_for_draft,

    create_looking_for_report,
)


# ==================================================
# CATEGORY INFORMATION
# ==================================================

CATEGORY_LABELS = {
    "caregiver": "Caregiver",
    "little": "Little",
    "pet": "Pet",
    "handler": "Handler",
    "partner": "Partner",
    "friends": "Friends",
}


CATEGORY_EMOJIS = {
    "caregiver": "🍼",
    "little": "🧸",
    "pet": "🐾",
    "handler": "🦴",
    "partner": "💕",
    "friends": "🤝",
}


CATEGORY_OPTIONS = [
    discord.SelectOption(
        label="Caregiver",
        value="caregiver",
        emoji="🍼",
        description="I'm looking for a caregiver.",
    ),
    discord.SelectOption(
        label="Little",
        value="little",
        emoji="🧸",
        description="I'm looking for a little.",
    ),
    discord.SelectOption(
        label="Pet",
        value="pet",
        emoji="🐾",
        description="I'm looking for a pet.",
    ),
    discord.SelectOption(
        label="Handler",
        value="handler",
        emoji="🦴",
        description="I'm looking for a handler.",
    ),
    discord.SelectOption(
        label="Partner",
        value="partner",
        emoji="💕",
        description="I'm looking for a partner.",
    ),
    discord.SelectOption(
        label="Friends",
        value="friends",
        emoji="🤝",
        description="I'm looking for friends.",
    ),
]


# ==================================================
# HELPERS
# ==================================================

def value_from_row(row, key, default=None):

    if not row:
        return default

    try:
        value = row[key]
    except Exception:
        try:
            value = row.get(key, default)
        except Exception:
            return default

    if value is None:
        return default

    return value


def clean_text(value, default="Not specified"):

    if value is None:
        return default

    value = str(value).strip()

    if not value:
        return default

    return value


def field_text(value, limit=1024):

    text = clean_text(value)

    if len(text) > limit:
        return text[: limit - 3] + "..."

    return text


async def get_post_by_message_id(message_id: int):

    return await db.fetchrow(
        """
        SELECT *
        FROM looking_for_posts
        WHERE message_id = $1
        LIMIT 1
        """,
        message_id,
    )


async def get_latest_selfie(
    guild: discord.Guild,
    user_id: int,
):

    settings = await get_looking_for_settings(
        guild.id
    )

    if not settings:
        return None

    selfies_channel_id = value_from_row(
        settings,
        "selfies_channel_id",
    )

    if not selfies_channel_id:
        return None

    channel = guild.get_channel(
        selfies_channel_id
    )

    if channel is None:
        try:
            channel = await guild.fetch_channel(
                selfies_channel_id
            )
        except Exception:
            return None

    try:

        async for message in channel.history(
            limit=250
        ):

            if message.author.id != user_id:
                continue

            for attachment in message.attachments:

                content_type = (
                    attachment.content_type or ""
                ).lower()

                filename = (
                    attachment.filename or ""
                ).lower()

                is_image = (
                    content_type.startswith("image/")
                    or filename.endswith(
                        (
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".webp",
                            ".gif",
                        )
                    )
                )

                if is_image:
                    return attachment.url

    except discord.Forbidden:
        return None

    except Exception as error:
        print(
            f"⚠️ Looking For selfie search failed: {error}"
        )

    return None


async def build_post_embed(
    guild: discord.Guild,
    post,
):

    user_id = value_from_row(
        post,
        "user_id",
    )

    category = value_from_row(
        post,
        "looking_for_role",
        "unknown",
    )

    member = guild.get_member(
        user_id
    )

    if member is None:
        try:
            member = await guild.fetch_member(
                user_id
            )
        except Exception:
            member = None

    emoji = CATEGORY_EMOJIS.get(
        category,
        "💌",
    )

    label = CATEGORY_LABELS.get(
        category,
        category.title(),
    )

    embed = discord.Embed(
        title=f"{emoji} Looking For A {label}",
        description=(
            field_text(
                value_from_row(
                    post,
                    "looking_for",
                ),
                4000,
            )
        ),
    )

    if member:

        embed.set_author(
            name=member.display_name,
            icon_url=member.display_avatar.url,
        )

    embed.add_field(
        name="👤 My Role(s)",
        value=field_text(
            value_from_row(
                post,
                "roles",
            )
        ),
        inline=True,
    )

    embed.add_field(
        name="💞 Connection Type",
        value=field_text(
            value_from_row(
                post,
                "connection_type",
            )
        ),
        inline=True,
    )

    embed.add_field(
        name="🌷 Preferred Dynamic",
        value=field_text(
            value_from_row(
                post,
                "dynamic_type",
            )
        ),
        inline=True,
    )

    embed.add_field(
        name="✨ Preferred Vibe",
        value=field_text(
            value_from_row(
                post,
                "preferred_vibe",
            )
        ),
        inline=True,
    )

    embed.add_field(
        name="❓ Things I'd Love To Know",
        value=field_text(
            value_from_row(
                post,
                "questions",
            )
        ),
        inline=False,
    )

    embed.add_field(
        name="🚫 DNI / Boundaries",
        value=field_text(
            value_from_row(
                post,
                "dni",
            )
        ),
        inline=False,
    )

    embed.add_field(
        name="💌 Contact Preference",
        value=field_text(
            value_from_row(
                post,
                "dm_status",
            )
        ),
        inline=True,
    )

    extra = clean_text(
        value_from_row(
            post,
            "extra",
        ),
        "",
    )

    if extra:

        embed.add_field(
            name="📝 Extra",
            value=field_text(
                extra
            ),
            inline=False,
        )

    selfie_url = value_from_row(
        post,
        "selfie_url",
    )

    if selfie_url:
        embed.set_image(
            url=selfie_url
        )

    embed.set_footer(
        text=(
            "Pillow Palace • Strictly SFW • 18+ • "
            "Use Send Message to contact safely through Pillow Pal"
        )
    )

    return embed


async def refresh_public_post(
    bot,
    post_id: int,
):

    post = await get_looking_for_post(
        post_id
    )

    if not post:
        return

    guild_id = value_from_row(
        post,
        "guild_id",
    )

    channel_id = value_from_row(
        post,
        "channel_id",
    )

    message_id = value_from_row(
        post,
        "message_id",
    )

    if not channel_id or not message_id:
        return

    guild = bot.get_guild(
        guild_id
    )

    if guild is None:
        return

    channel = guild.get_channel(
        channel_id
    )

    if channel is None:
        return

    try:

        message = await channel.fetch_message(
            message_id
        )

        embed = await build_post_embed(
            guild,
            post,
        )

        await message.edit(
            embed=embed,
            view=ActiveLookingForView(),
        )

    except Exception as error:
        print(
            f"⚠️ Failed to refresh Looking For post {post_id}: {error}"
        )


# ==================================================
# CREATION STATE
# ==================================================

class LookingForCreationState:

    def __init__(
        self,
        guild_id: int,
        user_id: int,
        categories: list[str],
    ):

        self.guild_id = guild_id
        self.user_id = user_id
        self.categories = categories

        self.roles = None
        self.connection_type = None
        self.dynamic_type = None
        self.preferred_vibe = None
        self.looking_for = None

        self.questions = None
        self.dni = None
        self.dm_status = None
        self.extra = None

        self.selfie_url = None

        self.post_ids = []


# ==================================================
# STEP 1 MODAL
# ==================================================

class LookingForAboutModal(
    discord.ui.Modal,
    title="Looking For • About You",
):

    roles = discord.ui.TextInput(
        label="Your role(s)",
        placeholder="Example: Little, Pet, Flip",
        required=True,
        max_length=100,
    )

    connection_type = discord.ui.TextInput(
        label="Connection type",
        placeholder=(
            "Friendship, Platonic Dynamic, Romantic, "
            "Relationship, Open to Either..."
        ),
        required=True,
        max_length=100,
    )

    dynamic_type = discord.ui.TextInput(
        label="Preferred dynamic",
        placeholder=(
            "Supportive, structured, gentle, playful, "
            "nurturing..."
        ),
        required=False,
        max_length=150,
    )

    preferred_vibe = discord.ui.TextInput(
        label="Preferred vibe",
        placeholder=(
            "Calm, patient, affectionate, fun, "
            "understanding..."
        ),
        required=False,
        max_length=150,
    )

    looking_for = discord.ui.TextInput(
        label="What are you looking for?",
        placeholder=(
            "Tell people what kind of person or "
            "connection you're hoping to find."
        ),
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(
        self,
        state: LookingForCreationState,
    ):

        super().__init__()

        self.state = state

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        self.state.roles = self.roles.value
        self.state.connection_type = (
            self.connection_type.value
        )
        self.state.dynamic_type = (
            self.dynamic_type.value
        )
        self.state.preferred_vibe = (
            self.preferred_vibe.value
        )
        self.state.looking_for = (
            self.looking_for.value
        )

        await interaction.response.send_modal(
            LookingForDetailsModal(
                self.state
            )
        )


# ==================================================
# STEP 2 MODAL
# ==================================================

class LookingForDetailsModal(
    discord.ui.Modal,
    title="Looking For • Your Post",
):

    questions = discord.ui.TextInput(
        label="Things you'd love to know",
        placeholder=(
            "What would you like someone interested "
            "in your post to tell you?"
        ),
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=800,
    )

    dni = discord.ui.TextInput(
        label="DNI / boundaries",
        placeholder=(
            "Boundaries, communication preferences, "
            "pressure, deal-breakers..."
        ),
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=800,
    )

    dm_status = discord.ui.TextInput(
        label="Contact preference",
        placeholder=(
            "Bot Contact Only / Ask First / Open / Closed"
        ),
        default="Bot Contact Only",
        required=True,
        max_length=100,
    )

    extra = discord.ui.TextInput(
        label="Anything else?",
        placeholder="Optional extra information.",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=800,
    )

    def __init__(
        self,
        state: LookingForCreationState,
    ):

        super().__init__()

        self.state = state

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        self.state.questions = self.questions.value
        self.state.dni = self.dni.value
        self.state.dm_status = self.dm_status.value
        self.state.extra = self.extra.value

        await interaction.response.defer(
            ephemeral=True
        )

        selfie_url = await get_latest_selfie(
            interaction.guild,
            interaction.user.id,
        )

        if selfie_url:

            embed = discord.Embed(
                title="📸 Use Your Latest Selfie?",
                description=(
                    "Pillow Pal found your most recent image "
                    "in the configured selfies channel.\n\n"
                    "Would you like to include it on your "
                    "Looking For post?"
                ),
            )

            embed.set_image(
                url=selfie_url
            )

            await interaction.followup.send(
                embed=embed,
                view=SelfieChoiceView(
                    self.state,
                    selfie_url,
                ),
                ephemeral=True,
            )

            return

        await create_drafts_and_show(
            interaction,
            self.state,
        )


# ==================================================
# SELFIE CHOICE
# ==================================================

class SelfieChoiceView(discord.ui.View):

    def __init__(
        self,
        state: LookingForCreationState,
        selfie_url: str,
    ):

        super().__init__(
            timeout=300
        )

        self.state = state
        self.selfie_url = selfie_url

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):

        if interaction.user.id != self.state.user_id:

            await interaction.response.send_message(
                "This form belongs to someone else.",
                ephemeral=True,
            )

            return False

        return True

    @discord.ui.button(
        label="Use Selfie",
        emoji="📸",
        style=discord.ButtonStyle.success,
    )
    async def use_selfie(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        self.state.selfie_url = self.selfie_url

        await interaction.response.defer(
            ephemeral=True
        )

        await create_drafts_and_show(
            interaction,
            self.state,
        )

    @discord.ui.button(
        label="Don't Use It",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
    )
    async def skip_selfie(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        self.state.selfie_url = None

        await interaction.response.defer(
            ephemeral=True
        )

        await create_drafts_and_show(
            interaction,
            self.state,
        )


# ==================================================
# CREATE DRAFTS
# ==================================================

async def create_drafts_and_show(
    interaction: discord.Interaction,
    state: LookingForCreationState,
):

    state.post_ids = []

    for category in state.categories:

        try:

            post = await create_looking_for_post(
                guild_id=state.guild_id,
                user_id=state.user_id,
                looking_for_role=category,
                roles=state.roles,
                connection_type=state.connection_type,
                dynamic_type=state.dynamic_type,
                preferred_vibe=state.preferred_vibe,
                looking_for=state.looking_for,
                questions=state.questions,
                dni=state.dni,
                dm_status=state.dm_status,
                extra=state.extra,
                selfie_url=state.selfie_url,
                status="draft",
            )

            post_id = value_from_row(
                post,
                "id",
            )

            if post_id is None and isinstance(
                post,
                int,
            ):
                post_id = post

            if post_id:
                state.post_ids.append(
                    post_id
                )

        except Exception as error:

            print(
                f"❌ Failed to create Looking For draft: {error}"
            )

    if not state.post_ids:

        await interaction.followup.send(
            (
                "❌ I couldn't create your drafts.\n\n"
                "Check the Railway logs and send me the "
                "error if one appeared."
            ),
            ephemeral=True,
        )

        return

    await show_draft_manager(
        interaction,
        state.post_ids,
    )


# ==================================================
# DRAFT MANAGER
# ==================================================

async def show_draft_manager(
    interaction: discord.Interaction,
    post_ids: list[int],
):

    posts = []

    for post_id in post_ids:

        post = await get_looking_for_post(
            post_id
        )

        if post:
            posts.append(post)

    if not posts:
        return

    first = posts[0]

    embed = await build_post_embed(
        interaction.guild,
        first,
    )

    category = value_from_row(
        first,
        "looking_for_role",
    )

    embed.title = (
        "📝 DRAFT • "
        f"{CATEGORY_LABELS.get(category, category.title())}"
    )

    await interaction.followup.send(
        content=(
            "Your draft posts are ready. Choose one below "
            "to preview, edit or publish."
        ),
        embed=embed,
        view=DraftManagerView(
            interaction.user.id,
            post_ids,
        ),
        ephemeral=True,
    )


class DraftSelect(discord.ui.Select):

    def __init__(
        self,
        post_ids: list[int],
    ):

        options = []

        for post_id in post_ids:

            options.append(
                discord.SelectOption(
                    label=f"Draft #{post_id}",
                    value=str(post_id),
                    description=(
                        "Select this draft to manage it."
                    ),
                )
            )

        super().__init__(
            placeholder="Choose a draft to manage",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        self.view.selected_post_id = int(
            self.values[0]
        )

        post = await get_looking_for_post(
            self.view.selected_post_id
        )

        if not post:
            await interaction.response.send_message(
                "That draft could not be found.",
                ephemeral=True,
            )
            return

        embed = await build_post_embed(
            interaction.guild,
            post,
        )

        category = value_from_row(
            post,
            "looking_for_role",
        )

        embed.title = (
            "📝 DRAFT • "
            f"{CATEGORY_LABELS.get(category, category.title())}"
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self.view,
        )


class DraftManagerView(discord.ui.View):

    def __init__(
        self,
        user_id: int,
        post_ids: list[int],
    ):

        super().__init__(
            timeout=900
        )

        self.user_id = user_id
        self.post_ids = post_ids

        self.selected_post_id = (
            post_ids[0]
            if post_ids
            else None
        )

        self.add_item(
            DraftSelect(
                post_ids
            )
        )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "These drafts belong to someone else.",
                ephemeral=True,
            )

            return False

        return True

    @discord.ui.button(
        label="Edit",
        emoji="✏️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def edit_draft(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.selected_post_id:
            return

        await interaction.response.send_message(
            "Choose which part of this post you want to edit.",
            view=EditPostFieldView(
                self.user_id,
                self.selected_post_id,
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Publish",
        emoji="✅",
        style=discord.ButtonStyle.success,
        row=1,
    )
    async def publish_draft(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.selected_post_id:
            return

        await publish_single_post(
            interaction,
            self.selected_post_id,
        )

    @discord.ui.button(
        label="Publish All",
        emoji="📨",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def publish_all(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        results = []

        for post_id in self.post_ids:

            result = await publish_post_core(
                interaction,
                post_id,
            )

            results.append(
                result
            )

        await interaction.followup.send(
            "\n".join(results),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Delete Draft",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def delete_draft(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.selected_post_id:
            return

        await delete_looking_for_draft(
            self.selected_post_id,
            self.user_id,
        )

        await interaction.response.send_message(
            "🗑️ That draft has been deleted.",
            ephemeral=True,
        )


# ==================================================
# EDIT SYSTEM
# ==================================================

EDIT_FIELDS = {
    "roles": "My Role(s)",
    "connection_type": "Connection Type",
    "dynamic_type": "Preferred Dynamic",
    "preferred_vibe": "Preferred Vibe",
    "looking_for": "What I'm Looking For",
    "questions": "Things I'd Love To Know",
    "dni": "DNI / Boundaries",
    "dm_status": "Contact Preference",
    "extra": "Extra",
}


class EditFieldSelect(discord.ui.Select):

    def __init__(
        self,
        post_id: int,
    ):

        self.post_id = post_id

        options = []

        for key, label in EDIT_FIELDS.items():

            options.append(
                discord.SelectOption(
                    label=label,
                    value=key,
                )
            )

        super().__init__(
            placeholder="Choose what to edit",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        field = self.values[0]

        post = await get_looking_for_post(
            self.post_id
        )

        if not post:
            await interaction.response.send_message(
                "Post not found.",
                ephemeral=True,
            )
            return

        current = clean_text(
            value_from_row(
                post,
                field,
            ),
            "",
        )

        await interaction.response.send_modal(
            EditSingleFieldModal(
                post_id=self.post_id,
                field=field,
                current_value=current,
            )
        )


class EditPostFieldView(discord.ui.View):

    def __init__(
        self,
        user_id: int,
        post_id: int,
    ):

        super().__init__(
            timeout=300
        )

        self.user_id = user_id

        self.add_item(
            EditFieldSelect(
                post_id
            )
        )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "This post belongs to someone else.",
                ephemeral=True,
            )

            return False

        return True


class EditSingleFieldModal(
    discord.ui.Modal,
    title="Edit Looking For Post",
):

    new_value = discord.ui.TextInput(
        label="New value",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
    )

    def __init__(
        self,
        post_id: int,
        field: str,
        current_value: str,
    ):

        super().__init__()

        self.post_id = post_id
        self.field = field

        self.new_value.label = (
            EDIT_FIELDS.get(
                field,
                "New value",
            )
        )

        self.new_value.default = current_value

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        post = await get_looking_for_post(
            self.post_id
        )

        if not post:

            await interaction.response.send_message(
                "Post not found.",
                ephemeral=True,
            )

            return

        if value_from_row(
            post,
            "user_id",
        ) != interaction.user.id:

            await interaction.response.send_message(
                "You can't edit someone else's post.",
                ephemeral=True,
            )

            return

        await update_looking_for_post_field(
            self.post_id,
            self.field,
            self.new_value.value,
        )

        status = value_from_row(
            post,
            "status",
        )

        if status == "active":

            await refresh_public_post(
                interaction.client,
                self.post_id,
            )

        updated = await get_looking_for_post(
            self.post_id
        )

        embed = await build_post_embed(
            interaction.guild,
            updated,
        )

        await interaction.response.send_message(
            "✅ Updated.",
            embed=embed,
            ephemeral=True,
        )


# ==================================================
# PUBLISH
# ==================================================

async def publish_single_post(
    interaction: discord.Interaction,
    post_id: int,
):

    await interaction.response.defer(
        ephemeral=True
    )

    result = await publish_post_core(
        interaction,
        post_id,
    )

    await interaction.followup.send(
        result,
        ephemeral=True,
    )


async def publish_post_core(
    interaction: discord.Interaction,
    post_id: int,
):

    post = await get_looking_for_post(
        post_id
    )

    if not post:
        return "❌ Draft not found."

    if value_from_row(
        post,
        "user_id",
    ) != interaction.user.id:

        return "❌ You don't own that draft."

    category = value_from_row(
        post,
        "looking_for_role",
    )

    active = await get_active_looking_for_post(
        interaction.guild.id,
        interaction.user.id,
        category,
    )

    if active:

        active_id = value_from_row(
            active,
            "id",
        )

        if active_id != post_id:

            label = CATEGORY_LABELS.get(
                category,
                category.title(),
            )

            return (
                f"⚠️ You already have an active "
                f"**{label}** post."
            )

    channel_id = (
        await get_looking_for_category_channel(
            interaction.guild.id,
            category,
        )
    )

    if not channel_id:

        return (
            f"❌ No destination channel is configured "
            f"for `{category}`."
        )

    channel = interaction.guild.get_channel(
        channel_id
    )

    if channel is None:

        try:
            channel = await interaction.guild.fetch_channel(
                channel_id
            )
        except Exception:
            return "❌ I couldn't find the destination channel."

    embed = await build_post_embed(
        interaction.guild,
        post,
    )

    try:

        message = await channel.send(
            embed=embed,
            view=ActiveLookingForView(),
        )

    except discord.Forbidden:

        return (
            f"❌ I don't have permission to post in "
            f"{channel.mention}."
        )

    await publish_looking_for_post(
        post_id,
        channel.id,
        message.id,
    )

    label = CATEGORY_LABELS.get(
        category,
        category.title(),
    )

    return (
        f"✅ **{label}** post published in "
        f"{channel.mention}."
    )


# ==================================================
# PUBLIC POST VIEW
# ==================================================

class ActiveLookingForView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Send Message",
        emoji="💌",
        style=discord.ButtonStyle.primary,
        custom_id="looking_for:send_message",
    )
    async def send_message(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        post = await get_post_by_message_id(
            interaction.message.id
        )

        if not post:

            await interaction.response.send_message(
                "This Looking For post could not be found.",
                ephemeral=True,
            )

            return

        owner_id = value_from_row(
            post,
            "user_id",
        )

        if owner_id == interaction.user.id:

            await interaction.response.send_message(
                "You can't send a contact request to yourself.",
                ephemeral=True,
            )

            return

        dm_status = clean_text(
            value_from_row(
                post,
                "dm_status",
            )
        ).lower()

        if dm_status == "closed":

            await interaction.response.send_message(
                "This member isn't currently accepting contact requests.",
                ephemeral=True,
            )

            return

        existing = await db.fetchrow(
            """
            SELECT id
            FROM looking_for_messages
            WHERE post_id = $1
              AND sender_id = $2
              AND status = 'pending'
            LIMIT 1
            """,
            value_from_row(
                post,
                "id",
            ),
            interaction.user.id,
        )

        if existing:

            await interaction.response.send_message(
                "You already have a pending request for this post.",
                ephemeral=True,
            )

            return

        await interaction.response.send_modal(
            ContactRequestModal(
                value_from_row(
                    post,
                    "id",
                )
            )
        )

    @discord.ui.button(
        label="Edit",
        emoji="✏️",
        style=discord.ButtonStyle.secondary,
        custom_id="looking_for:edit_post",
    )
    async def edit_post(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        post = await get_post_by_message_id(
            interaction.message.id
        )

        if not post:
            return

        if value_from_row(
            post,
            "user_id",
        ) != interaction.user.id:

            await interaction.response.send_message(
                "Only the owner of this post can edit it.",
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            "Choose what you'd like to edit:",
            view=EditPostFieldView(
                interaction.user.id,
                value_from_row(
                    post,
                    "id",
                ),
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Close",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="looking_for:close_post",
    )
    async def close_post_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        post = await get_post_by_message_id(
            interaction.message.id
        )

        if not post:
            return

        if value_from_row(
            post,
            "user_id",
        ) != interaction.user.id:

            await interaction.response.send_message(
                "Only the owner of this post can close it.",
                ephemeral=True,
            )

            return

        post_id = value_from_row(
            post,
            "id",
        )

        await close_looking_for_post(
            post_id
        )

        embed = await build_post_embed(
            interaction.guild,
            post,
        )

        embed.title = (
            "🔒 CLOSED • "
            + embed.title
        )

        embed.description = (
            "This Looking For post has been closed.\n\n"
            + (embed.description or "")
        )

        await interaction.response.edit_message(
            embed=embed,
            view=None,
        )

    @discord.ui.button(
        label="Report",
        emoji="🚩",
        style=discord.ButtonStyle.secondary,
        custom_id="looking_for:report_post",
    )
    async def report_post(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        post = await get_post_by_message_id(
            interaction.message.id
        )

        if not post:
            return

        await interaction.response.send_modal(
            ReportPostModal(
                value_from_row(
                    post,
                    "id",
                ),
                value_from_row(
                    post,
                    "user_id",
                ),
            )
        )


# ==================================================
# CONTACT REQUEST
# ==================================================

class ContactRequestModal(
    discord.ui.Modal,
    title="Send A Private Introduction",
):

    introduction = discord.ui.TextInput(
        label="Your introduction",
        placeholder=(
            "Tell them a little about yourself and why "
            "you're interested in their post."
        ),
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1500,
    )

    def __init__(
        self,
        post_id: int,
    ):

        super().__init__()

        self.post_id = post_id

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        post = await get_looking_for_post(
            self.post_id
        )

        if not post:

            await interaction.response.send_message(
                "That post no longer exists.",
                ephemeral=True,
            )

            return

        recipient_id = value_from_row(
            post,
            "user_id",
        )

        request = await db.fetchrow(
            """
            INSERT INTO looking_for_messages (
                post_id,
                guild_id,
                sender_id,
                recipient_id,
                message,
                status
            )
            VALUES ($1, $2, $3, $4, $5, 'pending')
            RETURNING *
            """,
            self.post_id,
            interaction.guild.id,
            interaction.user.id,
            recipient_id,
            self.introduction.value,
        )

        request_id = value_from_row(
            request,
            "id",
        )

        recipient = interaction.guild.get_member(
            recipient_id
        )

        if recipient is None:

            try:
                recipient = await interaction.guild.fetch_member(
                    recipient_id
                )
            except Exception:
                recipient = None

        if recipient is None:

            await interaction.response.send_message(
                "I couldn't find that member.",
                ephemeral=True,
            )

            return

        category = value_from_row(
            post,
            "looking_for_role",
        )

        category_label = CATEGORY_LABELS.get(
            category,
            category.title(),
        )

        embed = discord.Embed(
            title="💌 New Looking For Request",
            description=(
                "Someone is interested in your "
                f"**{category_label}** post.\n\n"
                "Their identity will stay private unless "
                "you accept the request."
            ),
        )

        embed.add_field(
            name="Their Introduction",
            value=field_text(
                self.introduction.value,
            ),
            inline=False,
        )

        embed.set_footer(
            text=(
                "Accept to reveal each other • "
                "Decline to quietly close the request"
            )
        )

        view = discord.ui.View(
            timeout=None
        )

        accept = discord.ui.Button(
            label="Accept",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=(
                f"looking_for_accept:{request_id}"
            ),
        )

        decline = discord.ui.Button(
            label="Decline",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
            custom_id=(
                f"looking_for_decline:{request_id}"
            ),
        )

        view.add_item(
            accept
        )

        view.add_item(
            decline
        )

        try:

            await recipient.send(
                embed=embed,
                view=view,
            )

        except discord.Forbidden:

            await db.execute(
                """
                UPDATE looking_for_messages
                SET status = 'failed',
                    responded_at = NOW()
                WHERE id = $1
                """,
                request_id,
            )

            await interaction.response.send_message(
                (
                    "I couldn't DM that member, so your "
                    "request wasn't delivered."
                ),
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            (
                "💌 Your introduction has been sent privately.\n\n"
                "They can accept or decline without you "
                "having to DM them directly."
            ),
            ephemeral=True,
        )


# ==================================================
# REPORT
# ==================================================

class ReportPostModal(
    discord.ui.Modal,
    title="Report Looking For Post",
):

    reason = discord.ui.TextInput(
        label="Why are you reporting this post?",
        placeholder=(
            "Please explain what staff should review."
        ),
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(
        self,
        post_id: int,
        reported_user_id: int,
    ):

        super().__init__()

        self.post_id = post_id
        self.reported_user_id = reported_user_id

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        await create_looking_for_report(
            post_id=self.post_id,
            guild_id=interaction.guild.id,
            reporter_id=interaction.user.id,
            reported_user_id=self.reported_user_id,
            reason=self.reason.value,
        )

        # Try to send the report to the server log channel too.
        try:

            settings = await interaction.client.db.get_guild_settings(
                interaction.guild.id
            )

            log_channel_id = value_from_row(
                settings,
                "log_channel",
            )

            if log_channel_id:

                channel = interaction.guild.get_channel(
                    log_channel_id
                )

                if channel:

                    embed = discord.Embed(
                        title="🚩 Looking For Report",
                    )

                    embed.add_field(
                        name="Post ID",
                        value=str(
                            self.post_id
                        ),
                        inline=True,
                    )

                    embed.add_field(
                        name="Reported Member",
                        value=f"<@{self.reported_user_id}>",
                        inline=True,
                    )

                    embed.add_field(
                        name="Reporter",
                        value=interaction.user.mention,
                        inline=True,
                    )

                    embed.add_field(
                        name="Reason",
                        value=field_text(
                            self.reason.value,
                        ),
                        inline=False,
                    )

                    await channel.send(
                        embed=embed
                    )

        except Exception as error:

            print(
                f"⚠️ Could not send Looking For report to log: {error}"
            )

        await interaction.response.send_message(
            (
                "🚩 Your report has been submitted privately "
                "for staff review."
            ),
            ephemeral=True,
        )


# ==================================================
# CATEGORY SELECT
# ==================================================

class LookingForCategorySelect(
    discord.ui.Select
):

    def __init__(self):

        super().__init__(
            placeholder="What are you looking for?",
            min_values=1,
            max_values=len(
                CATEGORY_OPTIONS
            ),
            options=CATEGORY_OPTIONS,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        self.view.selected_categories = list(
            self.values
        )

        selected_lines = []

        for category in self.values:

            emoji = CATEGORY_EMOJIS.get(
                category,
                "💌",
            )

            label = CATEGORY_LABELS.get(
                category,
                category.title(),
            )

            selected_lines.append(
                f"{emoji} **{label}**"
            )

        embed = discord.Embed(
            title="💌 Create A Looking For Post",
            description=(
                "You've selected:\n\n"
                + "\n".join(
                    selected_lines
                )
                + "\n\n"
                "If you selected more than one, Pillow Pal "
                "will make a separate post for each section.\n\n"
                "Press **Continue** when you're ready."
            ),
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self.view,
        )


class LookingForCategoryView(
    discord.ui.View
):

    def __init__(
        self,
        user_id: int,
    ):

        super().__init__(
            timeout=300
        )

        self.user_id = user_id
        self.selected_categories = []

        self.add_item(
            LookingForCategorySelect()
        )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "This form belongs to someone else.",
                ephemeral=True,
            )

            return False

        return True

    @discord.ui.button(
        label="Continue",
        emoji="➡️",
        style=discord.ButtonStyle.success,
    )
    async def continue_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.selected_categories:

            await interaction.response.send_message(
                "Select at least one option first.",
                ephemeral=True,
            )

            return

        state = LookingForCreationState(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            categories=self.selected_categories,
        )

        await interaction.response.send_modal(
            LookingForAboutModal(
                state
            )
        )


# ==================================================
# MAIN PANEL
# ==================================================

class LookingForPanelView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Create Looking For Post",
        emoji="💌",
        style=discord.ButtonStyle.primary,
        custom_id="looking_for:create_post",
    )
    async def create_post(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "This can only be used inside the server.",
                ephemeral=True,
            )

            return

        settings = await get_looking_for_settings(
            interaction.guild.id
        )

        if not settings:

            await interaction.response.send_message(
                "The Looking For system hasn't been configured yet.",
                ephemeral=True,
            )

            return

        if not value_from_row(
            settings,
            "enabled",
            True,
        ):

            await interaction.response.send_message(
                "The Looking For system is currently disabled.",
                ephemeral=True,
            )

            return

        category_channels = (
            await get_all_looking_for_category_channels(
                interaction.guild.id
            )
        )

        if not category_channels:

            await interaction.response.send_message(
                "The Looking For destination channels aren't configured.",
                ephemeral=True,
            )

            return

        embed = discord.Embed(
            title="💌 Create A Looking For Post",
            description=(
                "Choose what you're looking for below.\n\n"
                "You can choose **more than one** option.\n\n"
                "If you select multiple options, you'll fill "
                "the main form in once and Pillow Pal will "
                "create separate drafts for each section."
            ),
        )

        await interaction.response.send_message(
            embed=embed,
            view=LookingForCategoryView(
                interaction.user.id
            ),
            ephemeral=True,
        )


# ==================================================
# MAIN COG
# ==================================================

class LookingFor(
    commands.Cog
):

    def __init__(
        self,
        bot,
    ):

        self.bot = bot

    async def cog_load(
        self
    ):

        # Makes the permanent public buttons survive restarts.
        self.bot.add_view(
            LookingForPanelView()
        )

        self.bot.add_view(
            ActiveLookingForView()
        )

    # ==================================================
    # CONTACT ACCEPT / DECLINE LISTENER
    # ==================================================

    @commands.Cog.listener()
    async def on_interaction(
        self,
        interaction: discord.Interaction,
    ):

        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get(
            "custom_id",
            "",
        )

        if custom_id.startswith(
            "looking_for_accept:"
        ):

            request_id = int(
                custom_id.split(
                    ":",
                    1,
                )[1]
            )

            await self.handle_contact_response(
                interaction,
                request_id,
                accepted=True,
            )

        elif custom_id.startswith(
            "looking_for_decline:"
        ):

            request_id = int(
                custom_id.split(
                    ":",
                    1,
                )[1]
            )

            await self.handle_contact_response(
                interaction,
                request_id,
                accepted=False,
            )

    async def handle_contact_response(
        self,
        interaction: discord.Interaction,
        request_id: int,
        accepted: bool,
    ):

        request = await db.fetchrow(
            """
            SELECT *
            FROM looking_for_messages
            WHERE id = $1
            """,
            request_id,
        )

        if not request:

            await interaction.response.send_message(
                "That request no longer exists.",
                ephemeral=True,
            )

            return

        recipient_id = value_from_row(
            request,
            "recipient_id",
        )

        if interaction.user.id != recipient_id:

            await interaction.response.send_message(
                "This request isn't for you.",
                ephemeral=True,
            )

            return

        status = value_from_row(
            request,
            "status",
        )

        if status != "pending":

            await interaction.response.send_message(
                "You've already responded to this request.",
                ephemeral=True,
            )

            return

        sender_id = value_from_row(
            request,
            "sender_id",
        )

        if accepted:

            await db.execute(
                """
                UPDATE looking_for_messages
                SET status = 'accepted',
                    responded_at = NOW()
                WHERE id = $1
                """,
                request_id,
            )

            sender = self.bot.get_user(
                sender_id
            )

            if sender is None:

                try:
                    sender = await self.bot.fetch_user(
                        sender_id
                    )
                except Exception:
                    sender = None

            if sender:

                try:

                    await sender.send(
                        (
                            "💌 **Your Looking For request was accepted!**\n\n"
                            f"You can now connect with "
                            f"**{interaction.user}** "
                            f"(<@{interaction.user.id}>)."
                        )
                    )

                except discord.Forbidden:
                    pass

            embed = discord.Embed(
                title="✅ Request Accepted",
                description=(
                    "You've accepted the request.\n\n"
                    f"The person who contacted you is "
                    f"**{sender}** (<@{sender_id}>).\n\n"
                    "Pillow Pal has also told them that "
                    "you accepted."
                ),
            )

            await interaction.response.edit_message(
                embed=embed,
                view=None,
            )

        else:

            await db.execute(
                """
                UPDATE looking_for_messages
                SET status = 'declined',
                    responded_at = NOW()
                WHERE id = $1
                """,
                request_id,
            )

            sender = self.bot.get_user(
                sender_id
            )

            if sender is None:

                try:
                    sender = await self.bot.fetch_user(
                        sender_id
                    )
                except Exception:
                    sender = None

            if sender:

                try:

                    await sender.send(
                        (
                            "💌 Your Looking For request wasn't "
                            "accepted this time.\n\n"
                            "Their identity remains private."
                        )
                    )

                except discord.Forbidden:
                    pass

            embed = discord.Embed(
                title="✖️ Request Declined",
                description=(
                    "The request has been closed.\n\n"
                    "The other member hasn't been given "
                    "your identity or direct contact details."
                ),
            )

            await interaction.response.edit_message(
                embed=embed,
                view=None,
            )

    # ==================================================
    # SETUP COMMAND
    # ==================================================

    @app_commands.command(
        name="lookingforsetup",
        description="Configure the Looking For system.",
    )
    @app_commands.describe(
        panel_channel="Channel containing the Looking For panel",
        selfies_channel="Channel Pillow Pal searches for latest selfies",
        caregiver_channel="Looking For A Caregiver posts",
        little_channel="Looking For A Little posts",
        pet_channel="Looking For A Pet posts",
        handler_channel="Looking For A Handler posts",
        partner_channel="Looking For A Partner posts",
        friends_channel="Looking For Friends posts",
    )
    async def lookingforsetup(
        self,
        interaction: discord.Interaction,
        panel_channel: discord.TextChannel,
        selfies_channel: discord.TextChannel,
        caregiver_channel: discord.TextChannel,
        little_channel: discord.TextChannel,
        pet_channel: discord.TextChannel,
        handler_channel: discord.TextChannel,
        partner_channel: discord.TextChannel,
        friends_channel: discord.TextChannel,
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )

            return

        if not interaction.user.guild_permissions.administrator:

            await interaction.response.send_message(
                "You need Administrator permission to use this command.",
                ephemeral=True,
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        guild_id = interaction.guild.id

        # --------------------------------------------------
        # SAVE GENERAL SETTINGS
        # --------------------------------------------------

        await save_looking_for_settings(
            guild_id=guild_id,
            panel_channel_id=panel_channel.id,
            selfies_channel_id=selfies_channel.id,
        )

        # --------------------------------------------------
        # SAVE DESTINATION CHANNELS
        # --------------------------------------------------

        channels = {
            "caregiver": caregiver_channel.id,
            "little": little_channel.id,
            "pet": pet_channel.id,
            "handler": handler_channel.id,
            "partner": partner_channel.id,
            "friends": friends_channel.id,
        }

        for category, channel_id in channels.items():

            await set_looking_for_category_channel(
                guild_id=guild_id,
                category=category,
                channel_id=channel_id,
            )

        # --------------------------------------------------
        # CREATE PANEL
        # --------------------------------------------------

        panel_embed = discord.Embed(
            title="💌 Looking For",
            description=(
                "Looking to meet someone in Pillow Palace?\n\n"
                "Create a profile-style Looking For post using "
                "the button below.\n\n"
                "🍼 **Looking For A Caregiver**\n"
                "🧸 **Looking For A Little**\n"
                "🐾 **Looking For A Pet**\n"
                "🦴 **Looking For A Handler**\n"
                "💕 **Looking For A Partner**\n"
                "🤝 **Looking For Friends**\n\n"
                "You can select more than one option. Pillow Pal "
                "will create a separate editable draft for each "
                "section you choose.\n\n"
                "💌 Contact between members can be handled privately "
                "through Pillow Pal, so you don't have to open your "
                "DMs to everyone."
            ),
        )

        panel_embed.set_footer(
            text="Pillow Palace • Strictly SFW • 18+"
        )

        panel_message = await panel_channel.send(
            embed=panel_embed,
            view=LookingForPanelView(),
        )

        await save_looking_for_settings(
            guild_id=guild_id,
            panel_message_id=panel_message.id,
        )

        # --------------------------------------------------
        # CONFIRMATION
        # --------------------------------------------------

        confirmation = discord.Embed(
            title="✅ Looking For Setup Complete",
            description=(
                "Everything has been saved and the panel "
                "has been posted."
            ),
        )

        confirmation.add_field(
            name="💌 Panel",
            value=panel_channel.mention,
            inline=False,
        )

        confirmation.add_field(
            name="📸 Selfies",
            value=selfies_channel.mention,
            inline=False,
        )

        confirmation.add_field(
            name="🍼 Caregiver",
            value=caregiver_channel.mention,
            inline=True,
        )

        confirmation.add_field(
            name="🧸 Little",
            value=little_channel.mention,
            inline=True,
        )

        confirmation.add_field(
            name="🐾 Pet",
            value=pet_channel.mention,
            inline=True,
        )

        confirmation.add_field(
            name="🦴 Handler",
            value=handler_channel.mention,
            inline=True,
        )

        confirmation.add_field(
            name="💕 Partner",
            value=partner_channel.mention,
            inline=True,
        )

        confirmation.add_field(
            name="🤝 Friends",
            value=friends_channel.mention,
            inline=True,
        )

        await interaction.followup.send(
            embed=confirmation,
            ephemeral=True,
        )


# ==================================================
# COG SETUP
# ==================================================

async def setup(
    bot
):

    await bot.add_cog(
        LookingFor(bot)
    )
