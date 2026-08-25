import traceback
import discord

from discord.ext import commands
from discord import app_commands

from utils.tree_image import generate_tree_image
from utils.debug import debug_log, debug_exception

from database.relationships import (
    init_relationship_tables,
    add_relationship,
    remove_relationship,
    relationship_exists,
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


NON_MARRIAGE_CHOICES = [
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


# ==================================================
# MATCHING RELATIONSHIP TYPES
# ==================================================

RELATIONSHIP_PAIRS = {

    # If I select someone as my caregiver:
    #
    # My tree -> them = caregiver
    # Their tree -> me = little

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

class RelationshipProposalView(
    discord.ui.View
):

    def __init__(
        self,
        proposer_id: int,
        partner_id: int,
        relationship_type: str,
    ):
        super().__init__(
            timeout=300
        )

        self.proposer_id = (
            proposer_id
        )

        self.partner_id = (
            partner_id
        )

        self.relationship_type = (
            relationship_type
        )

        self.message: (
            discord.Message | None
        ) = None

    # --------------------------------------------------
    # DISABLE BUTTONS
    # --------------------------------------------------

    async def _disable(
        self,
        interaction: (
            discord.Interaction | None
        ) = None,
        new_content: (
            str | None
        ) = None,
    ):
        for child in self.children:
            child.disabled = True

        target_message = (
            self.message
        )

        if (
            interaction
            and getattr(
                interaction,
                "message",
                None,
            )
        ):
            target_message = (
                interaction.message
            )

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

    # ==================================================
    # ACCEPT
    # ==================================================

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

        if (
            interaction.user.id
            != self.partner_id
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Only the selected "
                        "person can respond "
                        "to this request."
                    ),
                    ephemeral=True,
                )
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

        # ==================================================
        # MARRIAGE
        # ==================================================

        if (
            self.relationship_type
            == "marry"
        ):

            try:

                if await is_married(
                    self.proposer_id
                ):

                    await (
                        interaction.response
                        .send_message(
                            (
                                "❌ The person "
                                "who sent this "
                                "request is already "
                                "married."
                            ),
                            ephemeral=True,
                        )
                    )

                    await self._disable(
                        interaction
                    )

                    return

                if await is_married(
                    self.partner_id
                ):

                    await (
                        interaction.response
                        .send_message(
                            (
                                "❌ You are "
                                "already married."
                            ),
                            ephemeral=True,
                        )
                    )

                    await self._disable(
                        interaction
                    )

                    return

            except Exception:

                traceback.print_exc()

                await (
                    interaction.response
                    .send_message(
                        (
                            "❌ Could not verify "
                            "marriage status. "
                            "Try again later."
                        ),
                        ephemeral=True,
                    )
                )

                await self._disable(
                    interaction
                )

                return

            # --------------------------------------------------
            # CREATE MARRIAGE
            #
            # IMPORTANT:
            # Only adds the spouse type.
            #
            # If these users are already Little/CG or
            # Pet/Handler, those relationships remain.
            # --------------------------------------------------

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

                await (
                    interaction.response
                    .send_message(
                        (
                            "❌ Failed to create "
                            "the marriage. "
                            "Check bot logs."
                        ),
                        ephemeral=True,
                    )
                )

                await self._disable(
                    interaction
                )

                return

            await (
                interaction.response
                .send_message(
                    (
                        f"💍 You accepted "
                        f"{proposer_mention}'s "
                        f"marriage proposal!"
                    ),
                    ephemeral=True,
                )
            )

            await self._disable(
                interaction,
                new_content=(
                    f"💍 {proposer_mention} "
                    f"and {partner_mention} "
                    f"are now married!"
                ),
            )

            return

        # ==================================================
        # NON-MARRIAGE RELATIONSHIPS
        # ==================================================

        if (
            self.relationship_type
            not in RELATIONSHIP_PAIRS
        ):

            await (
                interaction.response
                .send_message(
                    (
                        "❌ That relationship "
                        "type is no longer valid."
                    ),
                    ephemeral=True,
                )
            )

            await self._disable(
                interaction
            )

            return

        proposer_type, partner_type = (
            RELATIONSHIP_PAIRS[
                self.relationship_type
            ]
        )

        try:

            # --------------------------------------------------
            # PROPOSER SIDE
            # --------------------------------------------------

            await add_relationship(
                self.proposer_id,
                self.partner_id,
                proposer_type,
            )

            # --------------------------------------------------
            # PARTNER SIDE
            # --------------------------------------------------

            await add_relationship(
                self.partner_id,
                self.proposer_id,
                partner_type,
            )

        except Exception:

            traceback.print_exc()

            await (
                interaction.response
                .send_message(
                    (
                        "❌ Failed to create "
                        "the relationship. "
                        "Check bot logs."
                    ),
                    ephemeral=True,
                )
            )

            await self._disable(
                interaction
            )

            return

        # ==================================================
        # SUCCESS TEXT
        # ==================================================

        if (
            self.relationship_type
            == "caregiver"
        ):

            public_message = (
                f"🧸 {partner_mention} "
                f"is now "
                f"{proposer_mention}'s "
                f"**Caregiver / CG**, "
                f"and {proposer_mention} "
                f"is their **Little**! 💗"
            )

        elif (
            self.relationship_type
            == "little"
        ):

            public_message = (
                f"💗 {partner_mention} "
                f"is now "
                f"{proposer_mention}'s "
                f"**Little**, "
                f"and {proposer_mention} "
                f"is their "
                f"**Caregiver / CG**! 🧸"
            )

        elif (
            self.relationship_type
            == "handler"
        ):

            public_message = (
                f"🐾 {partner_mention} "
                f"is now "
                f"{proposer_mention}'s "
                f"**Handler**, "
                f"and {proposer_mention} "
                f"is their **Pet**! 🐶"
            )

        elif (
            self.relationship_type
            == "pet"
        ):

            public_message = (
                f"🐶 {partner_mention} "
                f"is now "
                f"{proposer_mention}'s "
                f"**Pet**, "
                f"and {proposer_mention} "
                f"is their "
                f"**Handler**! 🐾"
            )

        else:

            public_message = (
                f"💞 {proposer_mention} "
                f"and {partner_mention} "
                f"are now connected!"
            )

        await (
            interaction.response
            .send_message(
                "✅ Relationship accepted!",
                ephemeral=True,
            )
        )

        await self._disable(
            interaction,
            new_content=public_message,
        )

    # ==================================================
    # DECLINE
    # ==================================================

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

        if (
            interaction.user.id
            != self.partner_id
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Only the selected "
                        "person can respond "
                        "to this request."
                    ),
                    ephemeral=True,
                )
            )

        proposer = (
            interaction.guild
            .get_member(
                self.proposer_id
            )
        )

        partner = (
            interaction.guild
            .get_member(
                self.partner_id
            )
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

        await (
            interaction.response
            .send_message(
                (
                    "❌ Relationship "
                    "request declined."
                ),
                ephemeral=True,
            )
        )

        await self._disable(
            interaction,
            new_content=(
                f"💔 {partner_mention} "
                f"declined "
                f"{proposer_mention}'s "
                f"relationship request."
            ),
        )

    # ==================================================
    # TIMEOUT
    # ==================================================

    async def on_timeout(
        self,
    ):

        if not self.message:
            return

        try:

            await self.message.edit(
                content=(
                    "⏰ This relationship "
                    "request has expired."
                ),
                view=None,
            )

        except discord.HTTPException:
            pass


# ==================================================
# MAIN COG
# ==================================================

class Relationships(
    commands.Cog
):

    def __init__(
        self,
        bot,
    ):
        self.bot = bot

    # ==================================================
    # RUN RELATIONSHIP DATABASE MIGRATION
    # ==================================================

    async def cog_load(
        self,
    ):

        await init_relationship_tables()

        print(
            "✅ Relationship database ready."
        )

    # ==================================================
    # /RELATIONSHIP
    # ==================================================

    @app_commands.command(
        name="relationship",
        description=(
            "Send someone a relationship request."
        ),
    )
    @app_commands.describe(
        relationship_type=(
            "The relationship you want"
        ),
        user=(
            "The person you want the relationship with"
        ),
    )
    @app_commands.choices(
        relationship_type=(
            RELATIONSHIP_CHOICES
        ),
    )
    async def relationship(
        self,
        interaction: discord.Interaction,
        relationship_type: (
            app_commands.Choice[str]
        ),
        user: discord.Member,
    ):

        guild = interaction.guild

        # --------------------------------------------------
        # LOAD SERVER SETTINGS
        # --------------------------------------------------

        try:

            settings = (
                await self.bot.db
                .get_guild_settings(
                    guild.id
                )
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "⚠️ Could not load "
                        "server settings. "
                        "Ask an admin to run "
                        "`/setup`."
                    ),
                    ephemeral=True,
                )
            )

        if (
            not settings
            or not settings.get(
                "relationship_channel"
            )
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "⚠️ The relationship "
                        "system has not been "
                        "set up yet.\n"
                        "Ask an admin to run "
                        "`/setup` first."
                    ),
                    ephemeral=True,
                )
            )

        relationship_channel_id = (
            settings[
                "relationship_channel"
            ]
        )

        # --------------------------------------------------
        # ENFORCE CHANNEL
        # --------------------------------------------------

        if (
            interaction.channel.id
            != relationship_channel_id
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You must use "
                        "relationship commands in "
                        f"<#{relationship_channel_id}>."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # VALIDATE USER
        # --------------------------------------------------

        if (
            user.id
            == interaction.user.id
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You cannot create "
                        "a relationship with yourself."
                    ),
                    ephemeral=True,
                )
            )

        if user.bot:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You cannot create "
                        "a relationship with a bot."
                    ),
                    ephemeral=True,
                )
            )

        selected_type = (
            relationship_type.value
        )

        # ==================================================
        # MARRIAGE CHECK
        # ==================================================

        if (
            selected_type
            == "marry"
        ):

            try:

                if await is_married(
                    interaction.user.id
                ):

                    return await (
                        interaction.response
                        .send_message(
                            (
                                "❌ You are "
                                "already married."
                            ),
                            ephemeral=True,
                        )
                    )

                if await is_married(
                    user.id
                ):

                    return await (
                        interaction.response
                        .send_message(
                            (
                                "❌ That person "
                                "is already married."
                            ),
                            ephemeral=True,
                        )
                    )

            except Exception:

                traceback.print_exc()

                return await (
                    interaction.response
                    .send_message(
                        (
                            "❌ Could not verify "
                            "marriage status. "
                            "Try again later."
                        ),
                        ephemeral=True,
                    )
                )

        # ==================================================
        # CHECK EXISTING NON-MARRIAGE RELATIONSHIP
        # ==================================================

        else:

            proposer_type, partner_type = (
                RELATIONSHIP_PAIRS[
                    selected_type
                ]
            )

            try:

                exists = (
                    await relationship_exists(
                        interaction.user.id,
                        user.id,
                        proposer_type,
                    )
                )

            except Exception:

                traceback.print_exc()

                return await (
                    interaction.response
                    .send_message(
                        (
                            "❌ Could not check "
                            "existing relationships."
                        ),
                        ephemeral=True,
                    )
                )

            if exists:

                return await (
                    interaction.response
                    .send_message(
                        (
                            "❌ You already have "
                            "that relationship "
                            "with this person."
                        ),
                        ephemeral=True,
                    )
                )

        # ==================================================
        # CREATE PROPOSAL
        # ==================================================

        view = (
            RelationshipProposalView(
                proposer_id=(
                    interaction.user.id
                ),
                partner_id=user.id,
                relationship_type=(
                    selected_type
                ),
            )
        )

        # ==================================================
        # PROPOSAL TEXT
        # ==================================================

        if (
            selected_type
            == "marry"
        ):

            proposal_text = (
                f"💍 {interaction.user.mention} "
                f"wants to marry "
                f"{user.mention}!\n\n"
                f"{user.mention}, "
                f"do you accept?"
            )

        elif (
            selected_type
            == "caregiver"
        ):

            proposal_text = (
                f"🧸 {interaction.user.mention} "
                f"would like {user.mention} "
                f"to be their "
                f"**Caregiver / CG**.\n\n"
                f"{user.mention}, "
                f"do you accept this "
                f"**CG/Little** relationship?"
            )

        elif (
            selected_type
            == "little"
        ):

            proposal_text = (
                f"💗 {interaction.user.mention} "
                f"would like {user.mention} "
                f"to be their **Little**.\n\n"
                f"{user.mention}, "
                f"do you accept this "
                f"**CG/Little** relationship?"
            )

        elif (
            selected_type
            == "handler"
        ):

            proposal_text = (
                f"🐾 {interaction.user.mention} "
                f"would like {user.mention} "
                f"to be their **Handler**.\n\n"
                f"{user.mention}, "
                f"do you accept this "
                f"**Handler/Pet** relationship?"
            )

        elif (
            selected_type
            == "pet"
        ):

            proposal_text = (
                f"🐶 {interaction.user.mention} "
                f"would like {user.mention} "
                f"to be their **Pet**.\n\n"
                f"{user.mention}, "
                f"do you accept this "
                f"**Handler/Pet** relationship?"
            )

        else:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Invalid "
                        "relationship type."
                    ),
                    ephemeral=True,
                )
            )

        try:

            await (
                interaction.response
                .send_message(
                    proposal_text,
                    view=view,
                )
            )

            view.message = (
                await interaction
                .original_response()
            )

        except Exception:

            traceback.print_exc()

    # ==================================================
    # /REMOVERELATIONSHIP
    # ==================================================

    @app_commands.command(
        name="removerelationship",
        description=(
            "Remove one relationship with someone."
        ),
    )
    @app_commands.describe(
        relationship_type=(
            "The relationship you want to remove"
        ),
        user=(
            "The person you want to remove it with"
        ),
    )
    @app_commands.choices(
        relationship_type=(
            NON_MARRIAGE_CHOICES
        ),
    )
    async def removerelationship(
        self,
        interaction: discord.Interaction,
        relationship_type: (
            app_commands.Choice[str]
        ),
        user: discord.Member,
    ):

        selected_type = (
            relationship_type.value
        )

        if (
            selected_type
            not in RELATIONSHIP_PAIRS
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Invalid relationship type."
                    ),
                    ephemeral=True,
                )
            )

        user_type, partner_type = (
            RELATIONSHIP_PAIRS[
                selected_type
            ]
        )

        # --------------------------------------------------
        # CHECK IT EXISTS
        # --------------------------------------------------

        try:

            exists = (
                await relationship_exists(
                    interaction.user.id,
                    user.id,
                    user_type,
                )
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Could not check "
                        "your relationships."
                    ),
                    ephemeral=True,
                )
            )

        if not exists:

            return await (
                interaction.response
                .send_message(
                    (
                        f"❌ {user.mention} "
                        f"is not your "
                        f"**{user_type}**."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # REMOVE ONLY THIS TYPE
        #
        # Marriage/spouse remains untouched.
        # --------------------------------------------------

        try:

            await remove_relationship(
                interaction.user.id,
                user.id,
                user_type,
            )

            await remove_relationship(
                user.id,
                interaction.user.id,
                partner_type,
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Failed to remove "
                        "the relationship."
                    ),
                    ephemeral=True,
                )
            )

        await (
            interaction.response
            .send_message(
                (
                    f"🗑 Removed the "
                    f"**{user_type}** relationship "
                    f"between "
                    f"{interaction.user.mention} "
                    f"and {user.mention}."
                ),
                ephemeral=False,
            )
        )

    # ==================================================
    # /FORCEMARRY
    # ==================================================

    @app_commands.command(
        name="forcemarry",
        description=(
            "Force two users to marry. Admin role only."
        ),
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

            settings = (
                await self.bot.db
                .get_guild_settings(
                    interaction.guild.id
                )
            )

        except Exception as e:

            traceback.print_exc()

            await debug_exception(
                self.bot,
                (
                    "💍 `/forcemarry` "
                    "SETTINGS ERROR"
                ),
                e,
            )

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Could not load "
                        "server settings."
                    ),
                    ephemeral=True,
                )
            )

        if not settings:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Server settings "
                        "have not been configured."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # ADMIN ROLE
        # --------------------------------------------------

        admin_role_id = (
            settings.get(
                "admin_role"
            )
        )

        if not admin_role_id:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ No Admin role "
                        "has been configured.\n"
                        "Run `/setup` first."
                    ),
                    ephemeral=True,
                )
            )

        user_role_ids = [
            role.id
            for role
            in interaction.user.roles
        ]

        if (
            admin_role_id
            not in user_role_ids
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Only members with "
                        "the configured "
                        "**Admin role** can "
                        "use `/forcemarry`."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # VALIDATE USERS
        # --------------------------------------------------

        if (
            user1.id
            == user2.id
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You cannot marry "
                        "someone to themselves."
                    ),
                    ephemeral=True,
                )
            )

        if (
            user1.bot
            or user2.bot
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Bots cannot "
                        "be married."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # EXISTING MARRIAGES
        # --------------------------------------------------

        try:

            if await is_married(
                user1.id
            ):

                return await (
                    interaction.response
                    .send_message(
                        (
                            f"❌ {user1.mention} "
                            f"is already married."
                        ),
                        ephemeral=True,
                    )
                )

            if await is_married(
                user2.id
            ):

                return await (
                    interaction.response
                    .send_message(
                        (
                            f"❌ {user2.mention} "
                            f"is already married."
                        ),
                        ephemeral=True,
                    )
                )

        except Exception as e:

            traceback.print_exc()

            await debug_exception(
                self.bot,
                (
                    "💍 `/forcemarry` "
                    "MARRIAGE CHECK ERROR"
                ),
                e,
            )

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Could not check "
                        "existing marriages."
                    ),
                    ephemeral=True,
                )
            )

        # --------------------------------------------------
        # CREATE MARRIAGE
        #
        # Existing CG/Little/Pet/Handler relationships
        # are NOT removed.
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
                (
                    "💍 `/forcemarry` "
                    "CRASHED"
                ),
                e,
            )

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Failed to create "
                        "the forced marriage."
                    ),
                    ephemeral=True,
                )
            )

        await (
            interaction.response
            .send_message(
                (
                    f"💍 {user1.mention} "
                    f"and {user2.mention} "
                    f"have been married by "
                    f"{interaction.user.mention}!"
                )
            )
        )

    # ==================================================
    # /DIVORCE
    # ==================================================

    @app_commands.command(
        name="divorce",
        description=(
            "Divorce your current spouse."
        ),
    )
    async def divorce(
        self,
        interaction: discord.Interaction,
    ):

        try:

            marriage = (
                await get_marriage(
                    interaction.user.id
                )
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Could not check "
                        "marriage status. "
                        "Try again later."
                    ),
                    ephemeral=True,
                )
            )

        if not marriage:

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You are not "
                        "currently married."
                    ),
                    ephemeral=True,
                )
            )

        user1 = marriage[
            "user1_id"
        ]

        user2 = marriage[
            "user2_id"
        ]

        # --------------------------------------------------
        # IMPORTANT
        #
        # Divorce now removes ONLY "spouse".
        #
        # If the same people are also:
        #
        # Little / CG
        # Pet / Handler
        #
        # those relationships remain.
        # --------------------------------------------------

        try:

            await delete_marriage(
                marriage["id"]
            )

            await remove_relationship(
                user1,
                user2,
                "spouse",
            )

            await remove_relationship(
                user2,
                user1,
                "spouse",
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ Failed to "
                        "process divorce. "
                        "Check bot logs."
                    ),
                    ephemeral=True,
                )
            )

        partner_id = (
            user2
            if user1
            == interaction.user.id
            else user1
        )

        partner = (
            interaction.guild
            .get_member(
                partner_id
            )
        )

        if partner:

            message = (
                f"💔 {interaction.user.mention} "
                f"is now divorced from "
                f"{partner.mention}."
            )

        else:

            message = (
                "💔 Divorce complete."
            )

        await (
            interaction.response
            .send_message(
                message,
                ephemeral=False,
            )
        )

    # ==================================================
    # /TREE
    # ==================================================

    @app_commands.command(
        name="tree",
        description=(
            "Generate your pastel relationship tree."
        ),
    )
    @app_commands.describe(
        user=(
            "Optional member whose tree you want to view"
        ),
    )
    async def tree(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):

        guild = interaction.guild

        # --------------------------------------------------
        # LOAD SETTINGS
        # --------------------------------------------------

        try:

            settings = (
                await self.bot.db
                .get_guild_settings(
                    guild.id
                )
            )

        except Exception:

            traceback.print_exc()

            return await (
                interaction.response
                .send_message(
                    (
                        "⚠️ Could not load "
                        "server settings. "
                        "Ask an admin to run "
                        "`/setup`."
                    ),
                    ephemeral=True,
                )
            )

        if (
            not settings
            or not settings.get(
                "relationship_channel"
            )
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "⚠️ The relationship "
                        "system has not been "
                        "set up yet.\n"
                        "Ask an admin to run "
                        "`/setup` first."
                    ),
                    ephemeral=True,
                )
            )

        relationship_channel_id = (
            settings[
                "relationship_channel"
            ]
        )

        # --------------------------------------------------
        # ENFORCE RELATIONSHIP CHANNEL
        # --------------------------------------------------

        if (
            interaction.channel.id
            != relationship_channel_id
        ):

            return await (
                interaction.response
                .send_message(
                    (
                        "❌ You must use "
                        "this command in "
                        f"<#{relationship_channel_id}>."
                    ),
                    ephemeral=True,
                )
            )

        await debug_log(
            self.bot,
            "🌳 `/tree` command started.",
            "INFO",
        )

        try:

            await (
                interaction.response
                .defer(
                    thinking=True
                )
            )

            target = (
                user
                or interaction.user
            )

            # ==================================================
            # PROFILE NAME HELPER
            # ==================================================

            name_cache = {}

            async def get_tree_name(
                member: discord.Member,
            ):

                if member.id in name_cache:

                    return name_cache[
                        member.id
                    ]

                profile_name = None

                try:

                    profile_name = (
                        await self.bot.db
                        .get_profile_name(
                            guild.id,
                            member.id,
                        )
                    )

                except Exception:

                    profile_name = None

                if profile_name:

                    profile_name = (
                        str(
                            profile_name
                        ).strip()
                    )

                if not profile_name:

                    profile_name = (
                        member.display_name
                    )

                name_cache[
                    member.id
                ] = profile_name

                return profile_name

            # ==================================================
            # MAIN PERSON NAME
            # ==================================================

            target_name = (
                await get_tree_name(
                    target
                )
            )

            # ==================================================
            # LOAD MAIN PERSON RELATIONSHIPS
            # ==================================================

            rows = (
                await get_relationships(
                    target.id
                )
            )

            if not rows:

                return await (
                    interaction
                    .edit_original_response(
                        content=(
                            "❌ You have no "
                            "relationships yet."
                        )
                    )
                )

            # ==================================================
            # FIND SPOUSE FIRST
            # ==================================================

            spouse_id = None

            for row in rows:

                relationship_type = (
                    row[
                        "relationship_type"
                    ]
                )

                if (
                    relationship_type
                    == "spouse"
                ):

                    spouse_id = (
                        row[
                            "partner_id"
                        ]
                    )

                    break

            spouse_member = None
            spouse_name = None

            if spouse_id:

                spouse_member = (
                    guild.get_member(
                        spouse_id
                    )
                )

                if spouse_member:

                    spouse_name = (
                        await get_tree_name(
                            spouse_member
                        )
                    )

            # ==================================================
            # MAIN PERSON'S RELATIONSHIPS
            # ==================================================

            caregivers = []
            littles = []
            middles = []
            siblings = []
            handlers = []
            pets = []

            spouse_extra_roles = []

            # ==================================================
            # BUILD MAIN SIDE
            # ==================================================

            for row in rows:

                partner_id = (
                    row[
                        "partner_id"
                    ]
                )

                relationship_type = (
                    row[
                        "relationship_type"
                    ]
                )

                if (
                    relationship_type
                    == "spouse"
                ):
                    continue

                partner = (
                    guild.get_member(
                        partner_id
                    )
                )

                if not partner:
                    continue

                if (
                    spouse_id
                    and partner_id
                    == spouse_id
                ):

                    if (
                        relationship_type
                        not in spouse_extra_roles
                    ):

                        spouse_extra_roles.append(
                            relationship_type
                        )

                    continue

                partner_name = (
                    await get_tree_name(
                        partner
                    )
                )

                if (
                    relationship_type
                    == "caregiver"
                ):

                    caregivers.append(
                        partner_name
                    )

                elif (
                    relationship_type
                    == "little"
                ):

                    littles.append(
                        partner_name
                    )

                elif (
                    relationship_type
                    == "middle"
                ):

                    middles.append(
                        partner_name
                    )

                elif (
                    relationship_type
                    == "sibling"
                ):

                    siblings.append(
                        partner_name
                    )

                elif (
                    relationship_type
                    == "handler"
                ):

                    handlers.append(
                        partner_name
                    )

                elif (
                    relationship_type
                    == "pet"
                ):

                    pets.append(
                        partner_name
                    )

            # ==================================================
            # SPOUSE'S OWN RELATIONSHIPS
            # ==================================================

            spouse_data = {
                "caregivers": [],
                "littles": [],
                "middles": [],
                "siblings": [],
                "handlers": [],
                "pets": [],
            }

            if spouse_member:

                spouse_rows = (
                    await get_relationships(
                        spouse_member.id
                    )
                )

                for row in spouse_rows:

                    partner_id = (
                        row[
                            "partner_id"
                        ]
                    )

                    relationship_type = (
                        row[
                            "relationship_type"
                        ]
                    )

                    if (
                        relationship_type
                        == "spouse"
                    ):
                        continue

                    if (
                        partner_id
                        == target.id
                    ):
                        continue

                    partner = (
                        guild.get_member(
                            partner_id
                        )
                    )

                    if not partner:
                        continue

                    partner_name = (
                        await get_tree_name(
                            partner
                        )
                    )

                    if (
                        relationship_type
                        == "caregiver"
                    ):

                        spouse_data[
                            "caregivers"
                        ].append(
                            partner_name
                        )

                    elif (
                        relationship_type
                        == "little"
                    ):

                        spouse_data[
                            "littles"
                        ].append(
                            partner_name
                        )

                    elif (
                        relationship_type
                        == "middle"
                    ):

                        spouse_data[
                            "middles"
                        ].append(
                            partner_name
                        )

                    elif (
                        relationship_type
                        == "sibling"
                    ):

                        spouse_data[
                            "siblings"
                        ].append(
                            partner_name
                        )

                    elif (
                        relationship_type
                        == "handler"
                    ):

                        spouse_data[
                            "handlers"
                        ].append(
                            partner_name
                        )

                    elif (
                        relationship_type
                        == "pet"
                    ):

                        spouse_data[
                            "pets"
                        ].append(
                            partner_name
                        )

            # ==================================================
            # GENERATE TREE IMAGE
            # ==================================================

            jpeg_bytes = (
                generate_tree_image(
                    user_name=(
                        target_name
                    ),
                    spouse_name=(
                        spouse_name
                    ),
                    caregivers=(
                        caregivers
                    ),
                    littles=(
                        littles
                    ),
                    middles=(
                        middles
                    ),
                    siblings=(
                        siblings
                    ),
                    handler=(
                        handlers
                    ),
                    pets=(
                        pets
                    ),
                    spouse_data=(
                        spouse_data
                    ),
                    spouse_extra_roles=(
                        spouse_extra_roles
                    ),
                )
            )

            # ==================================================
            # SEND IMAGE
            # ==================================================

            file = discord.File(
                jpeg_bytes,
                filename=(
                    "family_tree.jpg"
                ),
            )

            await (
                interaction
                .edit_original_response(
                    content=(
                        "🌳 Relationship tree "
                        f"for {target.mention}:"
                    ),
                    attachments=[
                        file
                    ],
                )
            )

        except Exception as e:

            await debug_exception(
                self.bot,
                "🌳 `/tree` CRASHED",
                e,
            )

            traceback.print_exc()

            try:

                await (
                    interaction
                    .edit_original_response(
                        content=(
                            "❌ Something went "
                            "wrong while generating "
                            "the relationship tree."
                        )
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
        Relationships(
            bot
        )
    )
