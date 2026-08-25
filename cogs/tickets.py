import discord
from discord.ext import commands
from discord import app_commands

from database.tickets import (
    add_panel,
    get_panels,
)

from views.ticket_views import (
    VerificationTicketView,
    ReportsTicketView,
    ApplicationsTicketView,
    ContactTicketView,
    CloseTicketView,
)


# ==================================================
# PANEL VIEWS
# ==================================================

PANEL_VIEWS = {
    "verification": VerificationTicketView,
    "reports": ReportsTicketView,
    "applications": ApplicationsTicketView,
    "contact": ContactTicketView,
}


PANEL_CHOICES = [
    app_commands.Choice(
        name="Verification",
        value="verification",
    ),
    app_commands.Choice(
        name="Reports",
        value="reports",
    ),
    app_commands.Choice(
        name="Applications",
        value="applications",
    ),
    app_commands.Choice(
        name="Contact Staff",
        value="contact",
    ),
]


# ==================================================
# MAIN COG
# ==================================================

class Tickets(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ==================================================
    # RESTORE PERSISTENT BUTTONS
    # ==================================================

    async def cog_load(self):

        print(
            "🔄 Registering persistent ticket buttons..."
        )

        # --------------------------------------------------
        # PANEL BUTTONS
        #
        # These views have:
        #
        # timeout=None
        # fixed custom_id values
        #
        # Registering them here makes old panel buttons
        # work again after Railway redeploys.
        # --------------------------------------------------

        try:

            self.bot.add_view(
                VerificationTicketView()
            )

            self.bot.add_view(
                ReportsTicketView()
            )

            self.bot.add_view(
                ApplicationsTicketView()
            )

            self.bot.add_view(
                ContactTicketView()
            )

            print(
                "✅ Persistent ticket panel buttons registered."
            )

        except Exception as e:

            print(
                f"❌ Could not register ticket panel views: {e}"
            )

        # --------------------------------------------------
        # CLOSE TICKET BUTTON
        #
        # This is the SAME CloseTicketView used inside
        # views/ticket_views.py when a ticket is created.
        # --------------------------------------------------

        try:

            self.bot.add_view(
                CloseTicketView()
            )

            print(
                "✅ Persistent close-ticket button registered."
            )

        except Exception as e:

            print(
                f"❌ Could not register close-ticket view: {e}"
            )

        # --------------------------------------------------
        # CHECK SAVED PANELS
        #
        # The persistent views above are enough to restore
        # functionality.
        #
        # We still check PostgreSQL here so Railway logs
        # tell us how many ticket panels are saved.
        # --------------------------------------------------

        try:

            panels = await get_panels()

            print(
                f"🎫 Found {len(panels)} saved ticket panel(s)."
            )

            for panel in panels:

                panel_type = panel["panel_type"]
                message_id = panel["message_id"]

                print(
                    (
                        f"✅ Saved panel: "
                        f"{panel_type} "
                        f"(message {message_id})"
                    )
                )

        except Exception as e:

            print(
                f"⚠️ Could not read saved ticket panels: {e}"
            )

    # ==================================================
    # /TICKETPANEL
    # ==================================================

    @app_commands.command(
        name="ticketpanel",
        description="Create a ticket panel.",
    )
    @app_commands.describe(
        panel_type=(
            "Which panel would you like to create?"
        )
    )
    @app_commands.choices(
        panel_type=PANEL_CHOICES
    )
    async def ticketpanel(
        self,
        interaction: discord.Interaction,
        panel_type: app_commands.Choice[str],
    ):

        panel = panel_type.value

        view_class = PANEL_VIEWS.get(
            panel
        )

        if view_class is None:

            return await (
                interaction.response
                .send_message(
                    "❌ Invalid ticket panel type.",
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # CREATE PANEL
        # --------------------------------------------------

        embed = discord.Embed(
            title=f"🎫 {panel.title()} Tickets",
            description=(
                "Click the button below "
                "to open a ticket."
            ),
            colour=discord.Colour.blurple(),
        )

        view = view_class()

        await interaction.response.defer(
            ephemeral=True
        )

        # --------------------------------------------------
        # SEND PANEL
        # --------------------------------------------------

        try:

            message = await (
                interaction.channel.send(
                    embed=embed,
                    view=view,
                )
            )

        except discord.HTTPException:

            return await (
                interaction.followup
                .send(
                    "❌ I could not create the ticket panel.",
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # SAVE PANEL
        # --------------------------------------------------

        try:

            await add_panel(
                interaction.guild.id,
                interaction.channel.id,
                message.id,
                panel,
            )

        except Exception as e:

            print(
                (
                    f"❌ Failed to save ticket panel "
                    f"{message.id}: {e}"
                )
            )

            return await (
                interaction.followup
                .send(
                    (
                        "⚠️ The panel was created, "
                        "but I could not save it "
                        "to PostgreSQL."
                    ),
                    ephemeral=True,
                )
            )

        await (
            interaction.followup
            .send(
                "✅ Ticket panel created and saved.",
                ephemeral=True,
            )
        )


# ==================================================
# LOAD COG
# ==================================================

async def setup(bot):

    await bot.add_cog(
        Tickets(bot)
    )
