import discord
from discord import app_commands
from discord.ext import commands

from database.autothreads import (
    add_autothread,
    add_autothread_config,
    get_all_autothreads,
    get_autothread_configs,
    remove_autothread,
    remove_autothread_config,
)


class AutothreadCog(commands.Cog):
    """Manage per-server automatic thread channels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --------------------------------------------------
    # /AUTOTHREADSETUP
    # --------------------------------------------------

    @app_commands.command(
        name="autothreadsetup",
        description="Set up or remove an automatic thread channel.",
    )
    @app_commands.describe(
        action="Choose whether to add, remove, or list autothread channels",
        channel="The channel to configure",
        archive_duration="Thread auto-archive time",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Add channel", value="add"),
            app_commands.Choice(name="Remove channel", value="remove"),
            app_commands.Choice(name="List channels", value="list"),
        ],
        archive_duration=[
            app_commands.Choice(name="1 Hour", value=60),
            app_commands.Choice(name="24 Hours", value=1440),
            app_commands.Choice(name="3 Days", value=4320),
            app_commands.Choice(name="7 Days", value=10080),
        ],
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def autothreadsetup(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        channel: discord.TextChannel | None = None,
        archive_duration: app_commands.Choice[int] | None = None,
    ):
        guild = interaction.guild

        # --------------------------------------------------
        # LIST
        # --------------------------------------------------

        if action.value == "list":
            rows = await get_autothread_configs(guild.id)

            if not rows:
                return await interaction.response.send_message(
                    "❌ No autothread channels are configured for this server.",
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

                lines.append(
                    f"• {channel_name} — "
                    f"{row['auto_archive_duration']} minutes"
                )

            embed = discord.Embed(
                title="🧵 Autothread Channels",
                description="\n".join(lines),
                colour=discord.Colour.blurple(),
            )

            return await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
            )

        # Add/remove requires a channel
        if channel is None:
            return await interaction.response.send_message(
                "❌ You need to select a channel.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # ADD
        # --------------------------------------------------

        if action.value == "add":

            duration = (
                archive_duration.value
                if archive_duration
                else 1440
            )

            await add_autothread_config(
                guild_id=guild.id,
                channel_id=channel.id,
                auto_archive_duration=duration,
            )

            return await interaction.response.send_message(
                (
                    f"✅ {channel.mention} is now an autothread channel.\n"
                    f"Threads will auto-archive after "
                    f"**{duration} minutes**."
                ),
                ephemeral=True,
            )

        # --------------------------------------------------
        # REMOVE
        # --------------------------------------------------

        if action.value == "remove":

            await remove_autothread_config(
                guild_id=guild.id,
                channel_id=channel.id,
            )

            return await interaction.response.send_message(
                f"✅ Removed autothreads from {channel.mention}.",
                ephemeral=True,
            )

    # --------------------------------------------------
    # AUTOMATIC THREAD CREATION
    # --------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

# NEW
        if message.author.id == self.bot.user.id:
            return

        if not message.guild:
            return

        if not isinstance(message.channel, discord.TextChannel):
            return

        configs = await get_autothread_configs(
            message.guild.id
        )

        config = next(
            (
                row
                for row in configs
                if row["channel_id"] == message.channel.id
            ),
            None,
        )

        if not config:
            return

        try:
            thread_name = message.content.strip()

            if not thread_name:
                thread_name = f"Thread by {message.author.display_name}"

            # Keep thread names within Discord's limit
            thread_name = thread_name[:100]

            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=config["auto_archive_duration"],
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
                f"⚠️ Failed to create autothread "
                f"in {message.channel.id}: {e}"
            )

    # --------------------------------------------------
    # THREAD CLEANUP
    # --------------------------------------------------

    @commands.Cog.listener()
    async def on_thread_delete(
        self,
        thread: discord.Thread,
    ):
        try:
            await remove_autothread(thread.id)

        except Exception as e:
            print(
                f"⚠️ Failed to remove deleted "
                f"autothread {thread.id}: {e}"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(AutothreadCog(bot))
