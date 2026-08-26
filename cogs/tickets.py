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

    def __init__(
        self,
        bot,
    ):
        self.bot = bot

    # ==================================================
    # PERMISSION HELPERS
    # ==================================================

    async def get_server_roles(
        self,
        guild: discord.Guild,
    ):
        """
        Load the configured Admin, Mod and Member roles.
        """

        settings = await self.bot.db.get_guild_settings(
            guild.id
        )

        if not settings:
            return None, None, None

        admin_role_id = settings.get(
            "admin_role"
        )

        # Compatibility fallback for older database data
        mod_role_id = (
            settings.get("mod_role")
            or settings.get("staff_role")
        )

        member_role_id = settings.get(
            "member_role"
        )

        admin_role = (
            guild.get_role(admin_role_id)
            if admin_role_id
            else None
        )

        mod_role = (
            guild.get_role(mod_role_id)
            if mod_role_id
            else None
        )

        member_role = (
            guild.get_role(member_role_id)
            if member_role_id
            else None
        )

        return (
            admin_role,
            mod_role,
            member_role,
        )

    async def is_admin(
        self,
        interaction: discord.Interaction,
    ):
        """
        True for Discord administrators OR
        members with the configured Admin role.
        """

        if interaction.guild is None:
            return False

        member = interaction.user

        if not isinstance(
            member,
            discord.Member,
        ):
            return False

        # Actual Discord Administrator permission
        if member.guild_permissions.administrator:
            return True

        admin_role, _, _ = (
            await self.get_server_roles(
                interaction.guild
            )
        )

        if (
            admin_role
            and admin_role in member.roles
        ):
            return True

        return False

    async def is_mod_or_admin(
        self,
        interaction: discord.Interaction,
    ):
        """
        True for:
        - Discord administrators
        - configured Admin role
        - configured Mod role

        Normal Member role does NOT count.
        """

        if interaction.guild is None:
            return False

        member = interaction.user

        if not isinstance(
            member,
            discord.Member,
        ):
            return False

        if member.guild_permissions.administrator:
            return True

        admin_role, mod_role, _ = (
            await self.get_server_roles(
                interaction.guild
            )
        )

        if (
            admin_role
            and admin_role in member.roles
        ):
            return True

        if (
            mod_role
            and mod_role in member.roles
        ):
            return True

        return False

    # ==================================================
    # RESTORE PERSISTENT BUTTONS
    # ==================================================

    async def cog_load(
        self,
    ):

        print(
            "🔄 Registering persistent ticket buttons..."
        )

        # --------------------------------------------------
        # PANEL BUTTONS
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
        # --------------------------------------------------

        try:

            panels = await get_panels()

            print(
                f"🎫 Found {len(panels)} saved ticket panel(s)."
            )

            for panel in panels:

                panel_type = panel[
                    "panel_type"
                ]

                message_id = panel[
                    "message_id"
                ]

                print(
                    (
                        "✅ Saved panel: "
                        f"{panel_type} "
                        f"(message {message_id})"
                    )
                )

        except Exception as e:

            print(
                f"⚠️ Could not read saved ticket panels: {e}"
            )

    # ==================================================
    # /TICKETSETUP
    # ==================================================

    @app_commands.command(
        name="ticketsetup",
        description="Set up the ticket system for this server.",
    )
    @app_commands.describe(
        ticket_category=(
            "Category where ticket channels will be created"
        ),
        verification_channel=(
            "Channel for verification tickets"
        ),
        reports_channel=(
            "Channel for report tickets"
        ),
        applications_channel=(
            "Channel for staff applications"
        ),
        contact_channel=(
            "Channel for contact staff tickets"
        ),
    )
    async def ticketsetup(
        self,
        interaction: discord.Interaction,
        ticket_category: discord.CategoryChannel,
        verification_channel: discord.TextChannel,
        reports_channel: discord.TextChannel,
        applications_channel: discord.TextChannel,
        contact_channel: discord.TextChannel,
    ):

        # --------------------------------------------------
        # ADMIN ONLY
        # --------------------------------------------------

        if not await self.is_admin(
            interaction
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Only the configured "
                        "**Admin role** can use "
                        "this command."
                    ),
                    ephemeral=True,
                )
            )

        await interaction.response.defer(
            ephemeral=True
        )

        guild = interaction.guild

        # --------------------------------------------------
        # LOAD MOD ROLE
        # --------------------------------------------------

        admin_role, mod_role, member_role = (
            await self.get_server_roles(
                guild
            )
        )

        if mod_role is None:

            return await (
                interaction.followup
                .send(
                    (
                        "❌ No **Mod role** has been "
                        "configured yet.\n\n"
                        "Run `/setup` and select "
                        "the Mod role first."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # SAVE TICKET CATEGORY
        # --------------------------------------------------

        await self.bot.db.upsert_guild_settings(
            guild_id=guild.id,
            ticket_category_id=(
                ticket_category.id
            ),
        )

        # ==================================================
        # VERIFICATION PANEL
        # ==================================================

        verification_embed = discord.Embed(
            title="🪪 Verification Tickets",
            description=(
                "Click the button below to "
                "open a verification ticket."
            ),
            colour=discord.Colour.green(),
        )

        verification_message = (
            await verification_channel.send(
                embed=verification_embed,
                view=VerificationTicketView(),
            )
        )

        await add_panel(
            guild.id,
            verification_channel.id,
            verification_message.id,
            "verification",
        )

        # ==================================================
        # REPORTS PANEL
        # ==================================================

        reports_embed = discord.Embed(
            title="⚠️ Report Tickets",
            description=(
                "Click the button below to "
                "open a report ticket."
            ),
            colour=discord.Colour.red(),
        )

        reports_message = (
            await reports_channel.send(
                embed=reports_embed,
                view=ReportsTicketView(),
            )
        )

        await add_panel(
            guild.id,
            reports_channel.id,
            reports_message.id,
            "reports",
        )

        # ==================================================
        # APPLICATIONS PANEL
        # ==================================================

        applications_embed = discord.Embed(
            title="📝 Staff Applications",
            description=(
                "Click the button below to "
                "open a staff application."
            ),
            colour=discord.Colour.blurple(),
        )

        applications_message = (
            await applications_channel.send(
                embed=applications_embed,
                view=ApplicationsTicketView(),
            )
        )

        await add_panel(
            guild.id,
            applications_channel.id,
            applications_message.id,
            "applications",
        )

        # ==================================================
        # CONTACT PANEL
        # ==================================================

        contact_embed = discord.Embed(
            title="💌 Contact Staff",
            description=(
                "Click the button below to "
                "contact the moderation team."
            ),
            colour=discord.Colour.blurple(),
        )

        contact_message = (
            await contact_channel.send(
                embed=contact_embed,
                view=ContactTicketView(),
            )
        )

        await add_panel(
            guild.id,
            contact_channel.id,
            contact_message.id,
            "contact",
        )

        # ==================================================
        # FINISHED
        # ==================================================

        await interaction.followup.send(
            (
                "✅ **Ticket system set up successfully!**\n\n"
                f"**Mod Role:** {mod_role.mention}\n"
                f"**Ticket Category:** "
                f"`{ticket_category.name}`\n\n"
                f"🪪 Verification: "
                f"{verification_channel.mention}\n"
                f"⚠️ Reports: "
                f"{reports_channel.mention}\n"
                f"📝 Applications: "
                f"{applications_channel.mention}\n"
                f"💌 Contact Staff: "
                f"{contact_channel.mention}"
            ),
            ephemeral=True,
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

        # --------------------------------------------------
        # MOD / ADMIN ONLY
        # --------------------------------------------------

        if not await self.is_mod_or_admin(
            interaction
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Only the configured "
                        "**Mod or Admin role** can "
                        "use this command."
                    ),
                    ephemeral=True,
                )
            )

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
            title=(
                f"🎫 {panel.title()} Tickets"
            ),
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

            message = (
                await interaction.channel.send(
                    embed=embed,
                    view=view,
                )
            )

        except discord.HTTPException:

            return await (
                interaction.followup
                .send(
                    (
                        "❌ I could not create "
                        "the ticket panel."
                    ),
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
                    "❌ Failed to save ticket panel "
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

async def setup(
    bot,
):

    await bot.add_cog(
        Tickets(bot)
    )
