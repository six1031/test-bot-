import discord
from discord.ext import commands
from discord import app_commands

from database.autothreads import add_autothread

DEFAULT_CONFIG = {
    "enabled": False,
    "title_format": "{username} - {message}",
    "max_title_length": 50,
    "reply_message": None,
    "include_bots": False,
    "status_reactions": True,
    "slowmode": 0
}

# --------------------------------------------------
# MODAL POP-UP FOR TITLE INPUT
# --------------------------------------------------

class TitleFormatModal(discord.ui.Modal, title="Set Auto-Thread Title"):
    title_format = discord.ui.TextInput(
        label="Thread Title Format",
        placeholder="{username} - {message}",
        required=True
    )

    max_title_length = discord.ui.TextInput(
        label="Max Title Length (1–100)",
        placeholder="50",
        required=True
    )

    def __init__(self, channel_id: int, config: dict):
        super().__init__()
        self.channel_id = channel_id
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        cfg = self.config.get(str(self.channel_id), DEFAULT_CONFIG.copy())

        try:
            max_len = int(self.max_title_length.value)
            if max_len < 1 or max_len > 100:
                raise ValueError
        except:
            return await interaction.response.send_message(
                "❌ Max title length must be between **1 and 100**.",
                ephemeral=True
            )

        cfg["title_format"] = self.title_format.value
        cfg["max_title_length"] = max_len

        self.config[str(self.channel_id)] = cfg
        interaction.client.autothread_config = self.config

        await interaction.response.send_message(
            f"✅ Title settings updated for <#{self.channel_id}>.",
            ephemeral=True
        )


# --------------------------------------------------
# MAIN COG
# --------------------------------------------------

class Autothread(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.autothread_config = {}  # SQL replaces JSON

    def get_channel_config(self, channel_id: int):
        return self.bot.autothread_config.get(str(channel_id), DEFAULT_CONFIG.copy())

    # --------------------------------------------------
    # /autothread — main config command
    # --------------------------------------------------

    @app_commands.command(name="autothread", description="Configure auto-threading for a channel.")
    @app_commands.describe(
        channel="Channel to configure",
        enabled="Turn auto-threading ON or OFF",
        reply_message="Message to send inside the thread",
        include_bots="Create threads for bot messages?",
        slowmode="Slowmode in created threads (seconds)"
    )
    async def autothread(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        enabled: bool = None,
        reply_message: str = None,
        include_bots: bool = None,
        slowmode: int = None
    ):
        ADMIN_ROLE_ID = 1428444870766231622
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            return await interaction.response.send_message(
                "❌ You must have the **Admin** role to use this command.",
                ephemeral=True
            )

        cfg = self.get_channel_config(channel.id)

        if enabled is not None:
            cfg["enabled"] = enabled
        if reply_message is not None:
            cfg["reply_message"] = reply_message if reply_message.strip() else None
        if include_bots is not None:
            cfg["include_bots"] = include_bots
        if slowmode is not None:
            cfg["slowmode"] = max(0, slowmode)

        self.bot.autothread_config[str(channel.id)] = cfg

        await interaction.response.send_message(
            f"✅ Auto-thread settings updated for {channel.mention}.",
            ephemeral=True
        )

    # --------------------------------------------------
    # /autothread-title — POP-UP MENU
    # --------------------------------------------------

    @app_commands.command(name="autothread-title", description="Open a pop-up menu to set the auto-thread title.")
    @app_commands.describe(channel="Channel to configure")
    async def autothread_title(self, interaction: discord.Interaction, channel: discord.TextChannel):
        ADMIN_ROLE_ID = 1428444870766231622
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            return await interaction.response.send_message(
                "❌ You must have the **Admin** role to use this command.",
                ephemeral=True
            )

        modal = TitleFormatModal(channel.id, self.bot.autothread_config)
        await interaction.response.send_modal(modal)

    # --------------------------------------------------
    # Auto-thread listener
    # --------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return
        if message.author == self.bot.user:
            return

        cfg = self.get_channel_config(message.channel.id)

        if not cfg["enabled"]:
            return

        if message.author.bot and not cfg["include_bots"]:
            return

        username = message.author.display_name
        content = message.content if message.content else "(no content)"

        title = cfg["title_format"].replace("{username}", username).replace("{message}", content)
        if len(title) > cfg["max_title_length"]:
            title = title[:cfg["max_title_length"]]

        thread = await message.create_thread(
            name=title,
            auto_archive_duration=1440
        )

        # Store in SQL
        await add_autothread(
            thread_id=thread.id,
            parent_channel_id=message.channel.id,
            parent_message_id=message.id,
            thread_type=message.channel.id,  # store under the channel it belongs to
            owner_id=message.author.id
        )

        if cfg["slowmode"] > 0:
            try:
                await thread.edit(slowmode_delay=cfg["slowmode"])
            except:
                pass

        if cfg["reply_message"]:
            await thread.send(cfg["reply_message"])

        if cfg["status_reactions"]:
            try:
                await message.add_reaction("✅")
                await message.add_reaction("❌")
            except:
                pass


async def setup(bot):
    await bot.add_cog(Autothread(bot))
