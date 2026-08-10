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
        description="Run initial server setup (log channel, admin role, marriage channel)"
    )
    @app_commands.describe(
        log_channel="Channel to send setup logs to",
        admin_role="Role to treat as server admin for setup",
        marriage_channel="Channel for marriage/relationships posts",
        enforce_only_post="If true, restrict posting to the selected marriage channel"
    )
    async def setup_command(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None = None,
        admin_role: discord.Role | None = None,
        marriage_channel: discord.TextChannel | None = None,
        enforce_only_post: bool = True
    ):
        await interaction.response.send_message(
            "🔧 Setup started — running in background. Progress will be posted to the log channel if provided.",
            ephemeral=True
        )
        self.bot.loop.create_task(
            self._run_setup_background(interaction, log_channel, admin_role, marriage_channel, enforce_only_post)
        )

    async def _run_setup_background(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None,
        admin_role: discord.Role | None,
        marriage_channel: discord.TextChannel | None,
        enforce_only_post: bool
    ):
        try:
            await asyncio.wait_for(
                self._do_setup_work(log_channel, admin_role, marriage_channel, enforce_only_post),
                timeout=180.0
            )
            await interaction.followup.send("✅ Setup completed successfully.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⚠️ Setup timed out. Check bot permissions and try again.", ephemeral=True)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Setup failed: {e}", ephemeral=True)

    async def _do_setup_work(
        self,
        log_channel: discord.TextChannel | None,
        admin_role: discord.Role | None,
        marriage_channel: discord.TextChannel | None,
        enforce_only_post: bool
    ):
        # Helper to send to log channel if available
        async def log(msg: str):
            if log_channel:
                try:
                    await log_channel.send(msg)
                except Exception:
                    pass

        await log("🔧 Setup: starting.")

        # 1) Ensure admin role exists or note it
        guild = None
        if marriage_channel:
            guild = marriage_channel.guild
        elif log_channel:
            guild = log_channel.guild
        elif admin_role:
            guild = admin_role.guild
        else:
            # best-effort: use first guild bot is in
            guilds = list(self.bot.guilds)
            guild = guilds[0] if guilds else None

        if not guild:
            await log("⚠️ No guild context found; aborting role/channel operations.")
            return

        # If admin_role not provided, try to find or create a sensible default
        if admin_role is None:
            admin_role = discord.utils.get(guild.roles, name="Admin")
            if admin_role is None:
                try:
                    admin_role = await guild.create_role(name="Admin", reason="Setup: creating admin role")
                    await log("✅ Created role: Admin")
                except Exception:
                    await log("⚠️ Failed to create Admin role (missing permissions).")

        else:
            await log(f"✅ Admin role set to: {admin_role.name}")

        # 2) Ensure marriage_channel exists or create a placeholder if not provided
        if marriage_channel is None:
            # do not auto-create unless you want; just log
            await log("ℹ️ No marriage/relationships channel provided.")
        else:
            await log(f"✅ Marriage channel set to: #{marriage_channel.name}")

            # 3) Optionally enforce posting restrictions in the marriage channel
            if enforce_only_post:
                try:
                    # Build overwrites: deny send_messages for @everyone, allow for admin_role and the bot
                    everyone = guild.default_role
                    bot_member = guild.get_member(self.bot.user.id)
                    overwrites = marriage_channel.overwrites_for(everyone)
                    overwrites.send_messages = False

                    # Apply overwrites for everyone
                    await marriage_channel.set_permissions(everyone, send_messages=False, reason="Setup: restrict marriage channel")

                    # Ensure admin_role can send
                    if admin_role:
                        await marriage_channel.set_permissions(admin_role, send_messages=True, reason="Setup: allow admin role to post")

                    # Ensure bot can send
                    if bot_member:
                        await marriage_channel.set_permissions(bot_member, send_messages=True, reason="Setup: allow bot to post")

                    await log(f"🔒 Enforced posting restrictions on #{marriage_channel.name}.")
                except Exception:
                    traceback.print_exc()
                    await log(f"⚠️ Failed to enforce posting restrictions on #{marriage_channel.name}. Check bot permissions (Manage Channels).")

        await log("🔧 Setup finished (best-effort).")

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
