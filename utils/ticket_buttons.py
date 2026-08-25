import discord

class TicketTypeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Report", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Creating a **Report Ticket**…", ephemeral=True
        )
        await self.create_ticket(interaction, "report")

    @discord.ui.button(label="Contact Staff", style=discord.ButtonStyle.primary, emoji="📞")
    async def contact(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Creating a **Contact Staff Ticket**…", ephemeral=True
        )
        await self.create_ticket(interaction, "contact")

    @discord.ui.button(label="Other", style=discord.ButtonStyle.secondary, emoji="❓")
    async def other(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Creating an **Other Ticket**…", ephemeral=True
        )
        await self.create_ticket(interaction, "other")

    async def create_ticket(self, interaction, ticket_type):
              guild = interaction.guild

        settings = await interaction.client.db.get_guild_settings(guild.id)
        print(
            f"TICKET DEBUG: saved_category={settings.get('ticket_category') if settings else None} "
            f"server_categories={[(c.name, c.id) for c in guild.categories]}"
         )

        if not settings or not settings.get("ticket_category"):
            return await interaction.followup.send(
                "❌ Ticket category is not set up yet. Run `/setup` first.",
                ephemeral=True
        )

        category = guild.get_channel(
            settings["ticket_category"]
        )

        if category is None:
            return await interaction.followup.send(
                "❌ The configured ticket category could not be found.",
                ephemeral=True
        )
        channel = await guild.create_text_channel(
            f"{ticket_type}-{interaction.user.name}",
            category=category
        )

        await channel.send(
            f"{interaction.user.mention} opened a **{ticket_type}** ticket."
        )
