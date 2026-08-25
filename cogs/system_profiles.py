import traceback
import discord

from discord.ext import commands
from discord import app_commands

from database.system_profiles import (
    init_system_profile_tables,
    set_system_profile_channel,
    get_system_profile_settings,
)


# ==================================================
# SYSTEM PROFILE COG
# ==================================================

class SystemProfiles(commands.Cog):

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
    # DATABASE STARTUP
    # ==================================================

    async def cog_load(
        self,
    ):

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
            "The channel where system profiles "
            "and alter panels will be posted"
        ),
    )
    async def configure(
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
                        "❌ You need "
                        "**Administrator** permission "
                        "to configure system profiles."
                    ),
                    ephemeral=True,
                )
            )

        guild = interaction.guild

        # --------------------------------------------------
        # CHECK BOT CAN USE CHANNEL
        # --------------------------------------------------

        bot_member = guild.me

        if bot_member is None:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I couldn't find my "
                        "server member account."
                    ),
                    ephemeral=True,
                )
            )

        permissions = (
            channel.permissions_for(
                bot_member
            )
        )

        if not permissions.view_channel:

            return await (
                interaction.response
                .send_message(
                    (
                        f"❌ I can't view "
                        f"{channel.mention}."
                    ),
                    ephemeral=True,
                )
            )

        if not permissions.send_messages:

            return await (
                interaction.response
                .send_message(
                    (
                        f"❌ I can't send messages in "
                        f"{channel.mention}."
                    ),
                    ephemeral=True,
                )
            )

        if not permissions.embed_links:

            return await (
                interaction.response
                .send_message(
                    (
                        f"❌ I need **Embed Links** "
                        f"in {channel.mention}."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # SAVE CHANNEL
        # --------------------------------------------------

        try:

            await set_system_profile_channel(
                guild_id=guild.id,
                channel_id=channel.id,
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I couldn't save the "
                        "System Profiles channel."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # SUCCESS
        # --------------------------------------------------

        embed = discord.Embed(
            title=(
                "🌸 System Profiles Configured"
            ),
            description=(
                "System profiles and their "
                "alter profile panels will be posted in:\n\n"
                f"{channel.mention}"
            ),
            colour=(
                discord.Colour.blurple()
            ),
        )

        embed.add_field(
            name="Normal Member Profiles",
            value=(
                "These stay completely separate "
                "and are not affected."
            ),
            inline=False,
        )

        embed.add_field(
            name="System Profiles",
            value=(
                "Each system will have one main "
                "profile message containing buttons "
                "to browse its alter profiles."
            ),
            inline=False,
        )

        await (
            interaction.response
            .send_message(
                embed=embed,
                ephemeral=True,
            )
        )

    # ==================================================
    # /SYSTEMPROFILE CHANNEL
    #
    # Lets admins check which channel is configured.
    # ==================================================

    @systemprofile.command(
        name="channel",
        description=(
            "Show the configured System Profiles channel."
        ),
    )
    async def show_channel(
        self,
        interaction: discord.Interaction,
    ):

        try:

            settings = (
                await get_system_profile_settings(
                    interaction.guild.id
                )
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ I couldn't load the "
                        "System Profiles settings."
                    ),
                    ephemeral=True,
                )
            )

        if (
            not settings
            or not settings.get(
                "profile_channel_id"
            )
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "⚠️ No System Profiles "
                        "channel has been configured yet.\n\n"
                        "Run `/systemprofile configure`."
                    ),
                    ephemeral=True,
                )
            )

        channel_id = (
            settings[
                "profile_channel_id"
            ]
        )

        channel = (
            interaction.guild.get_channel(
                channel_id
            )
        )

        if channel:

            message = (
                "🌸 System Profiles are configured "
                f"to post in {channel.mention}."
            )

        else:

            message = (
                "⚠️ A System Profiles channel is saved, "
                "but that channel no longer exists.\n\n"
                "Run `/systemprofile configure` again."
            )

        await (
            interaction.response
            .send_message(
                message,
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
        SystemProfiles(
            bot
        )
    )
