        if not row:
            msg = "No recorded message activity yet."
        else:
            now = datetime.now(timezone.utc)
            last = self._utc(row["last_message"])
            since = self._utc(row["afk_since"])
            if since or now - last >= AFK_AFTER:
                start = since or last + AFK_AFTER
                msg = f"🌙 AFK since <t:{int(start.timestamp())}:R>."
                if row["reason"]:
                    msg += f" Reason: {discord.utils.escape_markdown(row['reason'])}"
            else:
                msg = f"🟢 Active in chat; last message <t:{int(last.timestamp())}:R>."
        await interaction.followup.send(f"**{member.display_name}**: {msg}", ephemeral=True)

    @app_commands.command(name="afksetup", description="Set the AFK dashboard's text channel (admin only).")
    @app_commands.describe(channel="Channel to host the automatically updated AFK dashboard")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def afksetup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        me = interaction.guild.me
        perms = channel.permissions_for(me)
        if not (perms.view_channel and perms.send_messages and perms.embed_links and perms.read_message_history):
            return await interaction.response.send_message(
                "I need View Channel, Send Messages, Embed Links and Read Message History there.", ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.db.execute("""
                INSERT INTO afk_dashboards (guild_id, channel_id, message_id)
                VALUES ($1, $2, NULL)
                ON CONFLICT (guild_id) DO UPDATE SET
                    channel_id = EXCLUDED.channel_id,
                    message_id = CASE WHEN afk_dashboards.channel_id = EXCLUDED.channel_id
                        THEN afk_dashboards.message_id ELSE NULL END
            """, interaction.guild.id, channel.id)
            await self.update_dashboard(interaction.guild.id)
            await interaction.followup.send(f"✅ Dashboard configured in {channel.mention}.", ephemeral=True)
        except Exception:
            log.exception("Failed to configure AFK dashboard")
            await interaction.followup.send("Couldn't configure the dashboard. Check database and bot logs.", ephemeral=True)

    @app_commands.command(name="activity", description="Show the server's current chat activity totals.")
    async def activity(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        rows = await self.bot.db.fetch(
            "SELECT last_message, afk_since FROM afk_members WHERE guild_id=$1",
            interaction.guild.id,
        )
        now = datetime.now(timezone.utc)
        active = sum(1 for r in rows if r["afk_since"] is None and now - self._utc(r["last_message"]) < AFK_AFTER)
        await interaction.response.send_message(
            f"🟢 Active: **{active}** | 🌙 AFK: **{len(rows)-active}** | Tracked: **{len(rows)}**\n"
            "Based on messages sent in this server, not Discord presence.", ephemeral=True,
        )

    @tasks.loop(seconds=REFRESH_SECONDS)
    async def refresh_dashboards(self):
        await self._ready.wait()
        try:
            dashboards = await self.bot.db.fetch("SELECT guild_id FROM afk_dashboards")
            for entry in dashboards:
                try:
                    await self.update_dashboard(entry["guild_id"])
                except Exception:
                    log.exception("Failed to refresh AFK dashboard for %s", entry["guild_id"])
        except Exception:
            log.exception("AFK dashboard refresh failed")

    @refresh_dashboards.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()

    async def update_dashboard(self, guild_id: int):
        async with self._update_lock:
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return
            config = await self.bot.db.fetchrow(
                "SELECT channel_id, message_id FROM afk_dashboards WHERE guild_id=$1", guild_id,
            )
            if not config:
                return
            channel = guild.get_channel(config["channel_id"])
            if not isinstance(channel, discord.TextChannel):
                log.warning("AFK dashboard channel missing in guild %s", guild_id)
                return
            rows = await self.bot.db.fetch("""
                SELECT user_id, last_message, afk_since, reason FROM afk_members
                WHERE guild_id=$1 ORDER BY last_message DESC
            """, guild_id)
            now = datetime.now(timezone.utc)
            active, afk = [], []
            for r in rows:
                member = guild.get_member(r["user_id"])
                if member is None:
                    continue  # do not show users who are no longer cached in the server
                last = self._utc(r["last_message"])
                since = self._utc(r["afk_since"])
                if since or now - last >= AFK_AFTER:
                    start = since or last + AFK_AFTER
                    reason = (r["reason"] or "")[:60]
                    extra = f" — {discord.utils.escape_markdown(reason)}" if reason else ""
                    afk.append(f"{member.mention} — <t:{int(start.timestamp())}:R>{extra}")
                else:
                    active.append(f"{member.mention} — <t:{int(last.timestamp())}:R>")
            embed = discord.Embed(
                title="🌙 Pillow Palace | Member Activity",
                description="Based on messages sent in this server, not Discord online status. Members appear after their first tracked message.",
                colour=discord.Colour.blurple(), timestamp=now,
            )
            embed.add_field(name=f"🟢 Active ({len(active)})", value=("\n".join(active[:MAX_LINES])[:1000] or "None"), inline=False)
            embed.add_field(name=f"🌙 AFK ({len(afk)})", value=("\n".join(afk[:MAX_LINES])[:1000] or "None"), inline=False)
            if len(active) > MAX_LINES or len(afk) > MAX_LINES:
                embed.add_field(name="More members", value="Use `/activity` for totals or `/afkstatus` for a member's status.", inline=False)
            embed.set_footer(text="Refreshes every 60 seconds • AFK after 30 minutes")
            msg = None
            if config["message_id"]:
                try:
                    msg = await channel.fetch_message(config["message_id"])
                except discord.NotFound:
                    pass
            if msg:
                await msg.edit(embed=embed)
            else:
                msg = await channel.send(embed=embed)
                await self.bot.db.execute(
                    "UPDATE afk_dashboards SET message_id=$2 WHERE guild_id=$1",
                    guild_id, msg.id,
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(AFK(bot))
