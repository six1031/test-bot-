import discord
from discord.ext import commands
from discord import app_commands

from utils.tree_image import generate_tree_image
from utils.debug import debug_log, debug_exception
from database.relationships import (
    add_relationship,
    remove_relationship,
    get_relationships,
    get_marriage,
    create_marriage,
    delete_marriage,
    get_spouse,
    is_married,
)


# --------------------------------------------------
# MARRIAGE PROPOSAL VIEW
# --------------------------------------------------

class MarriageProposalView(discord.ui.View):
    def __init__(self, proposer_id: int, partner_id: int):
        super().__init__(timeout=300)
        self.proposer_id = proposer_id
        self.partner_id = partner_id
        self.message: discord.Message | None = None

    async def _disable(self, interaction: discord.Interaction, new_content: str | None = None):
        for child in self.children:
            child.disabled = True
        if new_content is not None:
            await interaction.message.edit(content=new_content, view=self)
        else:
            await interaction.message.edit(view=self)

    @discord.ui.button(
        label="✅ Accept",
        style=discord.ButtonStyle.success,
        custom_id="marriage_accept",
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.partner_id:
            return await interaction.response.send_message(
                "❌ Only the proposed partner can respond to this.",
                ephemeral=True,
            )

        if await is_married(self.proposer_id) or await is_married(self.partner_id):
            await interaction.response.send_message(
                "❌ One of you is already married.",
                ephemeral=True,
            )
            return await self._disable(interaction)

        await create_marriage(self.proposer_id, self.partner_id)
        await add_relationship(self.proposer_id, self.partner_id, "spouse")
        await add_relationship(self.partner_id, self.proposer_id, "spouse")

        proposer = interaction.guild.get_member(self.proposer_id)
        partner = interaction.guild.get_member(self.partner_id)

        await interaction.response.send_message(
            f"💍 You accepted! You are now married to {proposer.mention}.",
            ephemeral=True,
        )

        await self._disable(
            interaction,
            new_content=f"💍 {proposer.mention} is now married to {partner.mention}!",
        )

    @discord.ui.button(
        label="❌ Decline",
        style=discord.ButtonStyle.danger,
        custom_id="marriage_decline",
    )
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.partner_id:
            return await interaction.response.send_message(
                "❌ Only the proposed partner can respond to this.",
                ephemeral=True,
            )

        proposer = interaction.guild.get_member(self.proposer_id)
        partner = interaction.guild.get_member(self.partner_id)

        await interaction.response.send_message(
            "💔 You declined the proposal.",
            ephemeral=True,
        )

        await self._disable(
            interaction,
            new_content=f"💔 {partner.mention} declined {proposer.mention}'s marriage proposal.",
        )

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="⏰ This marriage proposal has expired.",
                    view=None,
                )
            except discord.HTTPException:
                pass


# --------------------------------------------------
# MAIN COG
# --------------------------------------------------

class Relationships(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------------------------------
    # ADD RELATIONSHIP
    # --------------------------------------------------

    @app_commands.command(
        name="addrelationship",
        description="Add a relationship to your tree."
    )
    @app_commands.describe(
        partner="The user you want to add",
        rtype="spouse / caregiver / little / middle / sibling / handler / pet"
    )
    async def addrelationship(
        self,
        interaction: discord.Interaction,
        partner: discord.Member,
        rtype: str
    ):

        rtype = rtype.lower()
        valid = ["spouse", "caregiver", "little", "middle", "sibling", "handler", "pet"]

        if rtype not in valid:
            return await interaction.response.send_message(
                "❌ Invalid type. Use: spouse, caregiver, little, middle, sibling, handler, pet",
                ephemeral=True
            )

        if rtype == "spouse":
            return await interaction.response.send_message(
                "❌ Use `/marry` to add a spouse via proposal.",
                ephemeral=True
            )

        await add_relationship(interaction.user.id, partner.id, rtype)

        await interaction.response.send_message(
            f"✅ Added **{rtype}**: {partner.display_name}",
            ephemeral=True
        )

    # --------------------------------------------------
    # REMOVE RELATIONSHIP
    # --------------------------------------------------

    @app_commands.command(
        name="removerelationship",
        description="Remove a relationship from your tree."
    )
    async def removerelationship(
        self,
        interaction: discord.Interaction,
        partner: discord.Member
    ):

        result = await remove_relationship(interaction.user.id, partner.id)

        if result == "DELETE 0":
            return await interaction.response.send_message(
                "❌ That user was not in your tree.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"🗑 Removed {partner.display_name} from your tree.",
            ephemeral=True
        )

    # --------------------------------------------------
    # MARRY COMMAND
    # --------------------------------------------------

    @app_commands.command(
        name="marry",
        description="Propose marriage to another user."
    )
    @app_commands.describe(
        partner="The user you want to marry"
    )
    async def marry(
        self,
        interaction: discord.Interaction,
        partner: discord.Member
    ):

        if partner.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ You cannot marry yourself.",
                ephemeral=True
            )

        if partner.bot:
            return await interaction.response.send_message(
                "❌ You cannot marry a bot.",
                ephemeral=True
            )

        if await is_married(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You are already married.",
                ephemeral=True
            )

        if await is_married(partner.id):
            return await interaction.response.send_message(
                "❌ That user is already married.",
                ephemeral=True
            )

        view = MarriageProposalView(
            proposer_id=interaction.user.id,
            partner_id=partner.id,
        )

        await interaction.response.send_message(
            f"💍 {interaction.user.mention} wants to marry {partner.mention}!\n"
            f"{partner.mention}, do you accept?",
            view=view,
        )

        view.message = await interaction.original_response()

    # --------------------------------------------------
    # DIVORCE COMMAND
    # --------------------------------------------------

    @app_commands.command(
        name="divorce",
        description="Divorce your current spouse."
    )
    async def divorce(
        self,
        interaction: discord.Interaction
    ):

        marriage = await get_marriage(interaction.user.id)

        if not marriage:
            return await interaction.response.send_message(
                "❌ You are not currently married.",
                ephemeral=True
            )

        user1 = marriage["user1_id"]
        user2 = marriage["user2_id"]

        await delete_marriage(marriage["id"])
        await remove_relationship(user1, user2)
        await remove_relationship(user2, user1)

        partner_id = user2 if user1 == interaction.user.id else user1
        partner = interaction.guild.get_member(partner_id)

        if partner:
            msg = f"💔 {interaction.user.mention} is now divorced from {partner.mention}."
        else:
            msg = "💔 Divorce complete."

        await interaction.response.send_message(
            msg,
            ephemeral=False
        )

    # --------------------------------------------------
    # TREE COMMAND
    # --------------------------------------------------

    @app_commands.command(
        name="tree",
        description="Generate your pastel family tree."
    )
    async def tree(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):

        await debug_log(
            self.bot,
            "🌳 `/tree` command started.",
            "INFO"
        )

        try:

            # ------------------------------------------
            # DEFER DISCORD INTERACTION
            # ------------------------------------------

            await interaction.response.defer(thinking=True)

            await debug_log(
                self.bot,
                "✅ Interaction deferred successfully.",
                "SUCCESS"
            )

            # ------------------------------------------
            # TARGET USER
            # ------------------------------------------

            target = user or interaction.user

            await debug_log(
                self.bot,
                f"🔍 Building tree for **{target.display_name}** (`{target.id}`).",
                "DEBUG"
            )

            # ------------------------------------------
            # DATABASE
            # ------------------------------------------

            await debug_log(
                self.bot,
                "🔄 Getting relationships from PostgreSQL...",
                "DEBUG"
            )

            rows = await get_relationships(target.id)

            await debug_log(
                self.bot,
                f"✅ Database returned **{len(rows)}** relationships.",
                "SUCCESS"
            )

            if not rows:

                await debug_log(
                    self.bot,
                    "⚠️ User has no relationships.",
                    "WARNING"
                )

                return await interaction.edit_original_response(
                    content="❌ You have no relationships yet."
                )

            # ------------------------------------------
            # BUILD RELATIONSHIP LISTS
            # ------------------------------------------

            await debug_log(
                self.bot,
                "🔄 Processing relationships...",
                "DEBUG"
            )

            spouse = None
            caregivers = []
            littles = []
            middles = []
            siblings = []
            handler = None
            pets = []

            for row in rows:

                partner_id = row.get("partner_id")
                rtype = row.get("relationship_type")

                if not partner_id or not rtype:
                    continue

                partner = interaction.guild.get_member(partner_id)

                if not partner:
                    continue

                if rtype == "spouse":
                    spouse = partner.display_name

                elif rtype == "caregiver":
                    caregivers.append(partner.display_name)

                elif rtype == "little":
                    littles.append(partner.display_name)

                elif rtype == "middle":
                    middles.append(partner.display_name)

                elif rtype == "sibling":
                    siblings.append(partner.display_name)

                elif rtype == "handler":
                    handler = partner.display_name

                elif rtype == "pet":
                    pets.append(partner.display_name)

            await debug_log(
                self.bot,
                (
                    f"✅ Relationships processed.\n"
                    f"Spouse: {spouse}\n"
                    f"Caregivers: {len(caregivers)}\n"
                    f"Littles: {len(littles)}\n"
                    f"Middles: {len(middles)}\n"
                    f"Siblings: {len(siblings)}\n"
                    f"Handler: {handler}\n"
                    f"Pets: {len(pets)}"
                ),
                "SUCCESS"
            )

            # ------------------------------------------
            # GENERATE IMAGE
            # ------------------------------------------

            await debug_log(
                self.bot,
                "🖼️ Starting tree image generation...",
                "DEBUG"
            )

            jpeg_bytes = generate_tree_image(
                user_name=target.display_name,
                spouse_name=spouse,
                caregivers=caregivers,
                littles=littles,
                middles=middles,
                siblings=siblings,
                handler=handler,
                pets=pets,
            )

            await debug_log(
                self.bot,
                "✅ Tree image generated successfully.",
                "SUCCESS"
            )

            # ------------------------------------------
            # SEND IMAGE
            # ------------------------------------------

            await debug_log(
                self.bot,
                "📤 Uploading tree image to Discord...",
                "DEBUG"
            )

            file = discord.File(
                jpeg_bytes,
                filename="family_tree.jpg"
            )

            await interaction.edit_original_response(
                content=f"🌳 Cute pastel family tree for {target.mention}:",
                attachments=[file]
            )

            await debug_log(
                self.bot,
                "✅ `/tree` completed successfully.",
                "SUCCESS"
            )

        except Exception as e:

            await debug_exception(
                self.bot,
                "🌳 `/tree` CRASHED",
                e
            )

            try:

                await interaction.edit_original_response(
                    content=(
                        "❌ Something went wrong while generating "
                        "the family tree. The error has been sent "
                        "to the bot debug channel."
                    )
                )

            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(Relationships(bot))
