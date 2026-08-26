import discord

from database.tickets import (
    create_ticket,
    has_open_ticket,
    close_ticket as close_ticket_record,
)


# ==================================================
# ROLE HELPERS
# ==================================================

def get_ticket_roles(
    guild: discord.Guild,
    settings: dict,
):
    """
    Get configured Admin and Mod roles.

    staff_role is kept as a temporary fallback
    for servers that still have older saved data.
    """

    admin_role_id = settings.get(
        "admin_role"
    )

    mod_role_id = (
        settings.get("mod_role")
        or settings.get("staff_role")
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

    return admin_role, mod_role


def is_mod_or_admin(
    member: discord.Member,
    admin_role: discord.Role | None,
    mod_role: discord.Role | None,
):
    """
    Check whether a member can manage tickets.
    """

    # Real Discord Administrator permission
    if member.guild_permissions.administrator:
        return True

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
# CLOSE BUTTON
# ==================================================

class CloseTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="🔒 Close Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "❌ This button only works inside a server.",
                ephemeral=True,
            )

        settings = (
            await interaction.client.db.get_guild_settings(
                guild.id
            )
        )

        if not settings:

            return await interaction.response.send_message(
                (
                    "❌ Server roles are not set up yet. "
                    "Run `/setup` first."
                ),
                ephemeral=True,
            )

        admin_role, mod_role = (
            get_ticket_roles(
                guild,
                settings,
            )
        )

        # --------------------------------------------------
        # MOD ROLE REQUIRED
        # --------------------------------------------------

        if (
            admin_role is None
            and mod_role is None
        ):

            return await interaction.response.send_message(
                (
                    "❌ Admin/Mod roles are not set up yet. "
                    "Run `/setup` first."
                ),
                ephemeral=True,
            )

        member = interaction.user

        if not isinstance(
            member,
            discord.Member,
        ):

            return await interaction.response.send_message(
                "❌ I couldn't find your server member account.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # ONLY MOD / ADMIN CAN CLOSE
        # --------------------------------------------------

        if not is_mod_or_admin(
            member,
            admin_role,
            mod_role,
        ):

            return await interaction.response.send_message(
                "❌ Only Mods or Admins can close tickets.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            "🗑 Closing ticket...",
            ephemeral=True,
        )

        # --------------------------------------------------
        # MARK CLOSED
        # --------------------------------------------------

        try:

            await close_ticket_record(
                interaction.channel.id
            )

        except Exception as e:

            print(
                (
                    "⚠️ Failed to mark ticket "
                    f"{interaction.channel.id} closed: {e}"
                )
            )

        # --------------------------------------------------
        # DELETE CHANNEL
        # --------------------------------------------------

        try:

            await interaction.channel.delete(
                reason=(
                    f"Ticket closed by {interaction.user}"
                )
            )

        except discord.Forbidden:

            print(
                "❌ Missing permission to delete ticket channel."
            )

        except discord.HTTPException as e:

            print(
                f"❌ Failed to delete ticket channel: {e}"
            )


# ==================================================
# BASE VIEW
# ==================================================

class BaseTicketView(discord.ui.View):

    ticket_type = ""
    button_label = ""
    button_emoji = ""

    def __init__(self):

        super().__init__(
            timeout=None
        )

    async def create_ticket(
        self,
        interaction: discord.Interaction,
    ):

        guild = interaction.guild

        if guild is None:

            return await interaction.response.send_message(
                "❌ Tickets can only be opened inside the server.",
                ephemeral=True,
            )

        member = interaction.user

        if not isinstance(
            member,
            discord.Member,
        ):

            return await interaction.response.send_message(
                "❌ I couldn't find your server member account.",
                ephemeral=True,
            )

        # ==================================================
        # LOAD SERVER SETTINGS
        # ==================================================

        settings = (
            await interaction.client.db.get_guild_settings(
                guild.id
            )
        )

        if not settings:

            return await interaction.response.send_message(
                (
                    "❌ This server has not been "
                    "set up yet. Run `/setup` first."
                ),
                ephemeral=True,
            )

        # ==================================================
        # TICKET CATEGORY
        # ==================================================

        if not settings.get(
            "ticket_category"
        ):

            return await interaction.response.send_message(
                (
                    "❌ Ticket category is not "
                    "set up yet. Run `/setup` first."
                ),
                ephemeral=True,
            )

        category = guild.get_channel(
            settings["ticket_category"]
        )

        if not isinstance(
            category,
            discord.CategoryChannel,
        ):

            return await interaction.response.send_message(
                "❌ Ticket category could not be found.",
                ephemeral=True,
            )

        # ==================================================
        # ADMIN + MOD ROLES
        # ==================================================

        admin_role, mod_role = (
            get_ticket_roles(
                guild,
                settings,
            )
        )

        if mod_role is None:

            return await interaction.response.send_message(
                (
                    "❌ Mod role is not set up yet. "
                    "Run `/setup` first."
                ),
                ephemeral=True,
            )

        # ==================================================
        # CHECK FOR EXISTING TICKET
        # ==================================================

        staff_member = is_mod_or_admin(
            member,
            admin_role,
            mod_role,
        )

        # Normal members can have one open ticket
        # of each type.
        #
        # Mods/Admins can open unlimited tickets.

        if not staff_member:

            if await has_open_ticket(
                guild.id,
                member.id,
                self.ticket_type,
            ):

                return await interaction.response.send_message(
                    (
                        "❌ You already have an open "
                        f"{self.ticket_type} ticket."
                    ),
                    ephemeral=True,
                )

        # ==================================================
        # CHANNEL PERMISSIONS
        # ==================================================

        overwrites = {
            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False,
                    send_messages=False,
                ),

            member:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                ),

            mod_role:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                ),
        }

        # --------------------------------------------------
        # ADMIN ROLE
        # --------------------------------------------------

        if (
            admin_role
            and admin_role != mod_role
        ):

            overwrites[
                admin_role
            ] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
            )

        # --------------------------------------------------
        # BOT
        # --------------------------------------------------

        bot_member = guild.me

        if bot_member:

            overwrites[
                bot_member
            ] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
            )

        # ==================================================
        # CHANNEL NAME
        # ==================================================

        safe_name = (
            member.display_name
            .lower()
            .replace(" ", "-")
        )

        safe_name = "".join(
            character
            for character in safe_name
            if (
                character.isalnum()
                or character == "-"
            )
        )

        if not safe_name:

            safe_name = str(
                member.id
            )

        channel_name = (
            f"{self.ticket_type}-{safe_name}"
        )[:100]

        # ==================================================
        # CREATE CHANNEL
        # ==================================================

        try:

            channel = (
                await category.create_text_channel(
                    name=channel_name,
                    topic=(
                        f"{self.ticket_type}:"
                        f"{member.id}"
                    ),
                    overwrites=overwrites,
                    reason=(
                        f"{self.ticket_type} ticket "
                        f"opened by {member}"
                    ),
                )
            )

        except discord.Forbidden:

            return await interaction.response.send_message(
                (
                    "❌ I don't have permission "
                    "to create ticket channels."
                ),
                ephemeral=True,
            )

        except discord.HTTPException as e:

            print(
                f"❌ Failed to create ticket channel: {e}"
            )

            return await interaction.response.send_message(
                "❌ I couldn't create your ticket.",
                ephemeral=True,
            )

        # ==================================================
        # BUILD EMBED
        # ==================================================

        embed = discord.Embed(
            title=(
                f"{self.button_emoji} "
                f"{self.button_label}"
            ),
            colour=discord.Colour.blurple(),
        )

        # ==================================================
        # VERIFICATION MESSAGE
        # ==================================================

        if (
            self.ticket_type
            == "verification"
        ):

            embed.description = (
                "Hi there — thank you for opening a "
                "verification ticket with us.\n"
                "To keep our community safe and comfy, "
                "we need you to answer a few questions "
                "and complete a quick age check.\n"
                "You may cover everything on your ID "
                "except your date of birth and your photo.\n"
                "Please answer all questions clearly so "
                "the moderation team can verify you properly.\n\n"

                "**Verification Questions:**\n"
                "1. How old are you right now?\n"
                "2. What brings you to our Little Space community?\n"
                "3. Are you joining as a regressor, caregiver, or supporter?\n"
                "4. Pick one server rule and explain it in your own words.\n"
                "5. Tell us one way you keep yourself safe online.\n"
                "6. What are your personal boundaries or things you're not comfy with?\n"
                "7. How do you prefer people to interact with you in the server?\n"
                "8. Is there anything else the moderation team should know about you?\n"
                "9. In your own words, do you see age regression as NSFW or SFW?\n\n"

                "**ID Requirement:**\n"
                "Please upload a photo of your ID with "
                "everything covered except your date of "
                "birth and your photo.\n"
                "This is only used for age verification "
                "and will never be shared outside the "
                "moderation team."
            )

        # ==================================================
        # REPORT MESSAGE
        # ==================================================

        elif (
            self.ticket_type
            == "reports"
        ):

            embed.description = (
                "Please explain:\n"
                "• Who are you reporting?\n"
                "• What happened?\n"
                "• When did it happen?\n"
                "• Evidence/screenshots"
            )

        # ==================================================
        # APPLICATION MESSAGE
        # ==================================================

        elif (
            self.ticket_type
            == "applications"
        ):

            embed.description = (
                "Thank you for applying!\n\n"
                "Please answer the staff "
                "application questions."
            )

        # ==================================================
        # CONTACT MESSAGE
        # ==================================================

        elif (
            self.ticket_type
            == "contact"
        ):

            embed.description = (
                "Tell us how we can help and "
                "a moderator will respond shortly."
            )

        # ==================================================
        # SEND TICKET MESSAGE
        # ==================================================

        try:

            await channel.send(
                member.mention,
                embed=embed,
                view=CloseTicketView(),
            )

        except discord.HTTPException as e:

            print(
                (
                    "⚠️ Ticket created but initial "
                    f"message failed: {e}"
                )
            )

        # ==================================================
        # SAVE TICKET
        # ==================================================

        try:

            await create_ticket(
                guild.id,
                channel.id,
                member.id,
                self.ticket_type,
            )

        except Exception as e:

            print(
                (
                    "❌ Failed to save ticket "
                    f"{channel.id}: {e}"
                )
            )

            try:

                await channel.delete(
                    reason=(
                        "Ticket database save failed"
                    )
                )

            except Exception:
                pass

            return await interaction.response.send_message(
                (
                    "❌ I couldn't save the ticket "
                    "to the database, so it was cancelled."
                ),
                ephemeral=True,
            )

        # ==================================================
        # SUCCESS
        # ==================================================

        await interaction.response.send_message(
            (
                f"✅ Ticket created: "
                f"{channel.mention}"
            ),
            ephemeral=True,
        )


# ==================================================
# VERIFICATION
# ==================================================

class VerificationTicketView(
    BaseTicketView
):

    ticket_type = "verification"

    button_label = (
        "Open Verification Ticket"
    )

    button_emoji = "🪪"

    @discord.ui.button(
        label="Open Verification Ticket",
        style=discord.ButtonStyle.success,
        emoji="🪪",
        custom_id="ticket_verification",
    )
    async def button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await self.create_ticket(
            interaction
        )


# ==================================================
# REPORTS
# ==================================================

class ReportsTicketView(
    BaseTicketView
):

    ticket_type = "reports"

    button_label = (
        "Open Report Ticket"
    )

    button_emoji = "⚠️"

    @discord.ui.button(
        label="Open Report Ticket",
        style=discord.ButtonStyle.danger,
        emoji="⚠️",
        custom_id="ticket_reports",
    )
    async def button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await self.create_ticket(
            interaction
        )


# ==================================================
# APPLICATIONS
# ==================================================

class ApplicationsTicketView(
    BaseTicketView
):

    ticket_type = "applications"

    button_label = (
        "Apply For Staff"
    )

    button_emoji = "📝"

    @discord.ui.button(
        label="Apply For Staff",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="ticket_applications",
    )
    async def button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await self.create_ticket(
            interaction
        )


# ==================================================
# CONTACT
# ==================================================

class ContactTicketView(
    BaseTicketView
):

    ticket_type = "contact"

    button_label = (
        "Contact Staff"
    )

    button_emoji = "💌"

    @discord.ui.button(
        label="Contact Staff",
        style=discord.ButtonStyle.secondary,
        emoji="💌",
        custom_id="ticket_contact",
    )
    async def button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await self.create_ticket(
            interaction
        )
