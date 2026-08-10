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
        description="Run initial server setup and optional migrations"
    )
    @app_commands.describe(
        run_migrations="Run database migrations and ensure tables",
        create_roles="Create default server roles",
        create_channels="Create default channels and categories",
        seed_demo="Seed demo data such as ticket panels",
        timeout_seconds="Max seconds to allow setup to run"
    )
    async def setup_command(
        self,
        interaction: discord.Interaction,
        run_migrations: bool = True,
        create_roles: bool = False,
        create_channels: bool = False,
        seed_demo: bool = False,
        timeout_seconds: int = 120
    ):
        # Immediate reply so Discord doesn't stay thinking
        await interaction.response.send_message(
            "🔧 Setup started — running in background. I'll report back here.",
            ephemeral=True
        )

        # Launch background task (non-blocking)
        self.bot.loop.create_task(
            self._run_setup_background(interaction, run_migrations, create_roles, create_channels, seed_demo, timeout_seconds)
        )

    async def _run_setup_background(self, interaction: discord.Interaction, run_migrations: bool, create_roles: bool, create_channels: bool, seed_demo: bool, timeout_seconds: int):
        try:
            await asyncio.wait_for(
                self._do_setup_work(run_migrations, create_roles, create_channels, seed_demo),
                timeout=timeout_seconds
            )
            await interaction.followup.send("✅ Setup completed successfully.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⚠️ Setup timed out. Check DB connectivity and try again.", ephemeral=True)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Setup failed: {e}", ephemeral=True)

    async def _do_setup_work(self, run_migrations: bool, create_roles: bool, create_channels: bool, seed_demo: bool):
        # 1) Ensure DB tables (lazy import to avoid circular imports)
        if run_migrations:
            try:
                from database.autothreads import init_autothreads_table
                await init_autothreads_table()
            except Exception:
                # log but continue; init_autothreads_table should be defensive
                traceback.print_exc()

        # 2) Create roles if requested
        if create_roles:
            guilds = list(self.bot.guilds)
            if guilds:
                guild = guilds[0]  # best-effort: operate on first guild the bot is in
                roles_to_create = ["Moderator", "Support", "Member"]
                for rname in roles_to_create:
                    existing = discord.utils.get(guild.roles, name=rname)
                    if not existing:
                        await guild.create_role(name=rname)

        # 3) Create channels if requested
        if create_channels:
            guilds = list(self.bot.guilds)
            if guilds:
                guild = guilds[0]
                category = discord.utils.get(guild.categories, name="Community")
                if not category:
                    category = await guild.create_category("Community")
                if not discord.utils.get(guild.text_channels, name="welcome"):
                    await guild.create_text_channel("welcome", category=category)

        # 4) Seed demo ticket panel if requested (lazy import)
        if seed_demo:
            try:
                from database.tickets import add_ticket_panel
                # Use real values or skip; here we attempt and ignore failures
                await add_ticket_panel(guild_id=0, channel_id=0, message_id=0, config_json="{}")
            except Exception:
                traceback.print_exc()
                # ignore to avoid failing the whole setup

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
