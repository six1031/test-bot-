"""Pillow Palace timezone cog for discord.py 2.x and an asyncpg-style bot.db.

Requires: discord.py>=2.0, Python>=3.9, PostgreSQL, tzdata (recommended).
Install: pip install tzdata
"""
import logging
from datetime import datetime, timezone as utc_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)

POPULAR_ZONES = [
    "Europe/London", "Europe/Dublin", "Europe/Paris", "Europe/Berlin",
    "Europe/Madrid", "Europe/Rome", "Europe/Amsterdam", "Europe/Warsaw",
    "Europe/Athens", "Europe/Istanbul", "Africa/Johannesburg",
    "Africa/Lagos", "Africa/Cairo", "Asia/Dubai", "Asia/Kolkata",
    "Asia/Karachi", "Asia/Dhaka", "Asia/Bangkok", "Asia/Singapore",
    "Asia/Manila", "Asia/Tokyo", "Asia/Seoul", "Asia/Shanghai",
    "Australia/Perth", "Australia/Adelaide", "Australia/Brisbane",
    "Australia/Sydney", "Australia/Melbourne", "Pacific/Auckland",
    "Pacific/Chatham", "Pacific/Fiji", "Pacific/Honolulu",
    "America/Los_Angeles", "America/Denver", "America/Chicago",
    "America/New_York", "America/Toronto", "America/Vancouver",
    "America/Phoenix", "America/Anchorage", "America/Mexico_City",
    "America/Sao_Paulo", "America/Bogota", "America/Argentina/Buenos_Aires",
]

# Convenient city/country terms for autocomplete. Members may also enter any IANA zone.
ALIASES = {
    "uk": "Europe/London", "united kingdom": "Europe/London",
    "england": "Europe/London", "scotland": "Europe/London",
    "new zealand": "Pacific/Auckland", "nz": "Pacific/Auckland",
    "auckland": "Pacific/Auckland", "wellington": "Pacific/Auckland",
    "christchurch": "Pacific/Auckland", "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne", "brisbane": "Australia/Brisbane",
    "perth": "Australia/Perth", "adelaide": "Australia/Adelaide",
    "london": "Europe/London", "dublin": "Europe/Dublin",
    "paris": "Europe/Paris", "berlin": "Europe/Berlin",
    "tokyo": "Asia/Tokyo", "singapore": "Asia/Singapore",
    "new york": "America/New_York", "los angeles": "America/Los_Angeles",
    "chicago": "America/Chicago", "toronto": "America/Toronto",
}


def resolve_zone(value: str) -> str:
    """Resolve aliases and IANA timezone names; raise ValueError for invalid names."""
    raw = value.strip()
    if not raw:
        raise ValueError("Please enter a timezone.")
    candidate = ALIASES.get(raw.casefold(), raw)
    try:
        ZoneInfo(candidate)
        return candidate
    except ZoneInfoNotFoundError:
        pass
    # Accept case-insensitive exact IANA zone names.
    try:
        candidate = next(z for z in available_timezones() if z.casefold() == raw.casefold())
        ZoneInfo(candidate)
        return candidate
    except (StopIteration, ZoneInfoNotFoundError):
        raise ValueError("Unknown timezone. Try `Europe/London`, `Pacific/Auckland`, or a city like `Sydney`.")


def describe_time(zone_name: str):
    local = datetime.now(utc_timezone.utc).astimezone(ZoneInfo(zone_name))
    offset = local.strftime("%z")
    offset = f"UTC{offset[:3]}:{offset[3:]}" if offset else "UTC"
    return local, offset


class TimezoneGroup(app_commands.Group):
    def __init__(self, cog):
        super().__init__(name="timezone", description="Save and manage your local timezone")
        self.cog = cog

    @app_commands.command(name="set", description="Set your timezone by city or timezone name")
    @app_commands.describe(zone="Example: London, New Zealand, or Pacific/Auckland")
    async def set_zone(self, interaction: discord.Interaction, zone: str):
        try:
            name = resolve_zone(zone)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        try:
            await self.cog.bot.db.execute(
                """INSERT INTO member_timezones (user_id, timezone_name)
                   VALUES ($1, $2)
                   ON CONFLICT (user_id) DO UPDATE SET timezone_name=EXCLUDED.timezone_name""",
                interaction.user.id, name,
            )
        except Exception:
            log.exception("Saving timezone failed")
            await interaction.response.send_message("Could not save your timezone. Please try again.", ephemeral=True)
            return
        local, offset = describe_time(name)
        await interaction.response.send_message(
            f"✅ Your timezone is set to **{name}** ({offset}).\n"
            f"Your local time is **{local:%A, %d %B %Y at %H:%M}**.", ephemeral=True,
        )

    @set_zone.autocomplete("zone")
    async def autocomplete_zone(self, interaction: discord.Interaction, current: str):
        needle = current.casefold().strip()
        choices = []
        seen = set()
        for alias, target in ALIASES.items():
            if needle and needle in alias and target not in seen:
                seen.add(target)
                choices.append(app_commands.Choice(name=f"{alias.title()} — {target}"[:100], value=target))
        for zone in POPULAR_ZONES:
            if (not needle or needle in zone.casefold() or needle in zone.split("/")[-1].replace("_", " ").casefold()) and zone not in seen:
                seen.add(zone)
                choices.append(app_commands.Choice(name=zone, value=zone))
        if len(choices) < 25 and needle:
            try:
                for zone in sorted(available_timezones()):
                    if needle in zone.casefold() and zone not in seen:
                        seen.add(zone)
                        choices.append(app_commands.Choice(name=zone[:100], value=zone))
                        if len(choices) >= 25:
                            break
            except Exception:
                pass
        return choices[:25]

    @app_commands.command(name="setmember", description="Admin: set another member's timezone")
    @app_commands.describe(member="Member whose timezone you want to set", zone="City or IANA timezone, e.g. Auckland or Pacific/Auckland")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_member_zone(self, interaction: discord.Interaction, member: discord.Member, zone: str):
        if interaction.guild is None:
            await interaction.response.send_message("This command only works in a server.", ephemeral=True)
            return
        try:
            name = resolve_zone(zone)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        try:
            await self.cog.bot.db.execute(
                """INSERT INTO member_timezones (user_id, timezone_name)
                   VALUES ($1, $2)
                   ON CONFLICT (user_id) DO UPDATE SET timezone_name=EXCLUDED.timezone_name""",
                member.id, name,
            )
            local, offset = describe_time(name)
        except Exception:
            log.exception("Admin timezone update failed")
            await interaction.response.send_message("Could not update that member's timezone.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Set {member.mention}'s timezone to **{name}** ({offset}).\n"
            f"Their current local time is **{local:%A, %d %B %Y at %H:%M}**.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @set_member_zone.autocomplete("zone")
    async def autocomplete_member_zone(self, interaction: discord.Interaction, current: str):
        return await self.autocomplete_zone(interaction, current)

    @set_member_zone.error
    async def set_member_zone_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            message = "Only server administrators can set another member's timezone."
        else:
            log.error("Timezone admin command error: %s", error)
            message = "Something went wrong while updating the timezone."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="view", description="See your saved timezone")
    async def view_zone(self, interaction: discord.Interaction):
        await self.cog.show_time(interaction, interaction.user, private=True)

    @app_commands.command(name="remove", description="Remove your saved timezone")
    async def remove_zone(self, interaction: discord.Interaction):
        try:
            await self.cog.bot.db.execute("DELETE FROM member_timezones WHERE user_id=$1", interaction.user.id)
        except Exception:
            log.exception("Removing timezone failed")
            await interaction.response.send_message("Could not remove your timezone.", ephemeral=True)
            return
        await interaction.response.send_message("🗑️ Your saved timezone has been removed.", ephemeral=True)


class Timezones(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.timezone_group = TimezoneGroup(self)

    async def cog_load(self):
        await self.bot.db.execute(
            """CREATE TABLE IF NOT EXISTS member_timezones (
                user_id BIGINT PRIMARY KEY,
                timezone_name TEXT NOT NULL
            )"""
        )
        self.bot.tree.add_command(self.timezone_group)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.timezone_group.name)

    async def get_zone(self, user_id: int):
        row = await self.bot.db.fetchrow(
            "SELECT timezone_name FROM member_timezones WHERE user_id=$1", user_id
        )
        return row["timezone_name"] if row else None

    async def show_time(self, interaction: discord.Interaction, member: discord.abc.User, private=False):
        try:
            zone_name = await self.get_zone(member.id)
        except Exception:
            log.exception("Fetching timezone failed")
            await interaction.response.send_message("Could not read the saved timezone.", ephemeral=True)
            return
        if not zone_name:
            await interaction.response.send_message(
                f"{member.mention} hasn't set a timezone yet. They can use `/timezone set`.",
                ephemeral=True,
            )
            return
        try:
            local, offset = describe_time(zone_name)
        except ZoneInfoNotFoundError:
            await interaction.response.send_message("That timezone is unavailable on the bot host. Install `tzdata`.", ephemeral=True)
            return
        embed = discord.Embed(title="🌍 Pillow Palace | Local Time", color=discord.Color.purple())
        embed.description = (
            f"**Member:** {member.mention}\n"
            f"**Time:** {local:%H:%M:%S}\n"
            f"**Date:** {local:%A, %d %B %Y}\n"
            f"**Timezone:** `{zone_name}` ({offset}, {local.tzname()})"
        )
        await interaction.response.send_message(embed=embed, ephemeral=private)

    @app_commands.command(name="time", description="Check your own or another member's local time and date")
    @app_commands.describe(member="Optional member whose time you want to see")
    async def time(self, interaction: discord.Interaction, member: discord.Member = None):
        await self.show_time(interaction, member or interaction.user)

    @app_commands.command(name="timecompare", description="Compare your time with another member's")
    @app_commands.describe(member="Member to compare with")
    async def timecompare(self, interaction: discord.Interaction, member: discord.Member):
        try:
            own_name = await self.get_zone(interaction.user.id)
            other_name = await self.get_zone(member.id)
        except Exception:
            log.exception("Comparing timezones failed")
            await interaction.response.send_message("Could not retrieve saved timezones.", ephemeral=True)
            return
        if not own_name or not other_name:
            missing = "you" if not own_name else member.display_name
            await interaction.response.send_message(
                f"A timezone is missing for **{missing}**. Use `/timezone set` first.", ephemeral=True,
            )
            return
        try:
            now = datetime.now(utc_timezone.utc)
            own = now.astimezone(ZoneInfo(own_name))
            other = now.astimezone(ZoneInfo(other_name))
        except ZoneInfoNotFoundError:
            await interaction.response.send_message("Timezone data is unavailable. Install `tzdata`.", ephemeral=True)
            return
        embed = discord.Embed(title="🌐 Pillow Palace | Time Comparison", color=discord.Color.purple())
        embed.add_field(name=f"You ({own_name})", value=own.strftime("%a %d %b %Y, %H:%M"), inline=False)
        embed.add_field(name=f"{member.display_name} ({other_name})", value=other.strftime("%a %d %b %Y, %H:%M"), inline=False)
        delta = other.utcoffset() - own.utcoffset()
        hours = abs(int(delta.total_seconds())) // 3600
        mins = (abs(int(delta.total_seconds())) % 3600) // 60
        direction = "ahead of" if delta.total_seconds() > 0 else "behind" if delta.total_seconds() < 0 else "the same time as"
        difference = f"{hours}h {mins}m" if mins else f"{hours}h"
        embed.set_footer(text=f"Their clock is {difference} {direction} yours" if delta.total_seconds() else "Both clocks have the same UTC offset")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Timezones(bot))
