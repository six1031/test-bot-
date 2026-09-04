# cogs/looking_for.py

import discord
from discord.ext import commands
from discord import app_commands

from database.looking_for import (
    get_looking_for_settings,
    save_looking_for_settings,
    set_looking_for_category_channel,
    get_all_looking_for_category_channels,
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


# ==================================================
# CATEGORY SELECT
# ==================================================

class LookingForCategorySelect(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(
                label="Caregiver",
                value="caregiver",
                emoji="🍼",
                description="Create a post looking for a caregiver.",
            ),
            discord.SelectOption(
                label="Little",
                value="little",
                emoji="🧸",
                description="Create a post looking for a little.",
            ),
            discord.SelectOption(
                label="Pet",
                value="pet",
                emoji="🐾",
                description="Create a post looking for a pet.",
            ),
            discord.SelectOption(
                label="Handler",
                value="handler",
                emoji="🦴",
                description="Create a post looking for a handler.",
            ),
            discord.SelectOption(
                label="Partner",
                value="partner",
                emoji="💕",
                description="Create a post looking for a partner.",
            ),
            discord.SelectOption(
                label="Friends",
                value="friends",
                emoji="🤝",
                description="Create a post looking for friends.",
            ),
        ]

        super().__init__(
            placeholder="What are you looking for?",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        selected = list(self.values)

        self.view.selected_categories = selected

        pretty_categories = []

        for category in selected:

            emoji = CATEGORY_EMOJIS.get(
                category,
                "•",
            )

            label = CATEGORY_LABELS.get(
                category,
                category.title(),
            )

            pretty_categories.append(
                f"{emoji} {label}"
            )

        embed = discord.Embed(
            title="🧸 Looking For Post",
            description=(
                "You've selected:\n\n"
                + "\n".join(pretty_categories)
                + "\n\n"
                "Each selection will become its own post.\n"
                "You'll only need to fill in the main information once, "
                "then you'll be able to edit each individual post before "
                "it is published."
            ),
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self.view,
        )


# ==================================================
# CATEGORY SELECT VIEW
# ==================================================

class LookingForCategoryView(discord.ui.View):

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
    ) -> bool:

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "This Looking For form belongs to someone else.",
                ephemeral=True,
            )

            return False

        return True

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.success,
        emoji="➡️",
    )
    async def continue_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.selected_categories:

            await interaction.response.send_message(
                "Please select at least one option first.",
                ephemeral=True,
            )

            return

        categories = ", ".join(
            CATEGORY_LABELS.get(
                category,
                category.title(),
            )
            for category in self.selected_categories
        )

        await interaction.response.send_message(
            (
                f"✅ Selected: **{categories}**\n\n"
                "The next step will open the Looking For form."
            ),
            ephemeral=True,
        )


# ==================================================
# MAIN PANEL
# ==================================================

class LookingForPanelView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Create Looking For Post",
        style=discord.ButtonStyle.primary,
        emoji="💌",
        custom_id="looking_for:create_post",
    )
    async def create_post(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "This button can only be used inside the server.",
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

        if not settings.get(
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
                (
                    "The Looking For destination channels "
                    "haven't been configured yet."
                ),
                ephemeral=True,
            )

            return

        embed = discord.Embed(
            title="💌 Create a Looking For Post",
            description=(
                "Choose what you're looking for below.\n\n"
                "You can select **more than one** option.\n\n"
                "If you select multiple options, Pillow Pal will create "
                "a separate post for each section so you don't need to "
                "start the whole form again."
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

class LookingFor(commands.Cog):

    def __init__(
        self,
        bot,
    ):

        self.bot = bot

    async def cog_load(self):

        # Persistent panel button survives bot restarts
        self.bot.add_view(
            LookingForPanelView()
        )

    # --------------------------------------------------
    # SETUP COMMAND
    # --------------------------------------------------

    @app_commands.command(
        name="lookingforsetup",
        description="Configure the Looking For system.",
    )
    @app_commands.describe(
        panel_channel="Channel containing the Looking For panel",
        selfies_channel="Channel Pillow Pal searches for the latest selfie",
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

        # --------------------------------------------------
        # ADMIN CHECK
        # --------------------------------------------------

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
        # SAVE CATEGORY CHANNELS
        # --------------------------------------------------

        category_channels = {
            "caregiver": caregiver_channel.id,
            "little": little_channel.id,
            "pet": pet_channel.id,
            "handler": handler_channel.id,
            "partner": partner_channel.id,
            "friends": friends_channel.id,
        }

        for category, channel_id in category_channels.items():

            await set_looking_for_category_channel(
                guild_id=guild_id,
                category=category,
                channel_id=channel_id,
            )

        # --------------------------------------------------
        # PANEL
        # --------------------------------------------------

        panel_embed = discord.Embed(
            title="💌 Looking For",
            description=(
                "Looking to meet someone in Pillow Palace?\n\n"
                "Use the button below to create your Looking For post.\n\n"
                "You can create posts for:\n\n"
                "🍼 **Caregivers**\n"
                "🧸 **Littles**\n"
                "🐾 **Pets**\n"
                "🦴 **Handlers**\n"
                "💕 **Partners**\n"
                "🤝 **Friends**\n\n"
                "You can select multiple options and Pillow Pal will "
                "create a separate post for each one.\n\n"
                "Your posts can be edited before they're published."
            ),
        )

        panel_embed.set_footer(
            text="Pillow Palace • Strictly SFW • 18+"
        )

        panel_message = await panel_channel.send(
            embed=panel_embed,
            view=LookingForPanelView(),
        )

        # Save permanent panel message ID
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
                "The Looking For system has been configured."
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
# SETUP
# ==================================================

async def setup(bot):

    await bot.add_cog(
        LookingFor(bot)
    )
