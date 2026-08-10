import discord
from discord.ext import commands
import os
import asyncio

from database.database import db
from database.autothreads import get_all_autothreads
from database.tickets import get_all_open_tickets

from views.ticket_views import (
    VerificationTicketView,
    ReportsTicketView,
    ApplicationsTicketView,
    ContactTicketView,
    CloseTicketView,
)

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

bot.db = db  # REQUIRED so cogs can access the database
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
# RESTORE TICKET VIEWS
# --------------------------------------------------

async def restore_tickets():
    print("🔄 Restoring ticket views...")

    open_tickets = await get_all_open_tickets()

    for ticket in open_tickets:
        channel_id = ticket["channel_id"]
        channel = bot.get_channel(channel_id)

        if not channel:
            print(f"⚠️ Missing ticket channel {channel_id}")
            continue

        try:
            async for msg in channel.history(limit=10):
                if msg.author == bot.user:
                    await msg.edit(view=CloseTicketView())
                    print(f"🔧 Restored ticket view in #{channel.name}")
                    break
        except Exception as e:
            print(f"❌ Failed restoring ticket {channel_id}: {e}")


# --------------------------------------------------
# STARTUP
# --------------------------------------------------

async def main():
    async with bot:

        await db.connect()
        await load_cogs()

        # Register persistent views
        bot.add_view(VerificationTicketView())
        bot.add_view(ReportsTicketView())
        bot.add_view(ApplicationsTicketView())
        bot.add_view(ContactTicketView())
        bot.add_view(CloseTicketView())

        # Restore SQL-based autothreads
        await restore_autothreads()

        # Restore ticket views
        await restore_tickets()

        await bot.start(TOKEN)

    await db.close()


asyncio.run(main())
