# cogs/tickets.py

import traceback

import discord
from discord.ext import commands

from database.tickets import (
    create_ticket,
    has_open_ticket,
    close_ticket as close_ticket_record,
)


# ==================================================
# HELPERS
# ==================================================

async def get_ticket_roles(
    bot,
    guild: discord.Guild,
):
    """
    Return the configured Admin and Mod roles.

    mod_role is preferred, with staff_role kept as a
    backwards-compatible fallback.
    """

    settings = await bot.db.get_guild_settings(
        guild.id
    )

    if not settings:
        return (
            None,
            None,
            None,
        )

    admin_role_id = settings.get(
        "admin_role"
    )

    mod_role_id = (
        settings.get("mod_role")
        or settings.get("staff_role")
    )

    admin_role = (
        guild.get_role(
            admin_role_id
        )
        if admin_role_id
        else None
    )

    mod_role = (
        guild.get_role(
            mod_role_id
        )
        if mod_role_id
        else None
    )

    return (
        settings,
        admin_role,
        mod_role,
    )


async def is_ticket_staff(
    bot,
    guild: discord.Guild,
    member: discord.Member,
) -> bool:
    """
    Allow:
    - Discord Administrator
    - configured Admin role
    - configured Mod role
    """

    if member.guild_permissions.administrator:
        return True

    (
        _,
        admin_role,
        mod_role,
    ) = await get_ticket_roles(
        bot,
        guild,
    )

    return bool(
        (
            admin_role
            and admin_role in member.roles
        )
        or (
            mod_role
            and mod_role in member.roles
        )
    )


# ==================================================
# CLOSE BUTTON
# ==================================================

class CloseTicketView(
    discord.ui.View
):

    def __init__(
        self,
    ):
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
        member = interaction.user

        if (
            guild is None
            or not isinstance(
                member,
                discord.Member,
            )
        ):
            return await interaction.response.send_message(
                "❌ This button can only be used in a server.",
                ephemeral=True,
            )

        try:
            allowed = await is_ticket_staff(
                interaction.client,
                guild,
                member,
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't check the ticket staff roles.",
                ephemeral=True,
            )

        if not allowed:
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can close tickets.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            "🗑 Closing ticket...",
            ephemeral=True,
        )

        try:
            await close_ticket_record(
                interaction.channel.id
            )

        except Exception:
            traceback.print_exc()

        try:
            await interaction.channel.delete(
                reason=(
                    f"Ticket closed by "
                    f"{member} ({member.id})"
                )
            )

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            traceback.print_exc()


# ==================================================
# BASE TICKET VIEW
# ==================================================

class BaseTicketView(
    discord.ui.View
):

    ticket_type = ""
    button_label = ""
    button_emoji = ""

    def __init__(
        self,
    ):
        super().__init__(
            timeout=None
        )

    async def create_ticket(
        self,
        interaction: discord.Interaction,
    ):
        guild = interaction.guild
        opener = interaction.user

        if (
            guild is None
            or not isinstance(
                opener,
                discord.Member,
            )
        ):
            return await interaction.response.send_message(
                "❌ Tickets can only be opened inside a server.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # LOAD SERVER SETTINGS + STAFF ROLES
        # --------------------------------------------------

        try:
            (
                settings,
                admin_role,
                mod_role,
            ) = await get_ticket_roles(
                interaction.client,
                guild,
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ I couldn't load the server ticket settings.",
                ephemeral=True,
            )

        if not settings:
            return await interaction.response.send_message(
                "❌ This server has not been set up yet. Run `/setup` first.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # TICKET CATEGORY
        # --------------------------------------------------

        category_id = settings.get(
            "ticket_category"
        )

        if not category_id:
            return await interaction.response.send_message(
                "❌ Ticket category is not set up yet. Run `/setup` first.",
                ephemeral=True,
            )

        category = guild.get_channel(
            category_id
        )

        if not isinstance(
            category,
            discord.CategoryChannel,
        ):
            return await interaction.response.send_message(
                "❌ The configured ticket category could not be found.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # STAFF CHECK
        #
        # Admins / Mods may open unlimited tickets.
        # Normal members are limited to one open ticket
        # of each ticket type.
        # --------------------------------------------------

        is_staff = (
            opener.guild_permissions.administrator
            or (
                admin_role
                and admin_role in opener.roles
            )
            or (
                mod_role
                and mod_role in opener.roles
            )
        )

        if not is_staff:
            try:
                already_open = await has_open_ticket(
                    guild.id,
                    opener.id,
                    self.ticket_type,
                )

            except Exception:
                traceback.print_exc()

                return await interaction.response.send_message(
                    "❌ I couldn't check your existing tickets.",
                    ephemeral=True,
                )

            if already_open:
                return await interaction.response.send_message(
                    (
                        f"❌ You already have an open "
                        f"{self.ticket_type} ticket."
                    ),
                    ephemeral=True,
                )

        # --------------------------------------------------
        # CHANNEL PERMISSIONS
        #
        # Every created ticket explicitly allows:
        # - ticket opener
        # - configured Admin role
        # - configured Mod role
        # - bot
        #
        # This means Mods can see every ticket even when
        # @everyone cannot view the Tickets category.
        # --------------------------------------------------

        overwrites = {
            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False,
                ),

            opener:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                ),
        }

        if admin_role:
            overwrites[
                admin_role
            ] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )

        if (
            mod_role
            and (
                not admin_role
                or mod_role.id != admin_role.id
            )
        ):
            overwrites[
                mod_role
            ] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )

        bot_member = (
            guild.me
            or guild.get_member(
                interaction.client.user.id
            )
        )

        if bot_member:
            overwrites[
                bot_member
            ] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True,
            )

        # --------------------------------------------------
        # CREATE CHANNEL
        # --------------------------------------------------

        safe_name = (
            opener.name
            .lower()
            .replace(" ", "-")
        )

        channel_name = (
            f"{self.ticket_type}-{safe_name}"
        )[:100]

        try:
            channel = await category.create_text_channel(
                name=channel_name,
                topic=(
                    f"{self.ticket_type}:"
                    f"{opener.id}"
                ),
                overwrites=overwrites,
                reason=(
                    f"{self.ticket_type.title()} "
                    f"ticket opened by "
                    f"{opener} ({opener.id})"
                ),
            )

        except discord.Forbidden:
            return await interaction.response.send_message(
                (
                    "❌ I couldn't create the ticket channel. "
                    "Check my **Manage Channels** permission."
                ),
                ephemeral=True,
            )

        except discord.HTTPException:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ Discord rejected the ticket creation. Please try again.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # TICKET MESSAGE
        # --------------------------------------------------

        embed = discord.Embed(
            title=(
                f"{self.button_emoji} "
                f"{self.button_label}"
            ),
            colour=discord.Colour.blurple(),
        )

        if self.ticket_type == "verification":
            embed.description = (
                "Hi there — thank you for opening a verification ticket with us.\n"
                "To keep our community safe and comfy, we need you to answer a "
                "few questions and complete a quick age check.\n"
                "You may cover everything on your ID except your date of birth "
                "and your photo.\n"
                "Please answer all questions clearly so staff can verify you "
                "properly.\n\n"

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
                "Please upload a photo of your ID with everything covered except "
                "your date of birth and your photo.\n"
                "This is only used for age verification and will never be shared "
                "outside staff."
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

        try:
            await channel.send(
                opener.mention,
                embed=embed,
                view=CloseTicketView(),
                allowed_mentions=discord.AllowedMentions(
                    users=True,
                    roles=False,
                    everyone=False,
                ),
            )

            await create_ticket(
                guild.id,
                channel.id,
                opener.id,
                self.ticket_type,
            )

        except Exception:
            traceback.print_exc()

            try:
                await channel.delete(
                    reason=(
                        "Ticket setup failed after channel creation"
                    )
                )
            except Exception:
                pass

            return await interaction.response.send_message(
                "❌ I couldn't finish creating the ticket.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True,
        )


# ==================================================
# VERIFICATION
# ==================================================

class VerificationTicketView(
    BaseTicketView
):

    ticket_type = "verification"
    button_label = "Open Verification Ticket"
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
    button_label = "Open Report Ticket"
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
    button_label = "Apply For Staff"
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
    button_label = "Contact Staff"
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


# ==================================================
# COG
# ==================================================

class Tickets(
    commands.Cog
):

    def __init__(
        self,
        bot,
    ):
        self.bot = bot

    async def cog_load(
        self,
    ):
        # Persistent views must be registered after restart.
        self.bot.add_view(
            CloseTicketView()
        )

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
            "🎫 Ticket persistent views loaded."
        )


async def setup(
    bot,
):
    await bot.add_cog(
        Tickets(
            bot
        )
    )
