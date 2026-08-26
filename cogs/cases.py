# cogs/cases.py

import re
import traceback

import discord

from discord import app_commands
from discord.ext import commands

from database.cases import (
    add_case_entry,
    clear_warning,
    count_case_entries,
    delete_member_case_location,
    get_all_member_cases,
    get_case_entries,
    get_case_entry,
    get_case_settings,
    get_latest_case_entry,
    get_member_case,
    init_case_tables,
    save_member_case,
    set_case_channel,
)


# ==================================================
# HELPERS
# ==================================================

def trim_text(
    text: str,
    limit: int,
) -> str:
    text = str(
        text
    ).strip()

    if len(text) <= limit:
        return text

    return (
        text[: max(0, limit - 1)]
        + "…"
    )


def safe_thread_name(
    member: discord.Member,
) -> str:
    name = (
        member.display_name
        or member.name
        or "member"
    )

    name = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "-",
        name,
    )

    name = re.sub(
        r"-+",
        "-",
        name,
    ).strip(
        "-_"
    )

    if not name:
        name = "member"

    return (
        f"case-{name}-{member.id}"
    )[:100]


def entry_label(
    entry_type: str,
) -> str:
    labels = {
        "warning": "⚠️ WARNING",
        "note": "📝 STAFF NOTE",
        "timeout": "⏱️ TIMEOUT",
        "kick": "👢 KICK",
        "ban": "🔨 BAN",
    }

    return labels.get(
        entry_type,
        f"📌 {entry_type.upper()}",
    )


# ==================================================
# MODALS
# ==================================================

class WarningModal(
    discord.ui.Modal,
    title="Add Warning",
):

    reason = discord.ui.TextInput(
        label="Warning reason",
        placeholder="Why is this member being warned?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    def __init__(
        self,
        cog,
        guild_id: int,
        member_id: int,
    ):
        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.guild_id = guild_id
        self.member_id = member_id

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        if not await self.cog.is_staff(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use this.",
                ephemeral=True,
            )

        guild = interaction.guild

        if (
            guild is None
            or guild.id != self.guild_id
        ):
            return await interaction.response.send_message(
                "❌ I couldn't find this server.",
                ephemeral=True,
            )

        member = guild.get_member(
            self.member_id
        )

        if member is None:
            return await interaction.response.send_message(
                "❌ That member is no longer in the server.",
                ephemeral=True,
            )

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            entry = await self.cog.add_warning(
                member=member,
                staff=interaction.user,
                reason=str(
                    self.reason.value
                ),
            )

        except Exception as exc:
            traceback.print_exc()

            return await interaction.followup.send(
                f"❌ I couldn't add the warning: {exc}",
                ephemeral=True,
            )

        await interaction.followup.send(
            (
                f"✅ Warning **#{entry['id']}** added "
                f"to {member.mention}'s case."
            ),
            ephemeral=True,
        )


class NoteModal(
    discord.ui.Modal,
    title="Add Staff Note",
):

    note = discord.ui.TextInput(
        label="Staff note",
        placeholder="Add a private staff note about this member.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1500,
    )

    def __init__(
        self,
        cog,
        guild_id: int,
        member_id: int,
    ):
        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.guild_id = guild_id
        self.member_id = member_id

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        if not await self.cog.is_staff(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use this.",
                ephemeral=True,
            )

        guild = interaction.guild

        if (
            guild is None
            or guild.id != self.guild_id
        ):
            return await interaction.response.send_message(
                "❌ I couldn't find this server.",
                ephemeral=True,
            )

        member = guild.get_member(
            self.member_id
        )

        if member is None:
            return await interaction.response.send_message(
                "❌ That member is no longer in the server.",
                ephemeral=True,
            )

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            entry = await self.cog.add_note(
                member=member,
                staff=interaction.user,
                note=str(
                    self.note.value
                ),
            )

        except Exception as exc:
            traceback.print_exc()

            return await interaction.followup.send(
                f"❌ I couldn't add the note: {exc}",
                ephemeral=True,
            )

        await interaction.followup.send(
            (
                f"✅ Staff note **#{entry['id']}** added "
                f"to {member.mention}'s case."
            ),
            ephemeral=True,
        )


class ClearWarningModal(
    discord.ui.Modal,
    title="Clear Warning",
):

    warning_id = discord.ui.TextInput(
        label="Warning case number",
        placeholder="Example: 42",
        required=True,
        max_length=20,
    )

    def __init__(
        self,
        cog,
        guild_id: int,
        member_id: int,
    ):
        super().__init__(
            timeout=300
        )

        self.cog = cog
        self.guild_id = guild_id
        self.member_id = member_id

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        if not await self.cog.is_staff(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use this.",
                ephemeral=True,
            )

        value = str(
            self.warning_id.value
        ).strip()

        if not value.isdigit():
            return await interaction.response.send_message(
                "❌ Enter the warning number only.",
                ephemeral=True,
            )

        warning_id = int(
            value
        )

        entry = await get_case_entry(
            warning_id
        )

        if (
            not entry
            or entry["guild_id"] != self.guild_id
            or entry["member_id"] != self.member_id
            or entry["entry_type"] != "warning"
            or not entry["active"]
        ):
            return await interaction.response.send_message(
                "❌ I couldn't find an active warning with that number for this member.",
                ephemeral=True,
            )

        await interaction.response.defer(
            ephemeral=True
        )

        cleared = await self.cog.clear_member_warning(
            warning_id=warning_id,
            guild_id=self.guild_id,
            staff=interaction.user,
        )

        if not cleared:
            return await interaction.followup.send(
                "❌ That warning could not be cleared.",
                ephemeral=True,
            )

        await interaction.followup.send(
            f"✅ Warning **#{warning_id}** cleared.",
            ephemeral=True,
        )


# ==================================================
# PERSISTENT MEMBER CASE PANEL
# ==================================================

class CasePanelView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
        guild_id: int,
        member_id: int,
    ):
        super().__init__(
            timeout=None
        )

        self.cog = cog
        self.guild_id = guild_id
        self.member_id = member_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        guild = interaction.guild

        if (
            guild is None
            or guild.id != self.guild_id
        ):
            await interaction.response.send_message(
                "❌ This case belongs to another server.",
                ephemeral=True,
            )
            return False

        if not await self.cog.is_staff(
            interaction
        ):
            await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use case panels.",
                ephemeral=True,
            )
            return False

        return True

    @discord.ui.button(
        label="Warn",
        emoji="⚠️",
        style=discord.ButtonStyle.danger,
        custom_id="member_case:warn",
    )
    async def warn_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(
            WarningModal(
                cog=self.cog,
                guild_id=self.guild_id,
                member_id=self.member_id,
            )
        )

    @discord.ui.button(
        label="Add Note",
        emoji="📝",
        style=discord.ButtonStyle.primary,
        custom_id="member_case:add_note",
    )
    async def note_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(
            NoteModal(
                cog=self.cog,
                guild_id=self.guild_id,
                member_id=self.member_id,
            )
        )

    @discord.ui.button(
        label="History",
        emoji="📖",
        style=discord.ButtonStyle.secondary,
        custom_id="member_case:history",
    )
    async def history_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        embed = await self.cog.build_history_embed(
            guild=interaction.guild,
            member_id=self.member_id,
            limit=15,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Refresh",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="member_case:refresh",
    )
    async def refresh_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        embed = await self.cog.build_case_embed(
            guild=interaction.guild,
            member_id=self.member_id,
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self,
        )

    @discord.ui.button(
        label="Clear Warning",
        emoji="🧹",
        style=discord.ButtonStyle.secondary,
        custom_id="member_case:clear_warning",
        row=1,
    )
    async def clear_warning_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(
            ClearWarningModal(
                cog=self.cog,
                guild_id=self.guild_id,
                member_id=self.member_id,
            )
        )


# ==================================================
# CASES COG
# ==================================================

class Cases(
    commands.Cog
):

    def __init__(
        self,
        bot,
    ):
        self.bot = bot

    # ==================================================
    # LOAD / RESTORE
    # ==================================================

    async def cog_load(
        self,
    ):
        await init_case_tables()

        restored = 0

        try:
            cases = await get_all_member_cases()

        except Exception:
            traceback.print_exc()
            return

        for case in cases:
            message_id = case[
                "panel_message_id"
            ]

            if not message_id:
                continue

            try:
                self.bot.add_view(
                    CasePanelView(
                        cog=self,
                        guild_id=case[
                            "guild_id"
                        ],
                        member_id=case[
                            "member_id"
                        ],
                    ),
                    message_id=message_id,
                )

                restored += 1

            except Exception:
                traceback.print_exc()

        print(
            f"🛡️ Restored {restored} member case panel(s)."
        )

    # ==================================================
    # PERMISSIONS
    # ==================================================

    async def get_server_roles(
        self,
        guild: discord.Guild,
    ):
        settings = (
            await self.bot.db
            .get_guild_settings(
                guild.id
            )
        )

        if not settings:
            return (
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

        return (
            admin_role_id,
            mod_role_id,
        )

    async def is_staff(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        guild = interaction.guild
        member = interaction.user

        if (
            guild is None
            or not isinstance(
                member,
                discord.Member,
            )
        ):
            return False

        if member.guild_permissions.administrator:
            return True

        try:
            (
                admin_role_id,
                mod_role_id,
            ) = await self.get_server_roles(
                guild
            )

        except Exception:
            traceback.print_exc()
            return False

        member_role_ids = {
            role.id
            for role in member.roles
        }

        return bool(
            (
                admin_role_id
                and admin_role_id
                in member_role_ids
            )
            or (
                mod_role_id
                and mod_role_id
                in member_role_ids
            )
        )

    async def is_admin(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        guild = interaction.guild
        member = interaction.user

        if (
            guild is None
            or not isinstance(
                member,
                discord.Member,
            )
        ):
            return False

        if member.guild_permissions.administrator:
            return True

        try:
            (
                admin_role_id,
                _,
            ) = await self.get_server_roles(
                guild
            )

        except Exception:
            traceback.print_exc()
            return False

        if not admin_role_id:
            return False

        return any(
            role.id == admin_role_id
            for role in member.roles
        )

    # ==================================================
    # EMBEDS
    # ==================================================

    async def build_case_embed(
        self,
        guild: discord.Guild,
        member_id: int,
    ):
        member = guild.get_member(
            member_id
        )

        counts = await count_case_entries(
            guild.id,
            member_id,
        )

        latest = await get_latest_case_entry(
            guild.id,
            member_id,
        )

        member_text = (
            member.mention
            if member
            else f"<@{member_id}>"
        )

        embed = discord.Embed(
            title="🛡️ MEMBER CASE",
            colour=discord.Colour.orange(),
        )

        embed.add_field(
            name="Member",
            value=member_text,
            inline=True,
        )

        embed.add_field(
            name="User ID",
            value=f"`{member_id}`",
            inline=True,
        )

        embed.add_field(
            name="Status",
            value=(
                "✅ In server"
                if member
                else "🚪 Left server"
            ),
            inline=True,
        )

        if member:
            joined = (
                discord.utils.format_dt(
                    member.joined_at,
                    style="D",
                )
                if member.joined_at
                else "Unknown"
            )

            account_created = (
                discord.utils.format_dt(
                    member.created_at,
                    style="D",
                )
            )

            embed.add_field(
                name="Joined Server",
                value=joined,
                inline=True,
            )

            embed.add_field(
                name="Account Created",
                value=account_created,
                inline=True,
            )

        embed.add_field(
            name="Active Warnings",
            value=str(
                counts[
                    "active_warnings"
                ]
            ),
            inline=True,
        )

        embed.add_field(
            name="Staff Notes",
            value=str(
                counts[
                    "notes"
                ]
            ),
            inline=True,
        )

        embed.add_field(
            name="Total Case Entries",
            value=str(
                counts[
                    "total_entries"
                ]
            ),
            inline=True,
        )

        if latest:
            staff_text = (
                f"<@{latest['staff_id']}>"
            )

            active_text = ""

            if not latest[
                "active"
            ]:
                active_text = (
                    "\n**Status:** Cleared / inactive"
                )

            embed.add_field(
                name="Last Action",
                value=(
                    f"**#{latest['id']} • "
                    f"{entry_label(latest['entry_type'])}**\n"
                    f"**By:** {staff_text}\n"
                    f"**When:** "
                    f"{discord.utils.format_dt(latest['created_at'], style='R')}\n"
                    f"**Details:** "
                    f"{trim_text(latest['content'], 650)}"
                    f"{active_text}"
                ),
                inline=False,
            )

        else:
            embed.add_field(
                name="Last Action",
                value="No case history yet.",
                inline=False,
            )

        embed.set_footer(
            text=(
                "Warnings and notes are private staff records. "
                "Use the buttons below to update this case."
            )
        )

        return embed

    async def build_history_embed(
        self,
        guild: discord.Guild,
        member_id: int,
        limit: int = 15,
        entry_type: str | None = None,
        active_only: bool = False,
    ):
        entries = await get_case_entries(
            guild_id=guild.id,
            member_id=member_id,
            entry_type=entry_type,
            active_only=active_only,
            limit=limit,
        )

        member = guild.get_member(
            member_id
        )

        member_name = (
            str(member)
            if member
            else str(member_id)
        )

        title = (
            f"📖 Case History — {member_name}"
        )

        if entry_type == "warning":
            title = (
                f"⚠️ Warnings — {member_name}"
            )

        elif entry_type == "note":
            title = (
                f"📝 Staff Notes — {member_name}"
            )

        embed = discord.Embed(
            title=title,
            colour=discord.Colour.blurple(),
        )

        if not entries:
            embed.description = (
                "No matching case entries were found."
            )

            return embed

        lines = []

        for entry in entries:
            status = ""

            if not entry[
                "active"
            ]:
                status = " • **CLEARED**"

            lines.append(
                (
                    f"**#{entry['id']} • "
                    f"{entry_label(entry['entry_type'])}"
                    f"{status}**\n"
                    f"By <@{entry['staff_id']}> • "
                    f"{discord.utils.format_dt(entry['created_at'], style='R')}\n"
                    f"{trim_text(entry['content'], 350)}"
                )
            )

        embed.description = (
            "\n\n".join(
                lines
            )
        )[:4096]

        embed.set_footer(
            text=(
                f"Showing the newest {len(entries)} "
                "matching case entries."
            )
        )

        return embed

    # ==================================================
    # CASE THREAD / PANEL
    # ==================================================

    async def ensure_case(
        self,
        guild: discord.Guild,
        member: discord.Member,
    ):
        settings = await get_case_settings(
            guild.id
        )

        case_channel_id = settings.get(
            "case_channel_id"
        )

        if not case_channel_id:
            raise RuntimeError(
                (
                    "No Staff Cases channel is configured. "
                    "Use `/casesetup` first."
                )
            )

        case_channel = guild.get_channel(
            case_channel_id
        )

        if not isinstance(
            case_channel,
            discord.TextChannel,
        ):
            raise RuntimeError(
                (
                    "The configured Staff Cases channel "
                    "no longer exists."
                )
            )

        case = await get_member_case(
            guild.id,
            member.id,
        )

        thread = None

        if (
            case
            and case[
                "thread_id"
            ]
        ):
            thread = guild.get_thread(
                case[
                    "thread_id"
                ]
            )

            if thread is None:
                fetched = self.bot.get_channel(
                    case[
                        "thread_id"
                    ]
                )

                if isinstance(
                    fetched,
                    discord.Thread,
                ):
                    thread = fetched

        if thread is not None:
            if thread.archived:
                try:
                    await thread.edit(
                        archived=False,
                        reason="Member case accessed",
                    )

                except (
                    discord.Forbidden,
                    discord.HTTPException,
                ):
                    pass

            panel_message = None

            panel_message_id = (
                case[
                    "panel_message_id"
                ]
                if case
                else None
            )

            if panel_message_id:
                try:
                    panel_message = (
                        await thread.fetch_message(
                            panel_message_id
                        )
                    )

                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException,
                ):
                    panel_message = None

            if panel_message is None:
                panel_message = await thread.send(
                    embed=(
                        await self.build_case_embed(
                            guild,
                            member.id,
                        )
                    ),
                    view=CasePanelView(
                        cog=self,
                        guild_id=guild.id,
                        member_id=member.id,
                    ),
                )

                await save_member_case(
                    guild_id=guild.id,
                    member_id=member.id,
                    thread_id=thread.id,
                    panel_message_id=panel_message.id,
                )

            return (
                thread,
                panel_message,
            )

        if case:
            await delete_member_case_location(
                guild.id,
                member.id,
            )

        # Public threads inside a private staff channel inherit
        # the channel's visibility, so staff can access them
        # without individually inviting every moderator.
        thread = await case_channel.create_thread(
            name=safe_thread_name(
                member
            ),
            type=discord.ChannelType.public_thread,
            auto_archive_duration=1440,
            reason=(
                f"Staff case created for {member} ({member.id})"
            ),
        )

        panel_message = await thread.send(
            embed=(
                await self.build_case_embed(
                    guild,
                    member.id,
                )
            ),
            view=CasePanelView(
                cog=self,
                guild_id=guild.id,
                member_id=member.id,
            ),
        )

        await save_member_case(
            guild_id=guild.id,
            member_id=member.id,
            thread_id=thread.id,
            panel_message_id=panel_message.id,
        )

        return (
            thread,
            panel_message,
        )

    async def refresh_case_panel(
        self,
        guild: discord.Guild,
        member_id: int,
    ):
        case = await get_member_case(
            guild.id,
            member_id,
        )

        if not case:
            return

        thread = guild.get_thread(
            case[
                "thread_id"
            ]
        )

        if thread is None:
            fetched = self.bot.get_channel(
                case[
                    "thread_id"
                ]
            )

            if isinstance(
                fetched,
                discord.Thread,
            ):
                thread = fetched

        if thread is None:
            return

        try:
            panel_message = (
                await thread.fetch_message(
                    case[
                        "panel_message_id"
                    ]
                )
            )

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            return

        await panel_message.edit(
            embed=(
                await self.build_case_embed(
                    guild,
                    member_id,
                )
            ),
            view=CasePanelView(
                cog=self,
                guild_id=guild.id,
                member_id=member_id,
            ),
        )

    async def post_case_entry(
        self,
        guild: discord.Guild,
        member: discord.Member,
        entry,
    ):
        thread, _ = await self.ensure_case(
            guild,
            member,
        )

        status = ""

        if not entry[
            "active"
        ]:
            status = "\n**Status:** Cleared / inactive"

        await thread.send(
            (
                f"**#{entry['id']} • "
                f"{entry_label(entry['entry_type'])}**\n"
                f"**Member:** {member.mention}\n"
                f"**By:** <@{entry['staff_id']}>\n"
                f"**Details:** {entry['content']}"
                f"{status}"
            ),
            allowed_mentions=discord.AllowedMentions(
                users=False,
                roles=False,
                everyone=False,
            ),
        )

        await self.refresh_case_panel(
            guild,
            member.id,
        )

    # ==================================================
    # ADD / CLEAR ACTIONS
    # ==================================================

    async def add_warning(
        self,
        member: discord.Member,
        staff: discord.Member,
        reason: str,
    ):
        reason = str(
            reason
        ).strip()

        if not reason:
            raise ValueError(
                "A warning reason is required."
            )

        await self.ensure_case(
            member.guild,
            member,
        )

        entry = await add_case_entry(
            guild_id=member.guild.id,
            member_id=member.id,
            entry_type="warning",
            content=reason,
            staff_id=staff.id,
        )

        await self.post_case_entry(
            member.guild,
            member,
            entry,
        )

        return entry

    async def add_note(
        self,
        member: discord.Member,
        staff: discord.Member,
        note: str,
    ):
        note = str(
            note
        ).strip()

        if not note:
            raise ValueError(
                "A staff note is required."
            )

        await self.ensure_case(
            member.guild,
            member,
        )

        entry = await add_case_entry(
            guild_id=member.guild.id,
            member_id=member.id,
            entry_type="note",
            content=note,
            staff_id=staff.id,
        )

        await self.post_case_entry(
            member.guild,
            member,
            entry,
        )

        return entry

    async def clear_member_warning(
        self,
        warning_id: int,
        guild_id: int,
        staff: discord.Member,
    ):
        cleared = await clear_warning(
            warning_id=warning_id,
            guild_id=guild_id,
            removed_by=staff.id,
        )

        if not cleared:
            return None

        guild = staff.guild

        member = guild.get_member(
            cleared[
                "member_id"
            ]
        )

        if member:
            try:
                thread, _ = await self.ensure_case(
                    guild,
                    member,
                )

                await thread.send(
                    (
                        f"🧹 **Warning #{warning_id} cleared**\n"
                        f"**By:** {staff.mention}\n"
                        f"**Original warning:** "
                        f"{trim_text(cleared['content'], 1000)}"
                    ),
                    allowed_mentions=discord.AllowedMentions(
                        users=False,
                        roles=False,
                        everyone=False,
                    ),
                )

            except Exception:
                traceback.print_exc()

        await self.refresh_case_panel(
            guild,
            cleared[
                "member_id"
            ],
        )

        return cleared

    # ==================================================
    # /CASESETUP
    # ==================================================

    @app_commands.command(
        name="casesetup",
        description="Set the private staff channel used for member case threads.",
    )
    @app_commands.describe(
        channel="Private staff channel where member case threads should be created.",
    )
    @app_commands.default_permissions(
        administrator=True
    )
    async def casesetup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        if not await self.is_admin(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin role can set up the case channel.",
                ephemeral=True,
            )

        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True,
            )

        bot_member = guild.me

        if bot_member is None:
            return await interaction.response.send_message(
                "❌ I couldn't check my channel permissions.",
                ephemeral=True,
            )

        permissions = channel.permissions_for(
            bot_member
        )

        needed = []

        if not permissions.view_channel:
            needed.append(
                "View Channel"
            )

        if not permissions.send_messages:
            needed.append(
                "Send Messages"
            )

        if not permissions.create_public_threads:
            needed.append(
                "Create Public Threads"
            )

        if not permissions.send_messages_in_threads:
            needed.append(
                "Send Messages in Threads"
            )

        if not permissions.embed_links:
            needed.append(
                "Embed Links"
            )

        if needed:
            return await interaction.response.send_message(
                (
                    "❌ I need these permissions in "
                    f"{channel.mention}:\n"
                    + "\n".join(
                        f"• {permission}"
                        for permission in needed
                    )
                ),
                ephemeral=True,
            )

        await set_case_channel(
            guild.id,
            channel.id,
        )

        everyone_can_view = (
            channel
            .permissions_for(
                guild.default_role
            )
            .view_channel
        )

        warning = ""

        if everyone_can_view:
            warning = (
                "\n\n⚠️ **Important:** `@everyone` can currently "
                "view this channel. Case records should be kept "
                "in a private staff-only channel."
            )

        await interaction.response.send_message(
            (
                f"✅ Staff Cases channel set to {channel.mention}."
                f"{warning}"
            ),
            ephemeral=True,
        )

    # ==================================================
    # /CASE
    # ==================================================

    @app_commands.command(
        name="case",
        description="Open or create a member's staff case.",
    )
    @app_commands.describe(
        member="The member whose case you want to open.",
    )
    async def case_command(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        if not await self.is_staff(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use `/case`.",
                ephemeral=True,
            )

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            thread, _ = await self.ensure_case(
                interaction.guild,
                member,
            )

        except Exception as exc:
            traceback.print_exc()

            return await interaction.followup.send(
                f"❌ I couldn't open that case: {exc}",
                ephemeral=True,
            )

        await interaction.followup.send(
            (
                f"🛡️ {member.mention}'s case: "
                f"<#{thread.id}>"
            ),
            ephemeral=True,
        )

    # ==================================================
    # /WARN
    # ==================================================

    @app_commands.command(
        name="warn",
        description="Add a warning to a member's staff case.",
    )
    @app_commands.describe(
        member="The member to warn.",
        reason="Why the member is being warned.",
    )
    async def warn_command(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ):
        if not await self.is_staff(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use `/warn`.",
                ephemeral=True,
            )

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            entry = await self.add_warning(
                member=member,
                staff=interaction.user,
                reason=reason,
            )

        except Exception as exc:
            traceback.print_exc()

            return await interaction.followup.send(
                f"❌ I couldn't add the warning: {exc}",
                ephemeral=True,
            )

        await interaction.followup.send(
            (
                f"✅ Warning **#{entry['id']}** added "
                f"to {member.mention}'s case."
            ),
            ephemeral=True,
        )

    # ==================================================
    # /WARNINGS
    # ==================================================

    @app_commands.command(
        name="warnings",
        description="View a member's warning history.",
    )
    @app_commands.describe(
        member="The member whose warnings you want to view.",
    )
    async def warnings_command(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        if not await self.is_staff(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use `/warnings`.",
                ephemeral=True,
            )

        embed = await self.build_history_embed(
            guild=interaction.guild,
            member_id=member.id,
            limit=20,
            entry_type="warning",
            active_only=False,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # ==================================================
    # /CLEARWARNING
    # ==================================================

    @app_commands.command(
        name="clearwarning",
        description="Clear an active warning by its case number.",
    )
    @app_commands.describe(
        warning_id="The warning number shown in the member's case history.",
    )
    async def clearwarning_command(
        self,
        interaction: discord.Interaction,
        warning_id: int,
    ):
        if not await self.is_staff(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use `/clearwarning`.",
                ephemeral=True,
            )

        entry = await get_case_entry(
            warning_id
        )

        if (
            not entry
            or entry[
                "guild_id"
            ] != interaction.guild.id
            or entry[
                "entry_type"
            ] != "warning"
            or not entry[
                "active"
            ]
        ):
            return await interaction.response.send_message(
                "❌ I couldn't find an active warning with that number.",
                ephemeral=True,
            )

        await interaction.response.defer(
            ephemeral=True
        )

        cleared = await self.clear_member_warning(
            warning_id=warning_id,
            guild_id=interaction.guild.id,
            staff=interaction.user,
        )

        if not cleared:
            return await interaction.followup.send(
                "❌ That warning could not be cleared.",
                ephemeral=True,
            )

        await interaction.followup.send(
            f"✅ Warning **#{warning_id}** cleared.",
            ephemeral=True,
        )

    # ==================================================
    # /NOTE
    # ==================================================

    @app_commands.command(
        name="note",
        description="Add a private staff note to a member's case.",
    )
    @app_commands.describe(
        member="The member to add a note about.",
        note="The private staff note.",
    )
    async def note_command(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        note: str,
    ):
        if not await self.is_staff(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use `/note`.",
                ephemeral=True,
            )

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            entry = await self.add_note(
                member=member,
                staff=interaction.user,
                note=note,
            )

        except Exception as exc:
            traceback.print_exc()

            return await interaction.followup.send(
                f"❌ I couldn't add the staff note: {exc}",
                ephemeral=True,
            )

        await interaction.followup.send(
            (
                f"✅ Staff note **#{entry['id']}** added "
                f"to {member.mention}'s case."
            ),
            ephemeral=True,
        )

    # ==================================================
    # /NOTES
    # ==================================================

    @app_commands.command(
        name="notes",
        description="View a member's private staff notes.",
    )
    @app_commands.describe(
        member="The member whose staff notes you want to view.",
    )
    async def notes_command(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        if not await self.is_staff(
            interaction
        ):
            return await interaction.response.send_message(
                "❌ Only the configured Admin or Mod role can use `/notes`.",
                ephemeral=True,
            )

        embed = await self.build_history_embed(
            guild=interaction.guild,
            member_id=member.id,
            limit=20,
            entry_type="note",
            active_only=False,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


# ==================================================
# SETUP
# ==================================================

async def setup(
    bot,
):
    await bot.add_cog(
        Cases(
            bot
        )
    )
