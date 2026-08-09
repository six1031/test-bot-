import discord
from discord.ext import commands
from discord import app_commands
import asyncio

# --------------------------------------------------
# LOG CHANNELS
# --------------------------------------------------

BAN_LOG_CHANNEL_ID = 1531460605268066446  # YOUR BAN LOG CHANNEL

# --------------------------------------------------
# TEMP BAN SUPPORT
# --------------------------------------------------

def convert_duration_to_seconds(duration: str):
    duration = duration.lower().strip()

    try:
        if duration.endswith("h"):
            return int(duration[:-1]) * 3600
        if duration.endswith("m"):
            return int(duration[:-1]) * 60
        if duration.endswith("d"):
            return int(duration[:-1]) * 86400
        if duration == "n/a":
            return None
        return None
    except:
        return None

async def unban_after_delay(guild, user_id, delay):
    await asyncio.sleep(delay)
    user = discord.Object(id=user_id)
    try:
        await guild.unban(user)
    except:
        pass

# --------------------------------------------------
# MODERATION COG
# --------------------------------------------------

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------------------------------
    # /ping
    # --------------------------------------------------
    @app_commands.command(name="ping", description="Check if the bot is alive.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong!")

    @app_commands.command(name="ban", description="Ban a member with full logging.")
    @app_commands.describe(
        member="The member to ban",
        ban_type="Temporary or Permanent",
        duration="Duration (1h, 2d, 30m). Leave N/A for permanent.",
        rules="Rule numbers broken (e.g., 1, 3, 5)",
        reason="Reason for the ban",
        evidence="Links to screenshots, videos, message links, etc.",
        warnings="Previous warnings (None, Warning #1, Timeout, Previous Ban)"
    )
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        ban_type: str,
        duration: str = "N/A",
        rules: str = "N/A",
        reason: str = "No reason provided",
        evidence: str = "None provided",
        warnings: str = "None"
    ):
        ADMIN_ROLE_ID = 1428444870766231622

        # Restrict command to Admin role only
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            return await interaction.response.send_message(
                "❌ You must have the **Admin** role to use this command.",
                ephemeral=True
            )

        # Temporary ban
        if ban_type.lower() == "temporary":
            seconds = convert_duration_to_seconds(duration)
            if seconds is None:
                return await interaction.response.send_message(
                    "Invalid duration format. Use: 1h, 2d, 30m", ephemeral=True
                )

            await member.ban(reason=reason)
            self.bot.loop.create_task(unban_after_delay(interaction.guild, member.id, seconds))

            ban_message = f"⏳ {member} has been temporarily banned for **{duration}**."

        else:
            await member.ban(reason=reason)
            ban_message = f"🔨 {member} has been permanently banned."

        # Respond FIRST
        await interaction.response.send_message(ban_message)

        # Build log embed
        embed = discord.Embed(
            title="🔨 Member Banned",
            color=discord.Color.red()
        )

        embed.add_field(name="Member", value=f"{member} (`{member.id}`)", inline=False)
        embed.add_field(name="Username", value=member.name, inline=False)
        embed.add_field(name="Banned By", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Ban Type", value=ban_type, inline=False)
        embed.add_field(name="Duration", value=duration, inline=False)
        embed.add_field(name="Rule(s) Broken", value=rules, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Evidence", value=evidence, inline=False)
        embed.add_field(name="Previous Warnings", value=warnings, inline=False)
        embed.add_field(
            name="Time",
            value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>",
            inline=False
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        log_channel = interaction.guild.get_channel(BAN_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=embed)

    # --------------------------------------------------
    # /kick
    # --------------------------------------------------
    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="The member to kick", reason="Reason for the kick")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if not interaction.user.guild_permissions.kick_members:
            return await interaction.response.send_message("You don't have permission to kick members.", ephemeral=True)

        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 {member} has been kicked.\nReason: {reason}")

    # --------------------------------------------------
    # /addrole
    # --------------------------------------------------
    @app_commands.command(name="addrole", description="Add a role to a member.")
    @app_commands.describe(member="The member", role="The role to add")
    async def addrole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message("You don't have permission to manage roles.", ephemeral=True)

        await member.add_roles(role)
        await interaction.response.send_message(f"✅ Added **{role.name}** to **{member}**.")

    # --------------------------------------------------
    # /removerole
    # --------------------------------------------------
    @app_commands.command(name="removerole", description="Remove a role from a member.")
    @app_commands.describe(member="The member", role="The role to remove")
    async def removerole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message("You don't have permission to manage roles.", ephemeral=True)

        await member.remove_roles(role)
        await interaction.response.send_message(f"❌ Removed **{role.name}** from **{member}**.")

    # --------------------------------------------------
    # /timeout
    # --------------------------------------------------
    @app_commands.command(name="timeout", description="Timeout a member.")
    @app_commands.describe(member="The member", duration="Duration in seconds")
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: int):
        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("You don't have permission to timeout members.", ephemeral=True)

        until = discord.utils.utcnow() + discord.timedelta(seconds=duration)
        await member.timeout(until)
        await interaction.response.send_message(f"⏳ {member} has been timed out for {duration} seconds.")

# --------------------------------------------------
# SETUP
# --------------------------------------------------

async def setup(bot):
    await bot.add_cog(Moderation(bot))
