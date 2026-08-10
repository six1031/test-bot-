# cogs/autothread.py
import discord
from discord import app_commands
from discord.ext import commands

from database.autothreads import add_autothread, get_all_autothreads, remove_autothread

class AutothreadCog(commands.Cog):
    """Manage and restore autothreads stored in the database."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------------------
    # Slash commands
    # -------------------------
    @app_commands.command(name="autothread-add", description="Register a channel/message as an autothread parent")
    @app_commands.describe(parent_channel="Channel where threads will be created",
                           parent_message_id="Optional parent message ID (leave blank to use channel-level)",
                           thread_type="Numeric type or identifier for this autothread")
    async def autothread_add(self, interaction: discord.Interaction, parent_channel: discord.TextChannel, parent_message_id: int | None, thread_type: int):
        """Register an autothread in the database."""
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            # owner_id left None for generic autothreads; change if you want per-user ownership
            await add_autothread(
                thread_id=0,  # placeholder; actual thread_id will be set when thread is created
                parent_channel_id=parent_channel.id,
                parent_message_id=parent_message_id,
                thread_type=thread_type,
                owner_id=None
            )
            await interaction.followup.send(f"✅ Registered autothread parent in {parent_channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to register autothread: {e}", ephemeral=True)

    @app_commands.command(name="autothread-list", description="List registered autothread parents")
    async def autothread_list(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            rows = await get_all_autothreads()
            if not rows:
                await interaction.followup.send("No autothreads registered.", ephemeral=True)
                return

            lines = []
            for r in rows:
                parent_channel = r.get("parent_channel_id") if isinstance(r, dict) else r["parent_channel_id"]
                parent_message = r.get("parent_message_id") if isinstance(r, dict) else r["parent_message_id"]
                thread_type = r.get("thread_type") if isinstance(r, dict) else r["thread_type"]
                lines.append(f"Channel ID: `{parent_channel}`; Message ID: `{parent_message}`; Type: `{thread_type}`")

            # Keep the embed small and readable
            embed = discord.Embed(title="Autothread parents", color=discord.Color.blurple())
            embed.description = "\n".join(lines[:20])  # limit to first 20 entries
            if len(lines) > 20:
                embed.set_footer(text=f"And {len(lines)-20} more...")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to list autothreads: {e}", ephemeral=True)

    @app_commands.command(name="autothread-remove", description="Remove an autothread registration by parent channel ID")
    @app_commands.describe(parent_channel_id="Parent channel ID to remove")
    async def autothread_remove(self, interaction: discord.Interaction, parent_channel_id: int):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            # remove_autothread expects thread_id; we will remove by parent_channel_id here
            # If your DB schema doesn't support this, adapt accordingly.
            rows = await get_all_autothreads()
            found = None
            for r in rows:
                if (r.get("parent_channel_id") if isinstance(r, dict) else r["parent_channel_id"]) == parent_channel_id:
                    found = r
                    break

            if not found:
                await interaction.followup.send("No autothread found for that parent channel ID.", ephemeral=True)
                return

            thread_id = found.get("thread_id") if isinstance(found, dict) else found["thread_id"]
            await remove_autothread(thread_id)
            await interaction.followup.send("✅ Removed autothread registration.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to remove autothread: {e}", ephemeral=True)

    # -------------------------
    # Event listeners
    # -------------------------
    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """
        When a thread is created, check if it belongs to a registered autothread parent.
        If so, update the DB entry (replace placeholder thread_id=0) or add a new record.
        """
        try:
            parent = thread.parent
            if parent is None:
                return

            parent_channel_id = parent.id
            parent_message_id = getattr(thread, "message", None)
            # message may not be directly available; we store parent_message_id as None if not applicable
            parent_message_id = None

            rows = await get_all_autothreads()
            for r in rows:
                r_parent_channel = r.get("parent_channel_id") if isinstance(r, dict) else r["parent_channel_id"]
                r_parent_message = r.get("parent_message_id") if isinstance(r, dict) else r["parent_message_id"]
                if r_parent_channel == parent_channel_id and (r_parent_message is None or r_parent_message == parent_message_id):
                    # Found a matching autothread registration. Update DB record to set thread_id.
                    # Some implementations store thread_id immediately when created; here we remove old placeholder and add real record.
                    try:
                        # remove old placeholder if present
                        if r.get("thread_id") == 0 or (not r.get("thread_id")):
                            await remove_autothread(r.get("thread_id") if isinstance(r, dict) else r["thread_id"])
                        await add_autothread(thread.id, parent_channel_id, parent_message_id, r.get("thread_type") if isinstance(r, dict) else r["thread_type"], owner_id=None)
                        print(f"🔁 Registered new autothread instance: {thread.id} (parent {parent_channel_id})")
                    except Exception as inner:
                        print(f"⚠️ Failed to update autothread instance for thread {thread.id}: {inner}")
                    break
        except Exception as e:
            print(f"⚠️ Error in on_thread_create autothread handler: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AutothreadCog(bot))
