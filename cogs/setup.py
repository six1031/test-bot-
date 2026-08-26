# cogs/setup.py

import asyncio
import traceback
import discord

from discord import app_commands
from discord.ext import commands


class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description=(
            "Run initial server setup "
            "(roles, logs, tickets, relationships)"
        ),
    )
    @app_commands.describe(
        log_channel="Channel to send setup logs to",
        admin_role="Role to treat as server admin",
        mod_role="Role for moderators and ticket staff",
        member_role="Role for normal/verified members",
        ticket_category="Category where ticket channels will be created",
        marriage_channel="Channel for marriage/relationships posts",
        enforce_only_post=(
            "If true, restrict posting to the selected marriage channel"
        ),
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_command(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None = None,
        admin_role: discord.Role | None = None,
        mod_role: discord.Role | None = None,
        member_role: discord.Role | None = None,
        ticket_category: discord.CategoryChannel | None = None,
        marriage_channel: discord.TextChannel | None = None,
        enforce_only_post: bool = True,
    ):
        await interaction.response.send_message(
            (
                "🔧 Setup started — running in background. "
                "Progress will be posted to the log channel if provided."
            ),
            ephemeral=True,
        )

        self.bot.loop.create_task(
            self._run_setup_background(
                interaction,
                log_channel,
                admin_role,
                mod_role,
                member_role,
                ticket_category,
                marriage_channel,
                enforce_only_post,
            )
        )

    async def _run_setup_background(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None,
        admin_role: discord.Role | None,
        mod_role: discord.Role | None,
        member_role: discord.Role | None,
        ticket_category: discord.CategoryChannel | None,
        marriage_channel: discord.TextChannel | None,
        enforce_only_post: bool,
    ):
        try:
            await asyncio.wait_for(
                self._do_setup_work(
                    interaction,
                    log_channel,
                    admin_role,
                    mod_role,
                    member_role,
                    ticket_category,
                    marriage_channel,
                    enforce_only_post,
                ),
                timeout=180.0,
            )

            await interaction.followup.send(
                "✅ Setup completed successfully.",
                ephemeral=True,
            )

        except asyncio.TimeoutError:
            await interaction.followup.send(
                (
                    "⚠️ Setup timed out. "
                    "Check bot permissions and try again."
                ),
                ephemeral=True,
            )

        except Exception as e:
            traceback.print_exc()

            await interaction.followup.send(
                f"❌ Setup failed: {e}",
                ephemeral=True,
            )

    async def _do_setup_work(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None,
        admin_role: discord.Role | None,
        mod_role: discord.Role | None,
        member_role: discord.Role | None,
        ticket_category: discord.CategoryChannel | None,
        marriage_channel: discord.TextChannel | None,
        enforce_only_post: bool,
    ):
        # --------------------------------------------------
        # HELPER - SETUP LOG
        # --------------------------------------------------

        async def log(msg: str):
            if log_channel:
                try:
                    await log_channel.send(msg)
                except Exception:
                    pass

        await log("🔧 Setup: starting.")

        # --------------------------------------------------
        # DETERMINE GUILD CONTEXT
        # --------------------------------------------------

        guild = interaction.guild

        if guild is None:
            if marriage_channel:
                guild = marriage_channel.guild
            elif log_channel:
                guild = log_channel.guild
            elif admin_role:
                guild = admin_role.guild
            elif mod_role:
                guild = mod_role.guild
            elif member_role:
                guild = member_role.guild

        if guild is None:
            guilds = list(self.bot.guilds)
            guild = guilds[0] if guilds else None

        if not guild:
            await log(
                "⚠️ No guild context found; aborting role/channel operations."
            )
            return

        # --------------------------------------------------
        # ADMIN ROLE
        # --------------------------------------------------

        if admin_role is None:
            admin_role = discord.utils.get(
                guild.roles,
                name="Admin",
            )

            if admin_role is None:
                try:
                    admin_role = await guild.create_role(
                        name="Admin",
                        reason="Setup: creating admin role",
                    )

                    await log(
                        "✅ Created role: Admin"
                    )

                except Exception:
                    await log(
                        (
                            "⚠️ Failed to create Admin role "
                            "(missing permissions)."
                        )
                    )
        else:
            await log(
                f"✅ Admin role set to: {admin_role.name}"
            )

        # --------------------------------------------------
        # MOD ROLE
        # --------------------------------------------------

        if mod_role is None:
            # Try common names, but do not create one automatically.
            mod_role = (
                discord.utils.get(guild.roles, name="Mod")
                or discord.utils.get(guild.roles, name="Moderator")
                or discord.utils.get(guild.roles, name="Staff")
            )

            if mod_role:
                await log(
                    f"✅ Mod role detected as: {mod_role.name}"
                )
            else:
                await log(
                    "ℹ️ No mod role selected."
                )
        else:
            await log(
                f"✅ Mod role set to: {mod_role.name}"
            )

        # --------------------------------------------------
        # MEMBER ROLE
        # --------------------------------------------------

        if member_role is None:
            member_role = (
                discord.utils.get(guild.roles, name="Member")
                or discord.utils.get(guild.roles, name="Members")
                or discord.utils.get(guild.roles, name="Verified")
            )

            if member_role:
                await log(
                    f"✅ Member role detected as: {member_role.name}"
                )
            else:
                await log(
                    "ℹ️ No member role selected."
                )
        else:
            await log(
                f"✅ Member role set to: {member_role.name}"
            )

        # --------------------------------------------------
        # MARRIAGE / RELATIONSHIPS CHANNEL
        # --------------------------------------------------

        if marriage_channel is None:
            await log(
                "ℹ️ No marriage/relationships channel provided."
            )

        else:
            await log(
                f"✅ Marriage channel set to: #{marriage_channel.name}"
            )

            if enforce_only_post:
                try:
                    everyone = guild.default_role
                    bot_member = guild.get_member(
                        self.bot.user.id
                    )

                    await marriage_channel.set_permissions(
                        everyone,
                        send_messages=False,
                        reason="Setup: restrict marriage channel",
                    )

                    if admin_role:
                        await marriage_channel.set_permissions(
                            admin_role,
                            send_messages=True,
                            reason="Setup: allow admin role to post",
                        )

                    if mod_role:
                        await marriage_channel.set_permissions(
                            mod_role,
                            send_messages=True,
                            reason="Setup: allow mod role to post",
                        )

                    if bot_member:
                        await marriage_channel.set_permissions(
                            bot_member,
                            send_messages=True,
                            reason="Setup: allow bot to post",
                        )

                    await log(
                        (
                            "🔒 Enforced posting restrictions on "
                            f"#{marriage_channel.name}."
                        )
                    )

                except Exception:
                    traceback.print_exc()

                    await log(
                        (
                            "⚠️ Failed to enforce posting restrictions on "
                            f"#{marriage_channel.name}. "
                            "Check bot permissions (Manage Channels)."
                        )
                    )

        # --------------------------------------------------
        # SAVE SETTINGS TO DATABASE
        # --------------------------------------------------

        try:
            db_obj = getattr(
                self.bot,
                "db",
                None,
            )

            if (
                db_obj
                and callable(
                    getattr(
                        db_obj,
                        "upsert_guild_settings",
                        None,
                    )
                )
            ):
                await db_obj.upsert_guild_settings(
                    guild_id=guild.id,
                    log_channel_id=(
                        log_channel.id
                        if log_channel
                        else None
                    ),
                    admin_role_id=(
                        admin_role.id
                        if admin_role
                        else None
                    ),
                    mod_role_id=(
                        mod_role.id
                        if mod_role
                        else None
                    ),
                    member_role_id=(
                        member_role.id
                        if member_role
                        else None
                    ),
                    ticket_category_id=(
                        ticket_category.id
                        if ticket_category
                        else None
                    ),
                    marriage_channel_id=(
                        marriage_channel.id
                        if marriage_channel
                        else None
                    ),
                    relationship_channel_id=(
                        marriage_channel.id
                        if marriage_channel
                        else None
                    ),
                    enforce_only_post=enforce_only_post,
                )

                await log(
                    "✅ Saved guild settings to database."
                )

            else:
                await log(
                    (
                        "ℹ️ Database upsert helper not available; "
                        "settings not persisted."
                    )
                )

        except Exception:
            traceback.print_exc()

            await log(
                "⚠️ Failed to save guild settings to database."
            )

        await log(
            "🔧 Setup finished (best-effort)."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        SetupCog(bot)
    )
