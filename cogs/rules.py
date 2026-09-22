import math
import discord
from discord import app_commands
from discord.ext import commands


RULES_PER_PAGE = 25
EMBED_COLOUR = discord.Colour.from_rgb(181, 140, 255)


def rule_embed(rule: dict, number: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"Rule {number} — {rule['title']}",
        description=rule["description"],
        colour=EMBED_COLOUR,
    )
    embed.set_footer(text="Pillow Palace • Server Rules")
    return embed


class RuleModal(discord.ui.Modal):
    def __init__(
        self,
        manager_view,
        *,
        rule: dict | None = None,
    ):
        self.manager_view = manager_view
        self.rule = rule

        super().__init__(
            title="Edit Rule" if rule else "Add Rule"
        )

        self.rule_title = discord.ui.TextInput(
            label="Rule title",
            placeholder="e.g. 18+ Only",
            default=rule["title"] if rule else None,
            max_length=100,
            required=True,
        )

        self.rule_text = discord.ui.TextInput(
            label="Rule text",
            placeholder="Enter the full rule here...",
            default=rule["description"] if rule else None,
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=True,
        )

        self.add_item(self.rule_title)
        self.add_item(self.rule_text)

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        guild_id = interaction.guild_id

        if not guild_id:
            await interaction.response.send_message(
                "This can only be used in a server.",
                ephemeral=True,
            )
            return

        if self.rule:
            await self.manager_view.bot.db.update_rule(
                guild_id,
                int(self.rule["id"]),
                str(self.rule_title.value).strip(),
                str(self.rule_text.value).strip(),
            )
            message = "✅ Rule updated."
        else:
            await self.manager_view.bot.db.add_rule(
                guild_id,
                str(self.rule_title.value).strip(),
                str(self.rule_text.value).strip(),
            )
            message = "✅ Rule added."

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )

        await self.manager_view.refresh_original()


class RuleSelect(discord.ui.Select):
    def __init__(
        self,
        manager_view,
        rules: list[dict],
    ):
        self.manager_view = manager_view

        start = manager_view.page * RULES_PER_PAGE
        page_rules = rules[start:start + RULES_PER_PAGE]

        options = []

        for absolute_index, rule in enumerate(
            page_rules,
            start=start + 1,
        ):
            title = str(rule["title"])
            options.append(
                discord.SelectOption(
                    label=f"{absolute_index}. {title}"[:100],
                    value=str(rule["id"]),
                    description=(
                        str(rule["description"])
                        .replace("\n", " ")[:100]
                    ),
                )
            )

        if not options:
            options = [
                discord.SelectOption(
                    label="No rules added yet",
                    value="none",
                )
            ]

        super().__init__(
            placeholder="Select a rule to manage...",
            min_values=1,
            max_values=1,
            options=options,
            disabled=not bool(page_rules),
            row=0,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        if self.values[0] == "none":
            return

        self.manager_view.selected_rule_id = int(
            self.values[0]
        )

        await interaction.response.edit_message(
            embed=await self.manager_view.build_manager_embed(),
            view=await self.manager_view.rebuild(),
        )


class RulesManagerView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        guild_id: int,
        channel_id: int,
        owner_id: int,
    ):
        super().__init__(timeout=900)

        self.bot = bot
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.owner_id = owner_id

        self.selected_rule_id: int | None = None
        self.page = 0
        self.original_interaction: discord.Interaction | None = None

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ Only the person who opened this Rules Manager can use it.",
                ephemeral=True,
            )
            return False

        return True

    async def rebuild(self):
        self.clear_items()

        rules = await self.bot.db.get_rules(
            self.guild_id
        )

        page_count = max(
            1,
            math.ceil(len(rules) / RULES_PER_PAGE),
        )

        self.page = max(
            0,
            min(self.page, page_count - 1),
        )

        if self.selected_rule_id is not None:
            valid_ids = {
                int(rule["id"])
                for rule in rules
            }
            if self.selected_rule_id not in valid_ids:
                self.selected_rule_id = None

        self.add_item(
            RuleSelect(
                self,
                rules,
            )
        )

        add_button = discord.ui.Button(
            label="Add Rule",
            emoji="➕",
            style=discord.ButtonStyle.success,
            row=1,
        )
        add_button.callback = self.add_rule
        self.add_item(add_button)

        edit_button = discord.ui.Button(
            label="Edit",
            emoji="✏️",
            style=discord.ButtonStyle.primary,
            row=1,
            disabled=self.selected_rule_id is None,
        )
        edit_button.callback = self.edit_rule
        self.add_item(edit_button)

        delete_button = discord.ui.Button(
            label="Delete",
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
            row=1,
            disabled=self.selected_rule_id is None,
        )
        delete_button.callback = self.delete_rule
        self.add_item(delete_button)

        up_button = discord.ui.Button(
            label="Move Up",
            emoji="⬆️",
            style=discord.ButtonStyle.secondary,
            row=2,
            disabled=self.selected_rule_id is None,
        )
        up_button.callback = self.move_up
        self.add_item(up_button)

        down_button = discord.ui.Button(
            label="Move Down",
            emoji="⬇️",
            style=discord.ButtonStyle.secondary,
            row=2,
            disabled=self.selected_rule_id is None,
        )
        down_button.callback = self.move_down
        self.add_item(down_button)

        preview_button = discord.ui.Button(
            label="Preview",
            emoji="👁️",
            style=discord.ButtonStyle.secondary,
            row=2,
            disabled=not bool(rules),
        )
        preview_button.callback = self.preview_rules
        self.add_item(preview_button)

        previous_button = discord.ui.Button(
            label="Previous",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=3,
            disabled=self.page <= 0,
        )
        previous_button.callback = self.previous_page
        self.add_item(previous_button)

        next_button = discord.ui.Button(
            label="Next",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            row=3,
            disabled=self.page >= page_count - 1,
        )
        next_button.callback = self.next_page
        self.add_item(next_button)

        publish_button = discord.ui.Button(
            label="Publish Rules",
            emoji="📢",
            style=discord.ButtonStyle.success,
            row=3,
            disabled=not bool(rules),
        )
        publish_button.callback = self.publish_rules
        self.add_item(publish_button)

        return self

    async def build_manager_embed(self) -> discord.Embed:
        rules = await self.bot.db.get_rules(
            self.guild_id
        )

        channel = self.bot.get_channel(
            self.channel_id
        )

        page_count = max(
            1,
            math.ceil(len(rules) / RULES_PER_PAGE),
        )

        embed = discord.Embed(
            title="📜 Rules Manager",
            description=(
                "Add, edit, delete and reorder the server rules here.\n\n"
                f"**Publish channel:** "
                f"{channel.mention if channel else f'`{self.channel_id}`'}\n"
                f"**Rules:** {len(rules)}\n"
                f"**Page:** {self.page + 1}/{page_count}"
            ),
            colour=EMBED_COLOUR,
        )

        if not rules:
            embed.add_field(
                name="No rules yet",
                value="Press **➕ Add Rule** to create the first rule.",
                inline=False,
            )
            return embed

        selected = None

        if self.selected_rule_id is not None:
            selected = next(
                (
                    rule
                    for rule in rules
                    if int(rule["id"]) == self.selected_rule_id
                ),
                None,
            )

        if selected:
            number = (
                next(
                    index
                    for index, rule in enumerate(rules, start=1)
                    if int(rule["id"]) == self.selected_rule_id
                )
            )

            embed.add_field(
                name=f"Selected: Rule {number}",
                value=f"**{selected['title']}**\n{selected['description'][:900]}",
                inline=False,
            )
        else:
            embed.add_field(
                name="Select a rule",
                value=(
                    "Use the dropdown above to select a rule before "
                    "editing, deleting or moving it."
                ),
                inline=False,
            )

        return embed

    async def refresh_original(self):
        if not self.original_interaction:
            return

        try:
            await self.original_interaction.edit_original_response(
                embed=await self.build_manager_embed(),
                view=await self.rebuild(),
            )
        except discord.HTTPException:
            pass

    async def get_selected_rule(self):
        if self.selected_rule_id is None:
            return None

        return await self.bot.db.get_rule(
            self.guild_id,
            self.selected_rule_id,
        )

    async def add_rule(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.send_modal(
            RuleModal(self)
        )

    async def edit_rule(
        self,
        interaction: discord.Interaction,
    ):
        rule = await self.get_selected_rule()

        if not rule:
            await interaction.response.send_message(
                "❌ Select a rule first.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            RuleModal(
                self,
                rule=rule,
            )
        )

    async def delete_rule(
        self,
        interaction: discord.Interaction,
    ):
        rule = await self.get_selected_rule()

        if not rule:
            await interaction.response.send_message(
                "❌ Select a rule first.",
                ephemeral=True,
            )
            return

        await self.bot.db.delete_rule(
            self.guild_id,
            int(rule["id"]),
        )

        self.selected_rule_id = None

        await interaction.response.edit_message(
            embed=await self.build_manager_embed(),
            view=await self.rebuild(),
        )

    async def move_up(
        self,
        interaction: discord.Interaction,
    ):
        if self.selected_rule_id is None:
            await interaction.response.send_message(
                "❌ Select a rule first.",
                ephemeral=True,
            )
            return

        moved = await self.bot.db.move_rule(
            self.guild_id,
            self.selected_rule_id,
            -1,
        )

        await interaction.response.edit_message(
            embed=await self.build_manager_embed(),
            view=await self.rebuild(),
        )

        if not moved:
            await interaction.followup.send(
                "ℹ️ That rule is already at the top.",
                ephemeral=True,
            )

    async def move_down(
        self,
        interaction: discord.Interaction,
    ):
        if self.selected_rule_id is None:
            await interaction.response.send_message(
                "❌ Select a rule first.",
                ephemeral=True,
            )
            return

        moved = await self.bot.db.move_rule(
            self.guild_id,
            self.selected_rule_id,
            1,
        )

        await interaction.response.edit_message(
            embed=await self.build_manager_embed(),
            view=await self.rebuild(),
        )

        if not moved:
            await interaction.followup.send(
                "ℹ️ That rule is already at the bottom.",
                ephemeral=True,
            )

    async def previous_page(
        self,
        interaction: discord.Interaction,
    ):
        self.page = max(0, self.page - 1)
        self.selected_rule_id = None

        await interaction.response.edit_message(
            embed=await self.build_manager_embed(),
            view=await self.rebuild(),
        )

    async def next_page(
        self,
        interaction: discord.Interaction,
    ):
        self.page += 1
        self.selected_rule_id = None

        await interaction.response.edit_message(
            embed=await self.build_manager_embed(),
            view=await self.rebuild(),
        )

    async def preview_rules(
        self,
        interaction: discord.Interaction,
    ):
        rules = await self.bot.db.get_rules(
            self.guild_id
        )

        if not rules:
            await interaction.response.send_message(
                "❌ There are no rules to preview.",
                ephemeral=True,
            )
            return

        embeds = [
            rule_embed(rule, index)
            for index, rule in enumerate(rules, start=1)
        ]

        await interaction.response.send_message(
            content="👁️ **Rules Preview**",
            embeds=embeds[:10],
            ephemeral=True,
        )

        for start in range(10, len(embeds), 10):
            await interaction.followup.send(
                embeds=embeds[start:start + 10],
                ephemeral=True,
            )

    async def publish_rules(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        rules = await self.bot.db.get_rules(
            self.guild_id
        )

        if not rules:
            await interaction.followup.send(
                "❌ There are no rules to publish.",
                ephemeral=True,
            )
            return

        channel = self.bot.get_channel(
            self.channel_id
        )

        if not isinstance(
            channel,
            (discord.TextChannel, discord.Thread),
        ):
            await interaction.followup.send(
                "❌ I can no longer access the selected channel.",
                ephemeral=True,
            )
            return

        published = await self.bot.db.get_published_rule_messages(
            self.guild_id
        )

        for record in published:
            old_channel = self.bot.get_channel(
                int(record["channel_id"])
            )

            if not old_channel:
                continue

            try:
                old_message = await old_channel.fetch_message(
                    int(record["message_id"])
                )
                await old_message.delete()
            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
            ):
                pass

        await self.bot.db.clear_published_rule_messages(
            self.guild_id
        )

        for index, rule in enumerate(
            rules,
            start=1,
        ):
            message = await channel.send(
                embed=rule_embed(
                    rule,
                    index,
                )
            )

            await self.bot.db.save_published_rule_message(
                self.guild_id,
                int(rule["id"]),
                channel.id,
                message.id,
            )

        await interaction.followup.send(
            f"✅ Published **{len(rules)}** rule panel"
            f"{'s' if len(rules) != 1 else ''} in {channel.mention}.",
            ephemeral=True,
        )


class Rules(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot

    @app_commands.command(
        name="rulespanel",
        description="Open the server rules manager.",
    )
    @app_commands.describe(
        channel="Channel where the rule panels will be published.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(
        manage_guild=True
    )
    async def rulespanel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        member = interaction.user

        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ I could not check your server permissions.",
                ephemeral=True,
            )
            return

        if not (
            member.guild_permissions.manage_guild
            or member.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                "❌ You need **Manage Server** permission to use this command.",
                ephemeral=True,
            )
            return

        permissions = channel.permissions_for(
            interaction.guild.me
        )

        if not (
            permissions.view_channel
            and permissions.send_messages
            and permissions.embed_links
        ):
            await interaction.response.send_message(
                (
                    "❌ I need **View Channel**, **Send Messages**, "
                    "and **Embed Links** permissions in that channel."
                ),
                ephemeral=True,
            )
            return

        view = RulesManagerView(
            self.bot,
            interaction.guild.id,
            channel.id,
            interaction.user.id,
        )

        view.original_interaction = interaction

        await interaction.response.send_message(
            embed=await view.build_manager_embed(),
            view=await view.rebuild(),
            ephemeral=True,
        )


async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        Rules(bot)
    )
