import discord
from discord import app_commands
from discord.ext import commands

from database.autothreads import (
    add_autothread,
    add_autothread_config,
    get_autothread_config,
    get_autothread_configs,
    remove_autothread,
    remove_autothread_config,
    update_autothread_config,
)


# ==================================================
# HELPERS
# ==================================================

def build_thread_name(
    message: discord.Message,
    name_format: str,
):
    """
    Build the automatic thread name.

    Available placeholders:
    {message}
    {author}
    {channel}
    """

    # --------------------------------------------------
    # MESSAGE TEXT
    # --------------------------------------------------

    message_text = message.content.strip()

    # Bots often send embeds with no normal message text.
    # Try to use the embed title/description instead.
    if not message_text and message.embeds:

        for embed in message.embeds:

            if embed.title:
                message_text = embed.title.strip()
                break

            if embed.description:
                description = embed.description.strip()

                if description:
                    message_text = description.splitlines()[0]
                    break

    # Final fallback
    if not message_text:
        message_text = (
            f"Message from {message.author.display_name}"
        )

    # --------------------------------------------------
    # OTHER PLACEHOLDERS
    # --------------------------------------------------

    author_name = message.author.display_name

    channel_name = getattr(
        message.channel,
        "name",
        "channel",
    )

    # Default format
    if not name_format:
        name_format = "{message}"

    # --------------------------------------------------
    # REPLACE PLACEHOLDERS
    # --------------------------------------------------

    thread_name = name_format

    thread_name = thread_name.replace(
        "{message}",
        message_text,
    )

    thread_name = thread_name.replace(
        "{author}",
        author_name,
    )

    thread_name = thread_name.replace(
        "{channel}",
        channel_name,
    )

    # Remove accidental new lines / excessive spaces
    thread_name = " ".join(
        thread_name.split()
    )

    # Safety fallback
    if not thread_name:
        thread_name = (
            f"Thread by {author_name}"
        )

    # Discord thread-name limit
    return thread_name[:100]


# ==================================================
# AUTOTHREAD COG
# ==================================================

class AutothreadCog(commands.Cog):
    """Manage per-server automatic thread channels."""

    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot

    # ==================================================
    # /AUTOTHREADSETUP
    # ==================================================

    @app_commands.command(
        name="autothreadsetup",
        description="Set up, edit, remove, or list automatic thread channels.",
    )
    @app_commands.describe(
        action="Choose what you want to do",
        channel="The channel to configure",
        archive_duration="Thread auto-archive time",
        include_bots="Should messages from other bots create threads?",
        thread_name_format=(
            "Thread name format: {message}, {author}, or {channel}"
        ),
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(
                name="Add channel",
                value="add",
            ),
            app_commands.Choice(
                name="Edit channel",
                value="edit",
            ),
            app_commands.Choice(
                name="Remove channel",
                value="remove",
            ),
            app_commands.Choice(
                name="List channels",
                value="list",
            ),
        ],
        archive_duration=[
            app_commands.Choice(
                name="1 Hour",
                value=60,
            ),
            app_commands.Choice(
                name="24 Hours",
                value=1440,
            ),
            app_commands.Choice(
                name="3 Days",
                value=4320,
            ),
            app_commands.Choice(
                name="7 Days",
                value=10080,
            ),
        ],
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def autothreadsetup(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        channel: discord.TextChannel | None = None,
        archive_duration: app_commands.Choice[int] | None = None,
        include_bots: bool | None = None,
        thread_name_format: str | None = None,
    ):

        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True,
            )

        # ==================================================
        # LIST
        # ==================================================

        if action.value == "list":

            rows = await get_autothread_configs(
                guild.id
            )

            if not rows:
                return await interaction.response.send_message(
                    (
                        "❌ No autothread channels are "
                        "configured for this server."
                    ),
                    ephemeral=True,
                )

            lines = []

            for row in rows:

                configured_channel = guild.get_channel(
                    row["channel_id"]
                )

                channel_name = (
                    configured_channel.mention
                    if configured_channel
                    else f"`{row['channel_id']}`"
                )

                bots_text = (
                    "✅ Yes"
                    if row["include_bots"]
                    else "❌ No"
                )

                name_format = (
                    row["thread_name_format"]
                    or "{message}"
                )

                lines.append(
                    (
                        f"### {channel_name}\n"
                        f"🕒 **Archive:** "
                        f"{row['auto_archive_duration']} minutes\n"
                        f"🤖 **Bot messages:** {bots_text}\n"
                        f"🧵 **Thread name:** "
                        f"`{name_format}`"
                    )
                )

            embed = discord.Embed(
                title="🧵 Autothread Channels",
                description="\n\n".join(lines),
                colour=discord.Colour.blurple(),
            )

            return await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
            )

        # ==================================================
        # CHANNEL REQUIRED
        # ==================================================

        if channel is None:

            return await interaction.response.send_message(
                "❌ You need to select a channel.",
                ephemeral=True,
            )

        # ==================================================
        # ADD
        # ==================================================

        if action.value == "add":

            duration = (
                archive_duration.value
                if archive_duration
                else 1440
            )

            bots_enabled = (
                include_bots
                if include_bots is not None
                else True
            )

            name_format = (
                thread_name_format.strip()
                if thread_name_format
                else "{message}"
            )

            await add_autothread_config(
                guild_id=guild.id,
                channel_id=channel.id,
                auto_archive_duration=duration,
                include_bots=bots_enabled,
                thread_name_format=name_format,
            )

            bots_text = (
                "Yes"
                if bots_enabled
                else "No"
            )

            return await interaction.response.send_message(
                (
                    f"✅ {channel.mention} is now an "
                    f"autothread channel.\n\n"
                    f"🕒 **Auto archive:** "
                    f"{duration} minutes\n"
                    f"🤖 **Include bots:** "
                    f"{bots_text}\n"
                    f"🧵 **Thread name:** "
                    f"`{name_format}`"
                ),
                ephemeral=True,
            )

        # ==================================================
        # EDIT
        # ==================================================

        if action.value == "edit":

            current = await get_autothread_config(
                guild_id=guild.id,
                channel_id=channel.id,
            )

            if not current:

                return await interaction.response.send_message(
                    (
                        f"❌ {channel.mention} is not currently "
                        "an autothread channel.\n\n"
                        "Use **Add channel** first."
                    ),
                    ephemeral=True,
                )

            # At least one setting must be supplied
            if (
                archive_duration is None
                and include_bots is None
                and thread_name_format is None
            ):

                return await interaction.response.send_message(
                    (
                        "❌ Choose at least one setting to change:\n"
                        "• Archive duration\n"
                        "• Include bots\n"
                        "• Thread name format"
                    ),
                    ephemeral=True,
                )

            new_duration = (
                archive_duration.value
                if archive_duration
                else None
            )

            new_name_format = None

            if thread_name_format is not None:

                new_name_format = (
                    thread_name_format.strip()
                    or "{message}"
                )

            updated = await update_autothread_config(
                guild_id=guild.id,
                channel_id=channel.id,
                auto_archive_duration=new_duration,
                include_bots=include_bots,
                thread_name_format=new_name_format,
            )

            if not updated:

                return await interaction.response.send_message(
                    "❌ I couldn't update that autothread channel.",
                    ephemeral=True,
                )

            # Load the final saved settings
            config = await get_autothread_config(
                guild_id=guild.id,
                channel_id=channel.id,
            )

            bots_text = (
                "Yes"
                if config["include_bots"]
                else "No"
            )

            return await interaction.response.send_message(
                (
                    f"✅ Updated autothreads for "
                    f"{channel.mention}.\n\n"
                    f"🕒 **Auto archive:** "
                    f"{config['auto_archive_duration']} minutes\n"
                    f"🤖 **Include bots:** "
                    f"{bots_text}\n"
                    f"🧵 **Thread name:** "
                    f"`{config['thread_name_format']}`"
                ),
                ephemeral=True,
            )

        # ==================================================
        # REMOVE
        # ==================================================

        if action.value == "remove":

            current = await get_autothread_config(
                guild_id=guild.id,
                channel_id=channel.id,
            )

            if not current:

                return await interaction.response.send_message(
                    (
                        f"❌ {channel.mention} isn't currently "
                        "an autothread channel."
                    ),
                    ephemeral=True,
                )

            await remove_autothread_config(
                guild_id=guild.id,
                channel_id=channel.id,
            )

            return await interaction.response.send_message(
                (
                    f"✅ Removed autothreads from "
                    f"{channel.mention}."
                ),
                ephemeral=True,
            )

    # ==================================================
    # AUTOMATIC THREAD CREATION
    # ==================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message,
    ):

        # --------------------------------------------------
        # NEVER REACT TO OUR OWN BOT
        # --------------------------------------------------

        if (
            self.bot.user
            and message.author.id
            == self.bot.user.id
        ):
            return

        # --------------------------------------------------
        # SERVER MESSAGES ONLY
        # --------------------------------------------------

        if not message.guild:
            return

        # --------------------------------------------------
        # NORMAL TEXT CHANNELS ONLY
        # --------------------------------------------------

        if not isinstance(
            message.channel,
            discord.TextChannel,
        ):
            return

        # --------------------------------------------------
        # GET CHANNEL CONFIG
        # --------------------------------------------------

        config = await get_autothread_config(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
        )

        if not config:
            return

        # --------------------------------------------------
        # BOT MESSAGE SETTING
        # --------------------------------------------------

        if (
            message.author.bot
            and not config["include_bots"]
        ):
            return

        # --------------------------------------------------
        # BUILD THREAD NAME
        # --------------------------------------------------

        thread_name = build_thread_name(
            message,
            config["thread_name_format"],
        )

        # --------------------------------------------------
        # CREATE THREAD
        # --------------------------------------------------

        try:

            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=(
                    config[
                        "auto_archive_duration"
                    ]
                ),
            )

            await add_autothread(
                thread_id=thread.id,
                guild_id=message.guild.id,
                parent_channel_id=message.channel.id,
                parent_message_id=message.id,
                thread_type=0,
                owner_id=message.author.id,
            )

        except Exception as e:

            print(
                (
                    "⚠️ Failed to create autothread "
                    f"in {message.channel.id}: {e}"
                )
            )

    # ==================================================
    # THREAD CLEANUP
    # ==================================================

    @commands.Cog.listener()
    async def on_thread_delete(
        self,
        thread: discord.Thread,
    ):

        try:

            await remove_autothread(
                thread.id
            )

        except Exception as e:

            print(
                (
                    "⚠️ Failed to remove deleted "
                    f"autothread {thread.id}: {e}"
                )
            )


# ==================================================
# LOAD COG
# ==================================================

async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        AutothreadCog(bot)
    )
