import discord
from discord.ext import commands
import os
import asyncio

from database.database import db
from database.autothreads import get_all_autothreads

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

bot.db = db
bot.autothread_config = {}  # SQL replaces JSON


# --------------------------------------------------
# READY EVENT
# --------------------------------------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Bot is online.")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")


# --------------------------------------------------
# LOAD COGS
# --------------------------------------------------

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"✅ Loaded cog: {filename}")
            except Exception as e:
                print(f"❌ Failed to load {filename}: {e}")


# --------------------------------------------------
# RESTORE AUTO-THREADS
# --------------------------------------------------

async def restore_autothreads():
    print("🔄 Restoring auto-threads...")

    threads = await get_all_autothreads()

    for t in threads:
        thread = bot.get_channel(t["thread_id"])

        if not thread:
            print(f"⚠️ Missing thread {t['thread_id']} (deleted?)")
            continue

        print(f"🔧 Restored autothread: {thread.name} (Channel {t['thread_type']})")


# --------------------------------------------------
# STARTUP
# --------------------------------------------------

async def main():
    async with bot:

        await db.connect()
        
        await init_autothreads_table()
        
        await load_cogs()

        # Restore SQL-based autothreads
        await restore_autothreads()

        await bot.start(TOKEN)

    await db.close()


asyncio.run(main())
