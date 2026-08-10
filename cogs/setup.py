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
        description="Run initial setup and migrations"
    )
    @app_commands.describe(
        run_migrations="Whether to run DB migrations now",
        seed_demo="Whether to seed demo data (true/false)",
        timeout_seconds="Max seconds to allow setup to run"
    )
    async def setup_command(
        self,
        interaction: discord.Interaction,
        run_migrations: bool = True,
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
            self._run_setup_background(interaction, run_migrations, seed_demo, timeout_seconds)
        )

    async def _run_setup_background(self, interaction: discord.Interaction, run_migrations: bool, seed_demo: bool, timeout_seconds: int):
        try:
            await asyncio.wait_for(self._do_setup_work(run_migrations, seed_demo), timeout=timeout_seconds)
            await interaction.followup.send("✅ Setup completed successfully.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⚠️ Setup timed out. Check DB connectivity and try again.", ephemeral=True)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Setup failed: {e}", ephemeral=True)

    async def _do_setup_work(self, run_migrations: bool, seed_demo: bool):
        # Example: ensure autothreads table
        from database.autothreads import init_autothreads_table
        if run_migrations:
            await init_autothreads_table()

        # Example: optionally seed demo data
        if seed_demo:
            from database.tickets import add_ticket_panel
            # add a demo panel (replace with real values)
            await add_ticket_panel(0, 0, 0, "{}")

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
