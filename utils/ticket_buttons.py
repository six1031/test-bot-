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
        category = discord.utils.get(guild.categories, name="Tickets")

        if category is None:
            category = await guild.create_category("Tickets")

        channel = await guild.create_text_channel(
            f"{ticket_type}-{interaction.user.name}",
            category=category
        )

        await channel.send(
            f"{interaction.user.mention} opened a **{ticket_type}** ticket."
        )
