import discord

from database.tickets import (
    create_ticket,
    has_open_ticket,
)

STAFF_ROLE_ID = 1428444870766231622
TICKET_CATEGORY_ID = 1526141859213086841


# --------------------------------------------------
# CLOSE BUTTON
# --------------------------------------------------

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔒 Close Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        staff = interaction.guild.get_role(STAFF_ROLE_ID)

        if staff not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ Only staff can close tickets.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            "🗑 Closing ticket...",
            ephemeral=True,
        )

        await interaction.channel.delete()


# --------------------------------------------------
# BASE VIEW
# --------------------------------------------------

class BaseTicketView(discord.ui.View):

    ticket_type = ""
    button_label = ""
    button_emoji = ""

    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction: discord.Interaction):

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        if category is None:
            return await interaction.response.send_message(
                "❌ Ticket category not found.",
                ephemeral=True,
            )

        # STAFF BYPASS — staff can open unlimited tickets
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)

        if staff_role not in interaction.user.roles:
            # Users can only open ONE ticket per type
            if await has_open_ticket(interaction.user.id, self.ticket_type):
                return await interaction.response.send_message(
                    f"❌ You already have an open {self.ticket_type} ticket.",
                    ephemeral=True,
                )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            ),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            ),
        }

        channel = await category.create_text_channel(
            name=f"{self.ticket_type}-{interaction.user.name}",
            topic=f"{self.ticket_type}:{interaction.user.id}",
            overwrites=overwrites,
        )

        embed = discord.Embed(
            title=f"{self.button_emoji} {self.button_label}",
            colour=discord.Colour.blurple(),
        )

        # --------------------------------------------------
        # VERIFICATION MESSAGE
        # --------------------------------------------------
        if self.ticket_type == "verification":
            embed.description = (
                "Hi there — thank you for opening a verification ticket with us.\n"
                "To keep our community safe and comfy, we need you to answer a few questions and complete a quick age check.\n"
                "You may cover everything on your ID except your date of birth and your photo.\n"
                "Please answer all questions clearly so staff can verify you properly.\n\n"

                "**Verification Questions:**\n"
                "1. How old are you right now?\n"
                "2. What brings you to our Little Space community?\n"
                "3. Are you joining as a regressor, caregiver, or supporter?\n"
                "4. Pick one server rule and explain it in your own words.\n"
                "5. Tell us one way you keep yourself safe online.\n"
                "6. What are your personal boundaries or things you’re not comfy with?\n"
                "7. How do you prefer people to interact with you in the server?\n"
                "8. Is there anything else staff should know about you?\n"
                "9. In your own words, do you see age regression as NSFW or SFW?\n\n"

                "**ID Requirement:**\n"
                "Please upload a photo of your ID with everything covered except your date of birth and your photo.\n"
                "This is only used for age verification and will never be shared outside staff."
            )

        elif self.ticket_type == "reports":
            embed.description = (
                "Please explain:\n"
                "• Who are you reporting?\n"
                "• What happened?\n"
                "• When did it happen?\n"
                "• Evidence/screenshots"
            )

        elif self.ticket_type == "applications":
            embed.description = (
                "Thank you for applying!\n\n"
                "Please answer the staff application questions."
            )

        elif self.ticket_type == "contact":
            embed.description = (
                "Tell us how we can help and a staff member will respond shortly."
            )

        await channel.send(
            interaction.user.mention,
            embed=embed,
            view=CloseTicketView(),
        )

        await create_ticket(
            channel.id,
            interaction.user.id,
            self.ticket_type,
        )

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True,
        )


# --------------------------------------------------
# VERIFICATION
# --------------------------------------------------

class VerificationTicketView(BaseTicketView):

    ticket_type = "verification"
    button_label = "Open Verification Ticket"
    button_emoji = "🪪"

    @discord.ui.button(
        label="Open Verification Ticket",
        style=discord.ButtonStyle.success,
        emoji="🪪",
        custom_id="ticket_verification",
    )
    async def button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction)


# --------------------------------------------------
# REPORTS
# --------------------------------------------------

class ReportsTicketView(BaseTicketView):

    ticket_type = "reports"
    button_label = "Open Report Ticket"
    button_emoji = "⚠️"

    @discord.ui.button(
        label="Open Report Ticket",
        style=discord.ButtonStyle.danger,
        emoji="⚠️",
        custom_id="ticket_reports",
    )
    async def button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction)


# --------------------------------------------------
# APPLICATIONS
# --------------------------------------------------

class ApplicationsTicketView(BaseTicketView):

    ticket_type = "applications"
    button_label = "Apply For Staff"
    button_emoji = "📝"

    @discord.ui.button(
        label="Apply For Staff",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="ticket_applications",
    )
    async def button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction)


# --------------------------------------------------
# CONTACT
# --------------------------------------------------

class ContactTicketView(BaseTicketView):

    ticket_type = "contact"
    button_label = "Contact Staff"
    button_emoji = "💌"

    @discord.ui.button(
        label="Contact Staff",
        style=discord.ButtonStyle.secondary,
        emoji="💌",
        custom_id="ticket_contact",
    )
    async def button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction)
