import discord
from discord.ext import commands
from discord import app_commands

from database.tickets import (
    add_panel,
    get_panels,
)

from views.ticket_registry import PANEL_VIEWS
from views.ticket_views import (
    VerificationTicketView,
    ReportsTicketView,
    ApplicationsTicketView,
    ContactTicketView,
)

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

TICKET_CATEGORY_ID = 1526141859213086841   # ACTIVE TICKETS CATEGORY
STAFF_ROLE_ID = 1428444870766231622        # STAFF ROLE


# --------------------------------------------------
# CLOSE BUTTON
# --------------------------------------------------

class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔒 Close Ticket",
        style=discord.ButtonStyle.red,
        custom_id="close_ticket_button"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)

        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ Only staff can close tickets.",
                ephemeral=True
            )

        await interaction.channel.delete()
        
PANEL_VIEWS = {
    "verification": VerificationTicketView,
    "reports": ReportsTicketView,
    "applications": ApplicationsTicketView,
    "contact": ContactTicketView,
}


PANEL_CHOICES = [
    app_commands.Choice(name="Verification", value="verification"),
    app_commands.Choice(name="Reports", value="reports"),
    app_commands.Choice(name="Applications", value="applications"),
    app_commands.Choice(name="Contact Staff", value="contact"),
]


# --------------------------------------------------
# MAIN COG
# --------------------------------------------------

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        panels = await get_panels()

        for panel in panels:
            guild = self.bot.get_guild(panel["guild_id"])

            if guild is None:
                continue

            channel = guild.get_channel(panel["channel_id"])

            if channel is None:
                continue

            try:
                message = await channel.fetch_message(panel["message_id"])
            except discord.NotFound:
                continue

            panel_type = panel["panel_type"]

            if panel_type not in PANEL_VIEWS:
                continue

            try:
                await message.edit(
                    view=PANEL_VIEWS[panel_type]()
                )
            except Exception as e:
                print(f"Failed to restore panel {panel['message_id']}: {e}")

    @app_commands.command(
        name="ticketpanel",
        description="Create a ticket panel."
    )
    @app_commands.describe(
        panel_type="Which panel would you like to create?"
    )
    @app_commands.choices(panel_type=PANEL_CHOICES)
    async def ticketpanel(
        self,
        interaction: discord.Interaction,
        panel_type: app_commands.Choice[str],
    ):

        panel = panel_type.value

        embed = discord.Embed(
            title=f"🎫 {panel.title()} Tickets",
            description="Click the button below to open a ticket.",
            colour=discord.Colour.blurple(),
        )

        view = PANEL_VIEWS[panel]()

        await interaction.response.defer(ephemeral=True)

        msg = await interaction.channel.send(
            embed=embed,
            view=view,
        )

        await interaction.followup.send(
            "✅ Ticket panel created.",
            ephemeral=True,
        )

        await add_panel(
            interaction.guild.id,
            interaction.channel.id,
            msg.id,
            panel,
        )
        await add_panel(
            interaction.guild.id,
            interaction.channel.id,
            msg.id,
            panel,
        )


async def setup(bot):
    await bot.add_cog(Tickets(bot))
