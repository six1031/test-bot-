# cogs/relationships.py

import traceback
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
    is_married,
)


# ==================================================
# RELATIONSHIP TYPES
# ==================================================

RELATIONSHIP_CHOICES = [
    app_commands.Choice(
        name="💍 Marriage",
        value="marry",
    ),
    app_commands.Choice(
        name="🧸 Caregiver / CG",
        value="caregiver",
    ),
    app_commands.Choice(
        name="💗 Little",
        value="little",
    ),
    app_commands.Choice(
        name="🐾 Handler",
        value="handler",
    ),
    app_commands.Choice(
        name="🐶 Pet",
        value="pet",
    ),
]


# What gets stored on each person's tree.
#
# Example:
# If I ask someone to be my Caregiver:
#
# My tree:
#   them = caregiver
#
# Their tree:
#   me = little

RELATIONSHIP_PAIRS = {
    "caregiver": (
        "caregiver",
        "little",
    ),
    "little": (
        "little",
        "caregiver",
    ),
    "handler": (
        "handler",
        "pet",
    ),
    "pet": (
        "pet",
        "handler",
    ),
}


# ==================================================
# RELATIONSHIP PROPOSAL VIEW
# ==================================================

class RelationshipProposalView(discord.ui.View):

    def __init__(
        self,
        proposer_id: int,
        partner_id: int,
        relationship_type: str,
    ):
        super().__init__(timeout=300)

        self.proposer_id = proposer_id
        self.partner_id = partner_id
        self.relationship_type = relationship_type

        self.message: discord.Message | None = None

    # --------------------------------------------------
    # DISABLE BUTTONS
    # --------------------------------------------------

    async def _disable(
        self,
        interaction: discord.Interaction | None = None,
        new_content: str | None = None,
    ):
        for child in self.children:
            child.disabled = True

        target_message = self.message

        if interaction and getattr(
            interaction,
            "message",
            None,
        ):
            target_message = interaction.message

        if not target_message:
            return

        try:
            if new_content is not None:
                await target_message.edit(
                    content=new_content,
                    view=self,
                )

            else:
                await target_message.edit(
                    view=self,
                )

        except discord.HTTPException:
            pass

    # --------------------------------------------------
    # ACCEPT
    # --------------------------------------------------

    @discord.ui.button(
        label="✅ Accept",
        style=discord.ButtonStyle.success,
        custom_id="relationship_accept",
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.user.id != self.partner_id:
            return await interaction.response.send_message(
                "❌ Only the selected person can respond to this request.",
                ephemeral=True,
            )

        guild = interaction.guild

        proposer = guild.get_member(
            self.proposer_id
        )

        partner = guild.get_member(
            self.partner_id
        )

        proposer_mention = (
            proposer.mention
            if proposer
            else f"<@{self.proposer_id}>"
        )

        partner_mention = (
            partner.mention
            if partner
            else f"<@{self.partner_id}>"
        )

        # --------------------------------------------------
        # MARRIAGE
        # --------------------------------------------------

        if self.relationship_type == "marry":

            try:
                if await is_married(
                    self.proposer_id
                ):
                    await interaction.response.send_message(
                        "❌ The person who sent this request is already married.",
                        ephemeral=True,
                    )

                    await self._disable(
                        interaction
                    )

                    return

                if await is_married(
                    self.partner_id
                ):
                    await interaction.response.send_message(
                        "❌ You are already married.",
                        ephemeral=True,
                    )

                    await self._disable(
                        interaction
                    )

                    return

            except Exception:
                traceback.print_exc()

                await interaction.response.send_message(
                    "❌ Could not verify marriage status. Try again later.",
                    ephemeral=True,
                )

                await self._disable(
                    interaction
                )

                return

            try:
                await create_marriage(
                    self.proposer_id,
                    self.partner_id,
                )

                await add_relationship(
                    self.proposer_id,
                    self.partner_id,
                    "spouse",
                )

                await add_relationship(
                    self.partner_id,
                    self.proposer_id,
                    "spouse",
                )

            except Exception:
                traceback.print_exc()

                await interaction.response.send_message(
                    "❌ Failed to create the marriage. Check bot logs.",
                    ephemeral=True,
                )

                await self._disable(
                    interaction
                )

                return

            await interaction.response.send_message(
                f"💍 You accepted {proposer_mention}'s marriage proposal!",
                ephemeral=True,
            )

            await self._disable(
                interaction,
                new_content=(
                    f"💍 {proposer_mention} and "
                    f"{partner_mention} are now married!"
                ),
            )

            return

        # --------------------------------------------------
        # CG / LITTLE / HANDLER / PET
        # --------------------------------------------------

        if self.relationship_type not in RELATIONSHIP_PAIRS:
            await interaction.response.send_message(
                "❌ That relationship type is no longer valid.",
                ephemeral=True,
            )

            await self._disable(
                interaction
            )

            return

        proposer_type, partner_type = RELATIONSHIP_PAIRS[
            self.relationship_type
        ]

        try:
            # Relationship as shown on the proposer's tree
            await add_relationship(
                self.proposer_id,
                self.partner_id,
                proposer_type,
            )

            # Matching relationship on the other person's tree
            await add_relationship(
                self.partner_id,
                self.proposer_id,
                partner_type,
            )

        except Exception:
            traceback.print_exc()

            await interaction.response.send_message(
                "❌ Failed to create the relationship. Check bot logs.",
                ephemeral=True,
            )

            await self._disable(
                interaction
            )

            return

        # --------------------------------------------------
        # SUCCESS MESSAGES
        # --------------------------------------------------

        if self.relationship_type == "caregiver":

            public_message = (
                f"🧸 {partner_mention} is now "
                f"{proposer_mention}'s **Caregiver / CG**, "
                f"and {proposer_mention} is their **Little**! 💗"
            )

        elif self.relationship_type == "little":

            public_message = (
                f"💗 {partner_mention} is now "
                f"{proposer_mention}'s **Little**, "
                f"and {proposer_mention} is their "
                f"**Caregiver / CG**! 🧸"
            )

        elif self.relationship_type == "handler":

            public_message = (
                f"🐾 {partner_mention} is now "
                f"{proposer_mention}'s **Handler**, "
                f"and {proposer_mention} is their **Pet**!"
            )

        elif self.relationship_type == "pet":

            public_message = (
                f"🐶 {partner_mention} is now "
                f"{proposer_mention}'s **Pet**, "
                f"and {proposer_mention} is their **Handler**! 🐾"
            )

        else:
            public_message = (
                f"💞 {proposer_mention} and "
                f"{partner_mention} are now connected!"
            )

        await interaction.response.send_message(
            "✅ Relationship accepted!",
            ephemeral=True,
        )

        await self._disable(
            interaction,
            new_content=public_message,
        )

    # --------------------------------------------------
    # DECLINE
    # --------------------------------------------------

    @discord.ui.button(
        label="❌ Decline",
        style=discord.ButtonStyle.danger,
        custom_id="relationship_decline",
    )
    async def decline(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.user.id != self.partner_id:
            return await interaction.response.send_message(
                "❌ Only the selected person can respond to this request.",
                ephemeral=True,
            )

        proposer = interaction.guild.get_member(
            self.proposer_id
        )

        partner = interaction.guild.get_member(
            self.partner_id
        )

        proposer_mention = (
            proposer.mention
            if proposer
            else f"<@{self.proposer_id}>"
        )

        partner_mention = (
            partner.mention
            if partner
            else f"<@{self.partner_id}>"
        )

        await interaction.response.send_message(
            "❌ Relationship request declined.",
            ephemeral=True,
        )

        await self._disable(
            interaction,
            new_content=(
                f"💔 {partner_mention} declined "
                f"{proposer_mention}'s relationship request."
            ),
        )

    # --------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------

    async def on_timeout(self):

        if not self.message:
            return

        try:
            await self.message.edit(
                content="⏰ This relationship request has expired.",
                view=None,
            )

        except discord.HTTPException:
            pass


# ==================================================
# MAIN COG
# ==================================================

class Relationships(commands.Cog):

    def __init__(
        self,
        bot,
    ):
        self.bot = bot

    # ==================================================
    # /RELATIONSHIP
    # ==================================================

    @app_commands.command(
        name="relationship",
        description="Send someone a relationship request.",
    )
    @app_commands.describe(
        relationship_type="The type of relationship you want to create",
        user="The person you want the relationship with",
    )
    @app_commands.choices(
        relationship_type=RELATIONSHIP_CHOICES,
    )
    async def relationship(
        self,
        interaction: discord.Interaction,
        relationship_type: app_commands.Choice[str],
        user: discord.Member,
    ):
        guild = interaction.guild

        # --------------------------------------------------
        # LOAD SERVER SETTINGS
        # --------------------------------------------------

        try:
            settings = await self.bot.db.get_guild_settings(
                guild.id
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                (
                    "⚠️ Could not load server settings. "
                    "Ask an admin to run `/setup`."
                ),
                ephemeral=True,
            )

        if not settings or not settings.get(
            "relationship_channel"
        ):
            return await interaction.response.send_message(
                (
                    "⚠️ The relationship system has not "
                    "been set up yet.\n"
                    "Ask an admin to run `/setup` first."
                ),
                ephemeral=True,
            )

        relationship_channel_id = settings[
            "relationship_channel"
        ]

        # --------------------------------------------------
        # ENFORCE RELATIONSHIP CHANNEL
        # --------------------------------------------------

        if interaction.channel.id != relationship_channel_id:

            return await interaction.response.send_message(
                (
                    "❌ You must use relationship commands in "
                    f"<#{relationship_channel_id}>."
                ),
                ephemeral=True,
            )

        # --------------------------------------------------
        # VALIDATE USERS
        # --------------------------------------------------

        if user.id == interaction.user.id:

            return await interaction.response.send_message(
                "❌ You cannot create a relationship with yourself.",
                ephemeral=True,
            )

        if user.bot:

            return await interaction.response.send_message(
                "❌ You cannot create a relationship with a bot.",
                ephemeral=True,
            )

        selected_type = relationship_type.value

        # --------------------------------------------------
        # MARRIAGE CHECK
        # --------------------------------------------------

        if selected_type == "marry":

            try:
                if await is_married(
                    interaction.user.id
                ):
                    return await interaction.response.send_message(
                        "❌ You are already married.",
                        ephemeral=True,
                    )

                if await is_married(
                    user.id
                ):
                    return await interaction.response.send_message(
                        "❌ That person is already married.",
                        ephemeral=True,
                    )

            except Exception:
                traceback.print_exc()

                return await interaction.response.send_message(
                    "❌ Could not verify marriage status. Try again later.",
                    ephemeral=True,
                )

        # --------------------------------------------------
        # CREATE PROPOSAL
        # --------------------------------------------------

        view = RelationshipProposalView(
            proposer_id=interaction.user.id,
            partner_id=user.id,
            relationship_type=selected_type,
        )

        # --------------------------------------------------
        # PROPOSAL TEXT
        # --------------------------------------------------

        if selected_type == "marry":

            proposal_text = (
                f"💍 {interaction.user.mention} wants to marry "
                f"{user.mention}!\n\n"
                f"{user.mention}, do you accept?"
            )

        elif selected_type == "caregiver":

            proposal_text = (
                f"🧸 {interaction.user.mention} would like "
                f"{user.mention} to be their **Caregiver / CG**.\n\n"
                f"{user.mention}, do you accept this "
                f"**CG/Little** relationship?"
            )

        elif selected_type == "little":

            proposal_text = (
                f"💗 {interaction.user.mention} would like "
                f"{user.mention} to be their **Little**.\n\n"
                f"{user.mention}, do you accept this "
                f"**CG/Little** relationship?"
            )

        elif selected_type == "handler":

            proposal_text = (
                f"🐾 {interaction.user.mention} would like "
                f"{user.mention} to be their **Handler**.\n\n"
                f"{user.mention}, do you accept this "
                f"**Handler/Pet** relationship?"
            )

        elif selected_type == "pet":

            proposal_text = (
                f"🐶 {interaction.user.mention} would like "
                f"{user.mention} to be their **Pet**.\n\n"
                f"{user.mention}, do you accept this "
                f"**Handler/Pet** relationship?"
            )

        else:

            return await interaction.response.send_message(
                "❌ Invalid relationship type.",
                ephemeral=True,
            )

        try:
            await interaction.response.send_message(
                proposal_text,
                view=view,
            )

            view.message = await interaction.original_response()

        except Exception:
            traceback.print_exc()

    # ==================================================
    # REMOVE RELATIONSHIP
    # ==================================================

    @app_commands.command(
        name="removerelationship",
        description="Remove a non-marriage relationship.",
    )
    @app_commands.describe(
        partner="The person you want to remove from your tree",
    )
    async def removerelationship(
        self,
        interaction: discord.Interaction,
        partner: discord.Member,
    ):
        try:
            relationships = await get_relationships(
                interaction.user.id
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ Could not load your relationships.",
                ephemeral=True,
            )

        matching_relationship = None

        for row in relationships:

            if row["partner_id"] == partner.id:
                matching_relationship = row
                break

        if not matching_relationship:

            return await interaction.response.send_message(
                "❌ That person is not in your relationship tree.",
                ephemeral=True,
            )

        if matching_relationship[
            "relationship_type"
        ] == "spouse":

            return await interaction.response.send_message(
                "❌ Use `/divorce` to remove a marriage.",
                ephemeral=True,
            )

        try:
            # Remove both sides of the relationship
            await remove_relationship(
                interaction.user.id,
                partner.id,
            )

            await remove_relationship(
                partner.id,
                interaction.user.id,
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ Failed to remove the relationship.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            (
                f"🗑 Removed the relationship between "
                f"{interaction.user.mention} and {partner.mention}."
            ),
            ephemeral=False,
        )

    # ==================================================
    # FORCE MARRY
    # ==================================================

    @app_commands.command(
        name="forcemarry",
        description="Force two users to marry. Admin role only.",
    )
    @app_commands.describe(
        user1="The first user",
        user2="The second user",
    )
    async def forcemarry(
        self,
        interaction: discord.Interaction,
        user1: discord.Member,
        user2: discord.Member,
    ):
        # --------------------------------------------------
        # LOAD SETTINGS
        # --------------------------------------------------

        try:
            settings = await self.bot.db.get_guild_settings(
                interaction.guild.id
            )

        except Exception as e:
            traceback.print_exc()

            await debug_exception(
                self.bot,
                "💍 `/forcemarry` SETTINGS ERROR",
                e,
            )

            return await interaction.response.send_message(
                "❌ Could not load server settings.",
                ephemeral=True,
            )

        if not settings:

            return await interaction.response.send_message(
                "❌ Server settings have not been configured.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # ADMIN ROLE
        # --------------------------------------------------

        admin_role_id = settings.get(
            "admin_role"
        )

        if not admin_role_id:

            return await interaction.response.send_message(
                (
                    "❌ No Admin role has been configured.\n"
                    "Run `/setup` first."
                ),
                ephemeral=True,
            )

        user_role_ids = [
            role.id
            for role in interaction.user.roles
        ]

        if admin_role_id not in user_role_ids:

            return await interaction.response.send_message(
                (
                    "❌ Only members with the configured "
                    "**Admin role** can use `/forcemarry`."
                ),
                ephemeral=True,
            )

        # --------------------------------------------------
        # VALIDATE
        # --------------------------------------------------

        if user1.id == user2.id:

            return await interaction.response.send_message(
                "❌ You cannot marry someone to themselves.",
                ephemeral=True,
            )

        if user1.bot or user2.bot:

            return await interaction.response.send_message(
                "❌ Bots cannot be married.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # EXISTING MARRIAGES
        # --------------------------------------------------

        try:
            if await is_married(
                user1.id
            ):
                return await interaction.response.send_message(
                    f"❌ {user1.mention} is already married.",
                    ephemeral=True,
                )

            if await is_married(
                user2.id
            ):
                return await interaction.response.send_message(
                    f"❌ {user2.mention} is already married.",
                    ephemeral=True,
                )

        except Exception as e:
            traceback.print_exc()

            await debug_exception(
                self.bot,
                "💍 `/forcemarry` MARRIAGE CHECK ERROR",
                e,
            )

            return await interaction.response.send_message(
                "❌ Could not check existing marriages.",
                ephemeral=True,
            )

        # --------------------------------------------------
        # CREATE MARRIAGE
        # --------------------------------------------------

        try:
            await create_marriage(
                user1.id,
                user2.id,
            )

            await add_relationship(
                user1.id,
                user2.id,
                "spouse",
            )

            await add_relationship(
                user2.id,
                user1.id,
                "spouse",
            )

        except Exception as e:
            traceback.print_exc()

            await debug_exception(
                self.bot,
                "💍 `/forcemarry` CRASHED",
                e,
            )

            return await interaction.response.send_message(
                "❌ Failed to create the forced marriage.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            (
                f"💍 {user1.mention} and {user2.mention} "
                f"have been married by {interaction.user.mention}!"
            )
        )

    # ==================================================
    # DIVORCE
    # ==================================================

    @app_commands.command(
        name="divorce",
        description="Divorce your current spouse.",
    )
    async def divorce(
        self,
        interaction: discord.Interaction,
    ):
        try:
            marriage = await get_marriage(
                interaction.user.id
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ Could not check marriage status. Try again later.",
                ephemeral=True,
            )

        if not marriage:

            return await interaction.response.send_message(
                "❌ You are not currently married.",
                ephemeral=True,
            )

        user1 = marriage[
            "user1_id"
        ]

        user2 = marriage[
            "user2_id"
        ]

        try:
            await delete_marriage(
                marriage["id"]
            )

            await remove_relationship(
                user1,
                user2,
            )

            await remove_relationship(
                user2,
                user1,
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                "❌ Failed to process divorce. Check bot logs.",
                ephemeral=True,
            )

        partner_id = (
            user2
            if user1 == interaction.user.id
            else user1
        )

        partner = interaction.guild.get_member(
            partner_id
        )

        if partner:

            message = (
                f"💔 {interaction.user.mention} is now "
                f"divorced from {partner.mention}."
            )

        else:

            message = "💔 Divorce complete."

        await interaction.response.send_message(
            message,
            ephemeral=False,
        )

    # ==================================================
    # TREE
    # ==================================================

    @app_commands.command(
        name="tree",
        description="Generate your pastel relationship tree.",
    )
    @app_commands.describe(
        user="Optional member whose tree you want to view",
    )
    async def tree(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):
        # --------------------------------------------------
        # LOAD SETTINGS
        # --------------------------------------------------

        try:
            settings = await self.bot.db.get_guild_settings(
                interaction.guild.id
            )

        except Exception:
            traceback.print_exc()

            return await interaction.response.send_message(
                (
                    "⚠️ Could not load server settings. "
                    "Ask an admin to run `/setup`."
                ),
                ephemeral=True,
            )

        if not settings or not settings.get(
            "relationship_channel"
        ):

            return await interaction.response.send_message(
                (
                    "⚠️ The relationship system has not "
                    "been set up yet.\n"
                    "Ask an admin to run `/setup` first."
                ),
                ephemeral=True,
            )

        relationship_channel_id = settings[
            "relationship_channel"
        ]

        # --------------------------------------------------
        # ENFORCE RELATIONSHIP CHANNEL
        # --------------------------------------------------

        if interaction.channel.id != relationship_channel_id:

            return await interaction.response.send_message(
                (
                    "❌ You must use this command in "
                    f"<#{relationship_channel_id}>."
                ),
                ephemeral=True,
            )

        await debug_log(
            self.bot,
            "🌳 `/tree` command started.",
            "INFO",
        )

        try:
            await interaction.response.defer(
                thinking=True
            )

            target = (
                user
                or interaction.user
            )

            rows = await get_relationships(
                target.id
            )

            if not rows:

                return await interaction.edit_original_response(
                    content="❌ You have no relationships yet."
                )

            spouse = None

            caregivers = []
            littles = []
            middles = []
            siblings = []

            handler = None

            pets = []

            # --------------------------------------------------
            # BUILD TREE DATA
            # --------------------------------------------------

            for row in rows:

                partner_id = row[
                    "partner_id"
                ]

                relationship_type = row[
                    "relationship_type"
                ]

                partner = interaction.guild.get_member(
                    partner_id
                )

                if not partner:
                    continue

                if relationship_type == "spouse":

                    spouse = partner.display_name

                elif relationship_type == "caregiver":

                    caregivers.append(
                        partner.display_name
                    )

                elif relationship_type == "little":

                    littles.append(
                        partner.display_name
                    )

                elif relationship_type == "middle":

                    middles.append(
                        partner.display_name
                    )

                elif relationship_type == "sibling":

                    siblings.append(
                        partner.display_name
                    )

                elif relationship_type == "handler":

                    handler = partner.display_name

                elif relationship_type == "pet":

                    pets.append(
                        partner.display_name
                    )

            # --------------------------------------------------
            # GENERATE IMAGE
            # --------------------------------------------------

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

            file = discord.File(
                jpeg_bytes,
                filename="family_tree.jpg",
            )

            await interaction.edit_original_response(
                content=(
                    "🌳 Relationship tree "
                    f"for {target.mention}:"
                ),
                attachments=[
                    file
                ],
            )

        except Exception as e:

            await debug_exception(
                self.bot,
                "🌳 `/tree` CRASHED",
                e,
            )

            traceback.print_exc()

            try:
                await interaction.edit_original_response(
                    content=(
                        "❌ Something went wrong while generating "
                        "the relationship tree."
                    )
                )

            except Exception:
                pass


# ==================================================
# LOAD COG
# ==================================================

async def setup(
    bot,
):
    await bot.add_cog(
        Relationships(bot)
    )
