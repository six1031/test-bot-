"""Pillow Palace member help centre (discord.py 2.x, PostgreSQL).

Install in cogs/palace_help.py. Uses bot.db.execute/fetch/fetchrow.
/help dynamically discovers slash commands on every open/refresh.
/helpadmin hide, show, hidden: administrators control additional exclusions.

Discord.py cannot safely evaluate arbitrary custom app_commands.check callbacks
outside a real command invocation. Explicit exclusions and conservative staff-name
filtering therefore supplement default_permissions metadata.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

PAGE_SIZE = 5
COLOR = 0xAD8BE6
# Names in this set are hidden by default. /helpadmin show can override these,
# but commands requiring elevated Discord permissions still remain hidden.
STAFF_ROOTS = {
    'setup', 'settings', 'moderation', 'mod', 'admin', 'staff', 'ban', 'unban',
    'kick', 'mute', 'unmute', 'timeout', 'untimeout', 'purge', 'clear', 'warn',
    'warnings', 'lock', 'unlock', 'slowmode', 'verification', 'verifysetup',
    'economy', 'coins', 'shopsetup', 'birthdaysetup', 'birthdaygif',
    'birthdaytest', 'xpsetup', 'xpgif', 'xptest', 'xpimporthistory',
    'afksetup', 'afkreset', 'confessionsetup', 'confessiontoggle',
    'confessionstatus', 'ticketsetup', 'ticketssetup', 'autothreadsetup',
    'rulesetup', 'banpanel', 'applicationsetup',
}
STAFF_COMMANDS = {
    'timezone setmember', 'xp add', 'xp remove', 'xp reset', 'xp sync',
}
ELEVATED = {
    'administrator', 'manage_guild', 'manage_channels', 'manage_roles',
    'manage_messages', 'manage_webhooks', 'manage_threads', 'kick_members',
    'ban_members', 'moderate_members', 'manage_nicknames', 'view_audit_log',
    'manage_events', 'manage_emojis_and_stickers', 'manage_expressions',
}
CATEGORY_RULES = [
    ('👤 Profiles', ('profile', 'bio', 'aboutme', 'pronouns', 'avatar', 'userinfo')),
    ('💞 Looking For', ('looking', 'lf', 'find', 'match', 'partner', 'caregiver', 'little', 'handler')),
    ('🪙 Economy & Shop', ('balance', 'daily', 'weekly', 'pay', 'richest', 'coinhistory', 'shop', 'shopitem', 'buy', 'inventory', 'gift', 'coins')),
    ('🎮 Minigames', ('treasure', 'fish', 'claw', 'memory', 'trivia', 'game', 'dice', 'roll', 'rps', 'coinflip', 'slots')),
    ('⭐ Levels & XP', ('rank', 'leaderboard', 'level', 'xp')),
    ('🎂 Birthdays', ('birthday',)),
    ('🌍 Timezones', ('timezone', 'time', 'timecompare')),
    ('💤 AFK & Activity', ('afk', 'back', 'afkstatus', 'activity')),
    ('💌 Confessions', ('confess',)),
    ('🎟️ Tickets & Support', ('ticket', 'report', 'support', 'contact', 'appeal')),
    ('🎭 Community & Fun', ('qotd', 'count', 'wordchain', 'suggest', 'poll', 'event', 'intro', 'selfrole', 'roles', 'hug', 'pat', 'boop')),
]


def category_for(command):
    root = command.qualified_name.lower().split()[0]
    cog = getattr(getattr(command, 'binding', None), '__class__', type(None)).__name__.lower()
    for label, prefixes in CATEGORY_RULES:
        if any(root == p or root.startswith(p + '_') for p in prefixes):
            return label
    for label, prefixes in CATEGORY_RULES:
        if any(p in cog for p in prefixes):
            return label
    return '📚 Other Commands'


def flatten(items):
    for item in items:
        if isinstance(item, app_commands.Group):
            yield from flatten(item.commands)
        elif isinstance(item, app_commands.Command):
            yield item


def normalized(value):
    return ' '.join(value.strip().lower().lstrip('/').split())


def permission_allowed(command, member, channel):
    node = command
    while node:
        perms = getattr(node, 'default_permissions', None)
        if perms is not None:
            if getattr(perms, 'value', None) == 0:
                return False
            for name, enabled in perms:
                if enabled and not getattr(member.guild_permissions, name, False):
                    return False
        node = getattr(node, 'parent', None)
    # Channel-specific permissions are relevant for commands requiring them.
    return True


def is_staff_name(name):
    name = normalized(name)
    root = name.split()[0] if name else ''
    return root in STAFF_ROOTS or name in STAFF_COMMANDS


def command_visible(command, member, channel, rules):
    name = normalized(command.qualified_name)
    if name in ('help',) or name.startswith('helpadmin '):
        return False
    if not permission_allowed(command, member, channel):
        return False
    if getattr(command, 'guild_only', False) and member.guild is None:
        return False
    # Parent/group exclusion applies to all subcommands.
    parts = name.split()
    prefixes = [' '.join(parts[:i]) for i in range(1, len(parts) + 1)]
    for prefix in prefixes:
        if rules.get(prefix) is False:
            return False
    if rules.get(name) is True:
        return True
    if any(rules.get(p) is True for p in prefixes):
        return True
    return not is_staff_name(name)


def all_commands(bot, guild):
    guild_commands = bot.tree.get_commands(guild=guild)
    global_commands = bot.tree.get_commands()
    roots = {c.name: c for c in global_commands}
    roots.update({c.name: c for c in guild_commands})
    return sorted(flatten(roots.values()), key=lambda c: c.qualified_name.lower())


def usage(command):
    args = []
    for param in getattr(command, 'parameters', []):
        name = param.display_name
        args.append(f'<{name}>' if param.required else f'[{name}]')
    return '/' + command.qualified_name + (' ' + ' '.join(args) if args else '')


class SearchModal(discord.ui.Modal, title='Search Pillow Palace commands'):
    term = discord.ui.TextInput(label='Command name or description', placeholder='e.g. profile, shop, ticket', max_length=100)

    def __init__(self, view):
        super().__init__()
        self.parent_view = view

    async def on_submit(self, interaction):
        view = self.parent_view
        view.query = str(self.term.value).strip().lower()
        view.category = '🔎 Search Results'
        view.page = 0
        view.update_controls()
        await interaction.response.edit_message(embed=view.embed(), view=view)


class CategorySelect(discord.ui.Select):
    def __init__(self, view):
        self.help_view = view
        super().__init__(placeholder='Select a category…', min_values=1, max_values=1, row=0, options=[discord.SelectOption(label='Overview', value='🏠 Overview')])

    async def callback(self, interaction):
        view = self.help_view
        view.category = self.values[0]
        view.page = 0
        view.update_controls()
        await interaction.response.edit_message(embed=view.embed(), view=view)


class HelpView(discord.ui.View):
    def __init__(self, cog, member, channel, groups):
        super().__init__(timeout=300)
        self.cog, self.member, self.channel = cog, member, channel
        self.groups = groups
        self.category = '🏠 Overview'
        self.query = ''
        self.page = 0
        self.selector = CategorySelect(self)
        self.add_item(self.selector)
        self.update_controls()

    async def interaction_check(self, interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message('Use `/help` to open your own menu.', ephemeral=True)
            return False
        return True

    def items(self):
        if self.category == '🔎 Search Results':
            return [c for commands_list in self.groups.values() for c in commands_list
                    if self.query in c.qualified_name.lower() or self.query in (c.description or '').lower()]
        return self.groups.get(self.category, [])

    def update_controls(self):
        categories = list(self.groups)
        # Discord select menus allow 25 options, including Overview and Search.
        options = [discord.SelectOption(label='Overview', value='🏠 Overview', emoji='🏠')]
        options += [discord.SelectOption(label=c[:100], value=c) for c in categories[:23]]
        if self.category == '🔎 Search Results':
            options.append(discord.SelectOption(label='Search Results', value='🔎 Search Results', emoji='🔎'))
        self.selector.options = options[:25]
        self.selector.disabled = len(options) <= 1
        count = len(self.items())
        self.previous.disabled = self.category == '🏠 Overview' or self.page == 0
        self.next.disabled = self.category == '🏠 Overview' or (self.page + 1) * PAGE_SIZE >= count

    def embed(self):
        embed = discord.Embed(color=COLOR)
        if self.category == '🏠 Overview':
            embed.title = '🏰 Pillow Palace | Help Centre'
            embed.description = ('Explore the commands available to members. Choose a category, '
                                 'or use **Search** to find a command.\n\n'
                                 'The list updates automatically when new commands are loaded.')
            for cat, items in self.groups.items():
                embed.add_field(name=cat, value=f'{len(items)} commands', inline=True)
            if not self.groups:
                embed.description += '\n\nNo member commands are currently available.'
            embed.set_footer(text='Only commands visible under the help access rules are shown')
        else:
            items = self.items()
            pages = max(1, math.ceil(len(items) / PAGE_SIZE))
            embed.title = f'🏰 Pillow Palace | {self.category}'
            if not items:
                embed.description = 'No matching commands found.'
            for command in items[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]:
                embed.add_field(name=f'`{usage(command)[:240]}`',
                                value=(command.description or 'No description available.')[:950], inline=False)
            embed.set_footer(text=f'Page {self.page + 1}/{pages} • {len(items)} commands')
        return embed

    @discord.ui.button(label='Previous', emoji='◀️', style=discord.ButtonStyle.secondary, row=1)
    async def previous(self, interaction, button):
        self.page = max(0, self.page - 1)
        self.update_controls()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label='Next', emoji='▶️', style=discord.ButtonStyle.secondary, row=1)
    async def next(self, interaction, button):
        self.page += 1
        self.update_controls()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label='Search', emoji='🔎', style=discord.ButtonStyle.primary, row=1)
    async def search(self, interaction, button):
        await interaction.response.send_modal(SearchModal(self))

    @discord.ui.button(label='Refresh', emoji='🔄', style=discord.ButtonStyle.secondary, row=1)
    async def refresh(self, interaction, button):
        self.groups = await self.cog.build_groups(interaction.guild, interaction.user, interaction.channel)
        if self.category not in self.groups and self.category != '🔎 Search Results':
            self.category = '🏠 Overview'
        self.page = 0
        self.update_controls()
        await interaction.response.edit_message(embed=self.embed(), view=self)


class PalaceHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.bot.db.execute('''CREATE TABLE IF NOT EXISTS palace_help_visibility (
            guild_id BIGINT NOT NULL,
            command_name TEXT NOT NULL,
            visible BOOLEAN NOT NULL,
            PRIMARY KEY (guild_id, command_name)
        )''')

    async def rules_for(self, guild_id):
        rows = await self.bot.db.fetch('SELECT command_name, visible FROM palace_help_visibility WHERE guild_id=$1', guild_id)
        return {row['command_name']: row['visible'] for row in rows}

    async def build_groups(self, guild, member, channel):
        rules = await self.rules_for(guild.id)
        groups = defaultdict(list)
        for cmd in all_commands(self.bot, guild):
            if command_visible(cmd, member, channel, rules):
                groups[category_for(cmd)].append(cmd)
        return dict(sorted(groups.items()))

    @app_commands.command(name='help', description='Browse all available Pillow Palace member commands.')
    @app_commands.guild_only()
    async def help_command(self, interaction: discord.Interaction):
        groups = await self.build_groups(interaction.guild, interaction.user, interaction.channel)
        view = HelpView(self, interaction.user, interaction.channel, groups)
        await interaction.response.send_message(embed=view.embed(), view=view, ephemeral=True)

    helpadmin = app_commands.Group(name='helpadmin', description='Manage which commands appear in the member help menu.', guild_only=True)

    @helpadmin.command(name='hide', description='Hide a command or whole command group from member help.')
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(command='Full command name, e.g. profile edit or ticket')
    async def hide(self, interaction: discord.Interaction, command: str):
        await self.change_visibility(interaction, command, False)

    @helpadmin.command(name='show', description='Show a command in help, overriding the default staff-name filter.')
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(command='Full command name, e.g. profile edit')
    async def show(self, interaction: discord.Interaction, command: str):
        await self.change_visibility(interaction, command, True)

    async def change_visibility(self, interaction, command, visible):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('Administrators only.', ephemeral=True)
            return
        name = normalized(command)
        known = {normalized(c.qualified_name) for c in all_commands(self.bot, interaction.guild)}
        known |= { ' '.join(n.split()[:i]) for n in list(known) for i in range(1, len(n.split())) }
        if name not in known:
            await interaction.response.send_message(f'Unknown command: `/{name}`. Use its full slash-command name.', ephemeral=True)
            return
        if name in {'help', 'helpadmin'} or name.startswith('helpadmin '):
            await interaction.response.send_message('Help administration commands cannot be made public in help.', ephemeral=True)
            return
        await self.bot.db.execute('''INSERT INTO palace_help_visibility(guild_id, command_name, visible)
            VALUES($1,$2,$3) ON CONFLICT(guild_id,command_name)
            DO UPDATE SET visible=EXCLUDED.visible''', interaction.guild.id, name, visible)
        await interaction.response.send_message(
            f'`/{name}` is now {"allowed in" if visible else "hidden from"} the member help menu. '
            + ('Discord permission restrictions still apply.' if visible else 'Subcommands are hidden too.'), ephemeral=True)

    @helpadmin.command(name='reset', description='Remove a custom help visibility rule.')
    @app_commands.default_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction, command: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('Administrators only.', ephemeral=True)
            return
        name = normalized(command)
        await self.bot.db.execute('DELETE FROM palace_help_visibility WHERE guild_id=$1 AND command_name=$2', interaction.guild.id, name)
        await interaction.response.send_message(f'`/{name}` now uses its default help visibility.', ephemeral=True)

    @helpadmin.command(name='hidden', description='List custom visibility settings and default staff exclusions.')
    @app_commands.default_permissions(administrator=True)
    async def hidden(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('Administrators only.', ephemeral=True)
            return
        rules = await self.rules_for(interaction.guild.id)
        overrides = [f'`/{name}` — {"shown" if show else "hidden"}' for name, show in sorted(rules.items())]
        content = '\n'.join(overrides)[:1700] if overrides else 'No custom visibility rules.'
        await interaction.response.send_message(
            '**Custom help visibility rules**\n' + content + '\n\nStaff commands are also hidden by default, and Discord permission requirements are respected.',
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(PalaceHelp(bot))
