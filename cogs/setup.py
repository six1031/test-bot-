import discord
from discord import app_commands
from discord.ext import commands

class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="Configure the bot for your server."
    )
    @app_commands.describe(
        admin_role="Role that can use admin commands",
        marriage_channel="Channel for marriage commands",
        relationship_channel="Channel for relationship commands",
        ticket_category="Category for ticket creation",
        log_channel="Channel for bot logs"
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        admin_role: discord.Role = None,
        marriage_channel: discord.TextChannel = None,
        relationship_channel: discord.TextChannel = None,
        ticket_category: discord.CategoryChannel = None,
        log_channel: discord.TextChannel = None
    ):
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild.id

        # Save settings using your database helpers
        await self.bot.db.set_guild_settings(
            guild_id,
            admin_role.id if admin_role else None,
            marriage_channel.id if marriage_channel else None,
            relationship_channel.id if relationship_channel else None,
            ticket_category.id if ticket_category else None,
            log_channel.id if log_channel else None
        )

        embed = discord.Embed(
            title="Setup Complete",
            description="Your server settings have been saved.",
            color=discord.Color.green()
        )

        if admin_role:
            embed.add_field(name="Admin Role", value=admin_role.mention, inline=False)
        if marriage_channel:
            embed.add_field(name="Marriage Channel", value=marriage_channel.mention, inline=False)
        if relationship_channel:
            embed.add_field(name="Relationship Channel", value=relationship_channel.mention, inline=False)
        if ticket_category:
            embed.add_field(name="Ticket Category", value=ticket_category.name, inline=False)
        if log_channel:
            embed.add_field(name="Log Channel", value=log_channel.mention, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Setup(bot))
