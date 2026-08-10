# bot.py
import os
import asyncio
import discord
from discord.ext import commands

from database.database import db
from database.autothreads import get_all_autothreads, init_autothreads_table

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

bot.db = db
bot.autothread_config = {}  # placeholder for runtime autothread config


# --------------------------------------------------
# READY EVENT
# --------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")


# --------------------------------------------------
# LOAD COGS
# --------------------------------------------------
async def load_cogs():
    cogs_dir = "./cogs"
    for filename in os.listdir(cogs_dir):
        if not filename.endswith(".py"):
            continue
        if filename == "__init__.py":
            # skip package initializer unless it intentionally exposes a setup function
            continue
        module_name = f"cogs.{filename[:-3]}"
        try:
            await bot.load_extension(module_name)
            print(f"✅ Loaded cog: {filename}")
        except Exception as e:
            print(f"❌ Failed to load {filename}: {e}")


# --------------------------------------------------
# RESTORE AUTO-THREADS
# --------------------------------------------------
async def restore_autothreads():
    print("🔄 Restoring auto-threads...")
    try:
        threads = await get_all_autothreads()
    except Exception as e:
        print(f"⚠️ Failed to fetch autothreads: {e}")
        return

    for t in threads:
        thread_id = t.get("thread_id") if isinstance(t, dict) else t["thread_id"]
        try:
            thread = bot.get_channel(thread_id)
        except Exception:
            thread = None

        if not thread:
            print(f"⚠️ Missing thread {thread_id} (deleted or inaccessible)")
            continue

        # If you need to re-register views or listeners for the thread, do it here.
        print(f"🔧 Restored autothread: {getattr(thread, 'name', str(thread_id))}")


# --------------------------------------------------
# STARTUP / SHUTDOWN
# --------------------------------------------------
async def main():
    try:
        # Connect to DB first
        await db.connect()
        print("✅ Connected to PostgreSQL")

        # Ensure autothreads table exists before attempting to read it
        try:
            await init_autothreads_table()
            print("✅ Autothreads table ensured.")
        except Exception as e:
            print(f"⚠️ init_autothreads_table failed: {e}")

        # Load cogs after DB is ready
        await load_cogs()

        # Restore autothreads but don't let a failure stop the bot
        try:
            await restore_autothreads()
        except Exception as e:
            print(f"⚠️ Autothread restore failed: {e}")

        # Start the bot
        await bot.start(TOKEN)
    finally:
        # Ensure DB is closed on shutdown
        try:
            await db.close()
            print("✅ Database connection closed.")
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
