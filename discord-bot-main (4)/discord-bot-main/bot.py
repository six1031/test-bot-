import discord
from discord.ext import commands
import os
import asyncio

from database.database import db

from views.ticket_views import (
    VerificationTicketView,
    ReportsTicketView,
    ApplicationsTicketView,
    ContactTicketView,
    CloseTicketView,
)



# --------------------------------------------------
# BOT SETUP
# --------------------------------------------------

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --------------------------------------------------
# READY EVENT
# --------------------------------------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Bot is online and ready.")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

# --------------------------------------------------
# EXAMPLE PREFIX COMMAND
# --------------------------------------------------

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

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
# STARTUP
# --------------------------------------------------
async def main():
    async with bot:

        await db.connect()

        await load_cogs()

        bot.add_view(VerificationTicketView())
        bot.add_view(ReportsTicketView())
        bot.add_view(ApplicationsTicketView())
        bot.add_view(ContactTicketView())
        bot.add_view(CloseTicketView())

        await bot.start(TOKEN)

    await db.close()
    
asyncio.run(main())
