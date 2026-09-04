# cogs/looking_for.py

import discord
from discord.ext import commands
from discord import app_commands

from database.looking_for import (
    get_looking_for_settings,
    save_looking_for_settings,
)


class LookingFor(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # --------------------------------------------------
    # SETUP COMMAND
    # --------------------------------------------------

    @app_commands.command(
        name="lookingforsetup",
        description="Configure the Looking For system"
    )
    @app_commands.describe(
        panel_channel="Channel where the Looking For panel will go",
        posts_channel="Channel where Looking For posts will be published",
        selfies_channel="Channel Pillow Pal should search for selfies"
    )
    async def lookingforsetup(
        self,
        interaction: discord.Interaction,
        panel_channel: discord.TextChannel,
        posts_channel: discord.TextChannel,
        selfies_channel: discord.TextChannel,
    ):

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        # Admin only for now
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need Administrator permission to use this command.",
                ephemeral=True,
            )
            return

        await save_looking_for_settings(
            guild_id=interaction.guild.id,
            panel_channel_id=panel_channel.id,
            posts_channel_id=posts_channel.id,
            selfies_channel_id=selfies_channel.id,
        )

        embed = discord.Embed(
            title="🧸 Looking For Setup Saved",
            description=(
                "The Looking For system has been configured."
            ),
        )

        embed.add_field(
            name="Panel Channel",
            value=panel_channel.mention,
            inline=False,
        )

        embed.add_field(
            name="Posts Channel",
            value=posts_channel.mention,
            inline=False,
        )

        embed.add_field(
            name="Selfies Channel",
            value=selfies_channel.mention,
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(
        LookingFor(bot)
    )
