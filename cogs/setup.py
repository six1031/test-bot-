# inside cogs/setup.py (or wherever your /setup command lives)
import asyncio
import traceback
import discord
from discord import app_commands
from discord.ext import commands

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Run initial setup and migrations")
    async def setup_command(self, interaction: discord.Interaction):
        # Reply immediately so Discord doesn't stay thinking
        await interaction.response.send_message("🔧 Setup started — running in background. I'll report back here.", ephemeral=True)

        # Launch background task (non-blocking)
        self.bot.loop.create_task(self._run_setup_background(interaction))

    async def _run_setup_background(self, interaction: discord.Interaction):
        try:
            # Example: ensure tables, run migrations, seed data
            # Use asyncio.wait_for to avoid indefinite hangs on DB calls
            await asyncio.wait_for(self._do_setup_work(), timeout=120.0)
            await interaction.followup.send("✅ Setup completed successfully.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⚠️ Setup timed out. Check DB connectivity and try again.", ephemeral=True)
        except Exception as e:
            # Log full traceback to container logs for debugging
            traceback.print_exc()
            await interaction.followup.send(f"❌ Setup failed: {e}", ephemeral=True)

    async def _do_setup_work(self):
        # Put your actual setup/migration code here.
        # Example: call init_autothreads_table(), run migrations, create roles, etc.
        from database.autothreads import init_autothreads_table
        await init_autothreads_table()

        # Example of running other table creation safely
        # from database.database import db
        # async with db.pool.acquire() as conn:
        #     await conn.execute("CREATE TABLE IF NOT EXISTS ...")

        # Simulate work for demonstration (remove in production)
        # await asyncio.sleep(1)

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
