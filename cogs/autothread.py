import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_PATH = "data/autothread_config.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "title_format": "{username} - {message}",
    "max_title_length": 50,
    "reply_message": None,
    "include_bots": False,
    "status_reactions": True,
    "slowmode": 0
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)


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

        # Validate max length
        try:
            max_len = int(self.max_title_length.value)
            if max_len < 1 or max_len > 100:
                raise ValueError
        except:
            return await interaction.response.send_message(
                "❌ Max title length must be between **1 and 100**.",
                ephemeral=True
            )

        # Save new values
        cfg["title_format"] = self.title_format.value
        cfg["max_title_length"] = max_len

        self.config[str(self.channel_id)] = cfg
        save_config(self.config)

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
        self.config = load_config()

    def get_channel_config(self, channel_id: int):
        return self.config.get(str(channel_id), DEFAULT_CONFIG.copy())

    # --------------------------------------------------
    # /autothread — main config command
    # --------------------------------------------------

    @app_commands.command(name="autothread", description="Configure auto-threading for a channel.")
    @app_commands.describe(
        channel_id="Channel ID to configure",
        enabled="Turn auto-threading ON or OFF",
        reply_message="Message to send inside the thread",
        include_bots="Create threads for bot messages?",
        slowmode="Slowmode in created threads (seconds)"
    )
    async def autothread(
        self,
        interaction: discord.Interaction,
        channel_id: str,
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

        try:
            chan_id_int = int(channel_id)
        except:
            return await interaction.response.send_message(
                "Channel ID must be a valid number.",
                ephemeral=True
            )

        cfg = self.get_channel_config(chan_id_int)

        if enabled is not None:
            cfg["enabled"] = enabled
        if reply_message is not None:
            cfg["reply_message"] = reply_message if reply_message.strip() else None
        if include_bots is not None:
            cfg["include_bots"] = include_bots
        if slowmode is not None:
            cfg["slowmode"] = max(0, slowmode)

        self.config[str(chan_id_int)] = cfg
        save_config(self.config)

        await interaction.response.send_message(
            f"✅ Auto-thread settings updated for <#{chan_id_int}>.",
            ephemeral=True
        )

    # --------------------------------------------------
    # /autothread-title — POP-UP MENU
    # --------------------------------------------------

    @app_commands.command(name="autothread-title", description="Open a pop-up menu to set the auto-thread title.")
    @app_commands.describe(channel_id="Channel ID to configure")
    async def autothread_title(self, interaction: discord.Interaction, channel_id: str):
        ADMIN_ROLE_ID = 1428444870766231622
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            return await interaction.response.send_message(
                "❌ You must have the **Admin** role to use this command.",
                ephemeral=True
            )

        try:
            chan_id_int = int(channel_id)
        except:
            return await interaction.response.send_message(
                "Channel ID must be a valid number.",
                ephemeral=True
            )

        modal = TitleFormatModal(chan_id_int, self.config)
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
