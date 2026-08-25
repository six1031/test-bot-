import discord
from discord.ext import commands
from discord import app_commands

from database.tickets import add_panel

from views.ticket_views import (
    VerificationTicketView,
    ReportsTicketView,
    ApplicationsTicketView,
    ContactTicketView,
)


class TicketSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="ticketsetup",
        description="Set up the ticket system for this server.",
    )
    @app_commands.describe(
        staff_role="The role that can access and close tickets",
        ticket_category="The category where ticket channels will be created",
        verification_channel="Channel for the verification ticket panel",
        reports_channel="Channel for the reports ticket panel",
        applications_channel="Channel for the applications ticket panel",
        contact_channel="Channel for the contact staff ticket panel",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketsetup(
        self,
        interaction: discord.Interaction,
        staff_role: discord.Role,
        ticket_category: discord.CategoryChannel,
        verification_channel: discord.TextChannel,
        reports_channel: discord.TextChannel,
        applications_channel: discord.TextChannel,
        contact_channel: discord.TextChannel,
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild

        # --------------------------------------------------
        # SAVE TICKET SETTINGS
        # --------------------------------------------------

        await self.bot.db.upsert_guild_settings(
            guild_id=guild.id,
            staff_role_id=staff_role.id,
            ticket_category_id=ticket_category.id,
        )

        # --------------------------------------------------
        # VERIFICATION PANEL
        # --------------------------------------------------

        verification_embed = discord.Embed(
            title="🪪 Verification Tickets",
            description=(
                "Click the button below to open a verification ticket."
            ),
            colour=discord.Colour.green(),
        )

        verification_message = await verification_channel.send(
            embed=verification_embed,
            view=VerificationTicketView(),
        )

        await add_panel(
            guild.id,
            verification_channel.id,
            verification_message.id,
            "verification",
        )

        # --------------------------------------------------
        # REPORTS PANEL
        # --------------------------------------------------

        reports_embed = discord.Embed(
            title="⚠️ Report Tickets",
            description=(
                "Click the button below to open a report ticket."
            ),
            colour=discord.Colour.red(),
        )

        reports_message = await reports_channel.send(
            embed=reports_embed,
            view=ReportsTicketView(),
        )

        await add_panel(
            guild.id,
            reports_channel.id,
            reports_message.id,
            "reports",
        )

        # --------------------------------------------------
        # APPLICATIONS PANEL
        # --------------------------------------------------

        applications_embed = discord.Embed(
            title="📝 Staff Applications",
            description=(
                "Click the button below to open a staff application."
            ),
            colour=discord.Colour.blurple(),
        )

        applications_message = await applications_channel.send(
            embed=applications_embed,
            view=ApplicationsTicketView(),
        )

        await add_panel(
            guild.id,
            applications_channel.id,
            applications_message.id,
            "applications",
        )

        # --------------------------------------------------
        # CONTACT PANEL
        # --------------------------------------------------

        contact_embed = discord.Embed(
            title="💌 Contact Staff",
            description=(
                "Click the button below to contact the staff team."
            ),
            colour=discord.Colour.blurple(),
        )

        contact_message = await contact_channel.send(
            embed=contact_embed,
            view=ContactTicketView(),
        )

        await add_panel(
            guild.id,
            contact_channel.id,
            contact_message.id,
            "contact",
        )

        # --------------------------------------------------
        # FINISHED
        # --------------------------------------------------

        await interaction.followup.send(
            (
                "✅ **Ticket system set up successfully!**\n\n"
                f"**Staff Role:** {staff_role.mention}\n"
                f"**Ticket Category:** `{ticket_category.name}`\n\n"
                f"🪪 Verification: {verification_channel.mention}\n"
                f"⚠️ Reports: {reports_channel.mention}\n"
                f"📝 Applications: {applications_channel.mention}\n"
                f"💌 Contact Staff: {contact_channel.mention}"
            ),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(TicketSetup(bot))
