"""Pillow Palace Arcade — discord.py 2.x, asyncpg-style bot.db, Economy cog.

Install in cogs/palace_minigames.py. No changes to bot.py required.
Private game interactions; persistent public launcher; 15 minute inactivity timeout.
"""
import asyncio
import datetime as dt
import random
import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

LOG = logging.getLogger(__name__)
RNG = random.SystemRandom()
GAMES = {
    'treasure': ('🗝️ Treasure Hunt', 0),
    'coinflip': ('🪙 Coin Flip', 0),
    'claw': ('🧸 Claw Machine', 0),
    'memory': ('🧠 Memory Match', 0),
    'trivia': ('❓ Trivia', 0),
    'higherlower': ('🔢 Higher or Lower', 0),
    'dice': ('🎲 Dice Duel', 0),
}
QUESTIONS = {
    'Animals': [
        ('Which animal is the largest living mammal?', ['Blue whale','Elephant','Giraffe','Orca'],0),
        ('How many legs does an adult spider have?', ['Six','Eight','Ten','Twelve'],1),
        ('Which bird cannot fly?', ['Sparrow','Penguin','Eagle','Falcon'],1),
        ('What do tadpoles grow into?', ['Frogs','Fish','Lizards','Birds'],0),
        ('What is a baby goat called?', ['Calf','Cub','Kid','Foal'],2),
        ('Which mammal lays eggs?', ['Otter','Platypus','Seal','Dolphin'],1),
    ],
    'Gaming': [
        ('Which game features Creepers?', ['Minecraft','Terraria','Roblox','Portal'],0),
        ('Which company makes the PlayStation?', ['Nintendo','Sony','Valve','Sega'],1),
        ('What colour is Sonic the Hedgehog?', ['Red','Green','Blue','Yellow'],2),
        ('Which game features a character named Link?', ['Zelda','Halo','Portal','Tetris'],0),
        ('What shape are classic Tetris pieces made from?', ['Triangles','Squares','Hexagons','Circles'],1),
        ('What is the name of Mario’s brother?', ['Wario','Luigi','Yoshi','Toad'],1),
    ],
    'Movies & TV': [
        ('What is the name of the cowboy in Toy Story?', ['Buzz','Woody','Andy','Rex'],1),
        ('Which film features Elsa?', ['Frozen','Moana','Brave','Tangled'],0),
        ('What colour is Shrek?', ['Blue','Green','Red','Purple'],1),
        ('Which movie has a character named Simba?', ['Bambi','The Lion King','Tarzan','Up'],1),
        ('Which film series features Hogwarts?', ['Star Wars','Harry Potter','Twilight','Shrek'],1),
        ('Who lives in a pineapple under the sea?', ['Patrick','SpongeBob','Squidward','Gary'],1),
    ],
    'General Knowledge': [
        ('How many days are in a leap year?', ['364','365','366','367'],2),
        ('What is the capital of France?', ['Paris','Rome','Berlin','Madrid'],0),
        ('How many sides does a hexagon have?', ['Five','Six','Seven','Eight'],1),
        ('Which ocean is the largest?', ['Atlantic','Indian','Pacific','Arctic'],2),
        ('How many minutes are in an hour?', ['30','45','60','90'],2),
        ('Which continent is Brazil in?', ['Europe','Asia','South America','Africa'],2),
    ],
    'Science': [
        ('What planet is known as the Red Planet?', ['Venus','Mars','Jupiter','Mercury'],1),
        ('What gas do plants absorb?', ['Oxygen','Nitrogen','Carbon dioxide','Helium'],2),
        ('How many planets orbit the Sun?', ['Seven','Eight','Nine','Ten'],1),
        ('What is H2O?', ['Salt','Water','Oxygen','Iron'],1),
        ('What force keeps us on the ground?', ['Gravity','Magnetism','Friction','Heat'],0),
        ('Which organ pumps blood?', ['Brain','Liver','Heart','Lungs'],2),
    ],
}


def coins(n):
    return f'🪙 **{n:,}**'


class ArcadePanel(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        select = discord.ui.Select(custom_id='palace_arcade:select', placeholder='🎮 Choose a game',
            options=[discord.SelectOption(label=name.split(' ', 1)[1], emoji=name.split(' ', 1)[0], value=key)
                     for key, (name, _) in GAMES.items()])
        select.callback = self.choose
        self.add_item(select)

    async def choose(self, interaction):
        key = self.children[0].values[0]
        await self.cog.start_game(interaction, key)


class GameView(discord.ui.View):
    def __init__(self, cog, interaction, key):
        super().__init__(timeout=900)
        self.cog, self.owner, self.guild_id, self.key = cog, interaction.user.id, interaction.guild_id, key
        self.done = False
        self._lock = asyncio.Lock()
        self.message = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner:
            await interaction.response.send_message('This game belongs to someone else.', ephemeral=True)
            return False
        if self.done:
            await interaction.response.send_message('This game has finished.', ephemeral=True)
            return False
        return True

    def close(self):
        self.done = True
        for child in self.children:
            child.disabled = True
        self.stop()
        self.cog.release(self.guild_id, self.owner, self)

    async def on_timeout(self):
        if self.done:
            return
        self.close()
        if self.message:
            try:
                await self.message.edit(content='⌛ Game ended after 15 minutes of inactivity.', view=self)
            except (discord.HTTPException, discord.NotFound):
                pass

    @discord.ui.button(label='Stop Playing', emoji='🛑', style=discord.ButtonStyle.danger, row=4)
    async def stop_playing(self, interaction, button):
        self.close()
        await interaction.response.edit_message(content='🛑 You stopped playing. Choose another game from the arcade panel.', embed=None, view=self)

    async def finish(self, interaction, content):
        self.close()
        await interaction.response.edit_message(content=content, embed=None, view=self)


class Treasure(GameView):
    def __init__(self, cog, interaction):
        super().__init__(cog, interaction, 'treasure')
        for i in range(3):
            b = discord.ui.Button(label=f'Chest {i+1}', emoji='🎁', row=0)
            b.callback = self.pick(i)
            self.add_item(b)

    def pick(self, i):
        async def cb(interaction):
            async with self._lock:
                if self.done:
                    return await interaction.response.send_message('Already opened.', ephemeral=True)
                reward = RNG.choices([0, RNG.randint(20,50), RNG.randint(60,120), 250], weights=[25,45,25,5])[0]
                await interaction.response.defer()
                if reward:
                    await self.cog.credit(self.guild_id, self.owner, reward, 'Arcade treasure')
                self.close()
                await interaction.edit_original_response(content=f'🎁 Chest **{i+1}** contained {coins(reward)} Palace Coins!', view=self)
        return cb


class StakeModal(discord.ui.Modal, title='Place your Palace Coin stake'):
    stake = discord.ui.TextInput(label='Coins to stake (10–250)', placeholder='50', max_length=3)

    def __init__(self, view, choice=None):
        super().__init__()
        self.view, self.choice = view, choice

    async def on_submit(self, interaction):
        try:
            amount = int(str(self.stake.value).strip())
        except ValueError:
            amount = 0
        if not 10 <= amount <= 250:
            return await interaction.response.send_message('Enter a whole number from 10 to 250.', ephemeral=True)
        await self.view.play_stake(interaction, amount, self.choice)


class CoinFlip(GameView):
    def __init__(self, cog, interaction):
        super().__init__(cog, interaction, 'coinflip')

    @discord.ui.button(label='Heads', emoji='🪙', row=0)
    async def heads(self, interaction, button):
        await interaction.response.send_modal(StakeModal(self, 'Heads'))

    @discord.ui.button(label='Tails', emoji='🪙', row=0)
    async def tails(self, interaction, button):
        await interaction.response.send_modal(StakeModal(self, 'Tails'))

    async def play_stake(self, interaction, amount, choice):
        async with self._lock:
            if self.done:
                return await interaction.response.send_message('Game already finished.', ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            if not await self.cog.debit(self.guild_id, self.owner, amount, 'Arcade coin flip stake'):
                return await interaction.followup.send('Not enough Palace Coins.', ephemeral=True)
            outcome = RNG.choice(['Heads','Tails'])
            won = outcome == choice
            try:
                if won:
                    await self.cog.credit(self.guild_id, self.owner, amount*2, 'Arcade coin flip win')
            except Exception:
                await self.cog.credit(self.guild_id, self.owner, amount, 'Arcade coin flip refund')
                self.close()
                return await interaction.followup.send('Reward failed; stake refunded.', ephemeral=True)
            self.close()
            await interaction.followup.send(f'🪙 **{outcome}!** You chose {choice}. ' +
                (f'You won {coins(amount)} profit!' if won else f'You lost {coins(amount)}.'), ephemeral=True)


class Dice(GameView):
    def __init__(self, cog, interaction):
        super().__init__(cog, interaction, 'dice')

    @discord.ui.button(label='Roll Dice', emoji='🎲', row=0)
    async def roll(self, interaction, button):
        await interaction.response.send_modal(StakeModal(self))

    async def play_stake(self, interaction, amount, choice):
        async with self._lock:
            if self.done:
                return await interaction.response.send_message('Game already finished.', ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            if not await self.cog.debit(self.guild_id, self.owner, amount, 'Arcade dice stake'):
                return await interaction.followup.send('Not enough Palace Coins.', ephemeral=True)
            player, bot = RNG.randint(1,6), RNG.randint(1,6)
            payout = amount*2 if player > bot else amount if player == bot else 0
            try:
                if payout:
                    await self.cog.credit(self.guild_id, self.owner, payout, 'Arcade dice payout')
            except Exception:
                await self.cog.credit(self.guild_id, self.owner, amount, 'Arcade dice refund')
                self.close()
                return await interaction.followup.send('Reward failed; stake refunded.', ephemeral=True)
            self.close()
            result = f'Won {coins(amount)} profit!' if player > bot else ('Tie — stake returned.' if player == bot else f'Lost {coins(amount)}.')
            await interaction.followup.send(f'🎲 You rolled **{player}**, bot rolled **{bot}**. {result}', ephemeral=True)


class Claw(GameView):
    def __init__(self, cog, interaction, items):
        super().__init__(cog, interaction, 'claw')
        self.items = {str(r['item_id']): r for r in items}
        options = [discord.SelectOption(label=str(r['name'])[:100], value=str(r['item_id']),
                   description=f"50 coins per attempt • {('Unlimited' if r['stock'] is None else str(r['stock'])+' left')}"[:100]) for r in items[:25]]
        select = discord.ui.Select(placeholder='Choose a plushie to grab', options=options, row=0)
        select.callback = self.choose
        self.add_item(select)

    async def choose(self, interaction):
        async with self._lock:
            if self.done:
                return await interaction.response.send_message('Already played.', ephemeral=True)
            item = self.items[self.children[1].values[0]]  # Stop Playing is first child
            await interaction.response.defer()
            if not await self.cog.debit(self.guild_id, self.owner, 50, 'Arcade claw attempt'):
                return await interaction.followup.send('You need 50 Palace Coins to play.', ephemeral=True)
            # Shop has no rarity column. Chance is fixed until rarity support is added.
            won = RNG.random() < 0.35
            if won:
                try:
                    won = await self.cog.award_shop_item(self.guild_id, self.owner, int(item['item_id']))
                except Exception:
                    LOG.exception('Claw inventory award failed')
                    await self.cog.credit(self.guild_id, self.owner, 50, 'Claw error refund')
                    self.close()
                    return await interaction.edit_original_response(content='Could not award the plushie; your coins were refunded.', view=self)
            self.close()
            await interaction.edit_original_response(content=(f'🧸 You grabbed **{discord.utils.escape_markdown(item["name"])}**! Added to your inventory.'
                if won else '🧸 The claw slipped! No plushie this time.'), view=self)


class Memory(GameView):
    def __init__(self, cog, interaction):
        super().__init__(cog, interaction, 'memory')
        self.cards = list('AABBCCDDEEFFGGHH')
        RNG.shuffle(self.cards)
        self.matched, self.first, self.attempts = set(), None, 0
        for i in range(16):
            b = discord.ui.Button(label='?', style=discord.ButtonStyle.secondary, row=i//4)
            b.callback = self.flip(i)
            self.add_item(b)

    def draw(self):
        for i, b in enumerate(self.children[1:]):
            if i >= 16: break
            b.label = self.cards[i] if i in self.matched or i == self.first else '?'
            b.disabled = i in self.matched
            b.style = discord.ButtonStyle.success if i in self.matched else discord.ButtonStyle.secondary

    def flip(self, i):
        async def cb(interaction):
            async with self._lock:
                if self.done or i in self.matched or i == self.first:
                    return await interaction.response.send_message('Choose another card.', ephemeral=True)
                await interaction.response.defer()
                if self.first is None:
                    self.first = i
                    self.draw()
                    return await interaction.edit_original_response(content='🧠 Find the matching pair!', view=self)
                a = self.first
                self.first = None
                self.attempts += 1
                if self.cards[a] == self.cards[i]:
                    self.matched.update((a,i))
                    if len(self.matched) == 16:
                        reward = 150 if self.attempts <= 12 else 100 if self.attempts <= 18 else 50
                        await self.cog.credit(self.guild_id, self.owner, reward, 'Arcade memory match')
                        self.close()
                        return await interaction.edit_original_response(content=f'🧠 All pairs found in {self.attempts} attempts! Earned {coins(reward)}.', view=self)
                    self.draw()
                    return await interaction.edit_original_response(content=f'✅ Match! {len(self.matched)//2}/8 pairs found.', view=self)
                self.draw()
                await interaction.edit_original_response(content=f'❌ No match: **{self.cards[a]}** and **{self.cards[i]}**. Try again!', view=self)
        return cb


class Trivia(GameView):
    def __init__(self, cog, interaction):
        super().__init__(cog, interaction, 'trivia')
        self.questions, self.index, self.correct = [], 0, 0
        select = discord.ui.Select(placeholder='Choose a trivia category', options=[discord.SelectOption(label=x, value=x) for x in QUESTIONS], row=0)
        select.callback = self.category
        self.add_item(select)

    async def category(self, interaction):
        self.questions = RNG.sample(QUESTIONS[self.children[1].values[0]], 5)
        self.remove_item(self.children[1])
        for i in range(4):
            b = discord.ui.Button(label=str(i+1), row=0)
            b.callback = self.answer(i)
            self.add_item(b)
        await interaction.response.edit_message(content=self.prompt(), view=self)

    def prompt(self):
        question, answers, _ = self.questions[self.index]
        return f'❓ **Question {self.index+1}/5**\n{question}\n\n' + '\n'.join(f'**{i+1}.** {a}' for i,a in enumerate(answers))

    def answer(self, index):
        async def cb(interaction):
            async with self._lock:
                if self.done:
                    return await interaction.response.send_message('Game finished.', ephemeral=True)
                correct = index == self.questions[self.index][2]
                self.correct += int(correct)
                self.index += 1
                if self.index == 5:
                    reward = self.correct*20 + (100 if self.correct == 5 else 0)
                    if reward:
                        await self.cog.credit(self.guild_id, self.owner, reward, 'Arcade trivia')
                    return await self.finish(interaction, f'❓ Finished! {self.correct}/5 correct. Earned {coins(reward)}.')
                await interaction.response.edit_message(content=('✅ Correct!\n\n' if correct else '❌ Incorrect!\n\n')+self.prompt(), view=self)
        return cb


class HigherLower(GameView):
    REWARDS = [0,10,25,50,100,200]
    def __init__(self, cog, interaction):
        super().__init__(cog, interaction, 'higherlower')
        self.number = RNG.randint(1,100)
        self.streak = 0

    @discord.ui.button(label='Higher', emoji='⬆️', row=0)
    async def higher(self, interaction, button):
        await self.guess(interaction, True)

    @discord.ui.button(label='Lower', emoji='⬇️', row=0)
    async def lower(self, interaction, button):
        await self.guess(interaction, False)

    @discord.ui.button(label='Cash Out', emoji='💰', row=1)
    async def cashout(self, interaction, button):
        async with self._lock:
            reward = self.REWARDS[self.streak]
            if reward:
                await interaction.response.defer()
                await self.cog.credit(self.guild_id, self.owner, reward, 'Arcade higher/lower cashout')
                self.close()
                await interaction.edit_original_response(content=f'💰 Cashed out {coins(reward)} after {self.streak} correct guesses!', view=self)
            else:
                await self.finish(interaction, 'You left with no coins. See you next time!')

    async def guess(self, interaction, higher):
        async with self._lock:
            if self.done:
                return await interaction.response.send_message('Game finished.', ephemeral=True)
            old = self.number
            new = RNG.randint(1,100)
            correct = (new > old if higher else new < old)
            if not correct:
                return await self.finish(interaction, f'❌ It was **{new}** (previously {old}). Streak ended; no coins earned.')
            self.streak += 1
            self.number = new
            if self.streak == 5:
                await interaction.response.defer()
                await self.cog.credit(self.guild_id, self.owner, 200, 'Arcade higher/lower 5 streak')
                self.close()
                return await interaction.edit_original_response(content=f'🏆 Five correct guesses! Earned {coins(200)}!', view=self)
            await interaction.response.edit_message(content=f'✅ It was **{new}** (previously {old})!\nStreak: **{self.streak}** • Cash out {coins(self.REWARDS[self.streak])} or guess again.\nCurrent number: **{new}**', view=self)


class PalaceMinigames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = {}
        self.panel_dirty = set()
        self.panel = ArcadePanel(self)
        self._panel_lock = asyncio.Lock()

    async def cog_load(self):
        await self.bot.db.execute('''CREATE TABLE IF NOT EXISTS palace_arcade_settings (
            guild_id BIGINT PRIMARY KEY, channel_id BIGINT, message_id BIGINT)''')
        self.bot.add_view(self.panel)
        self.maintenance.start()

    async def cog_unload(self):
        self.maintenance.cancel()
        self.panel.stop()
        for view in list(self.sessions.values()):
            view.close()

    def economy(self):
        cog = self.bot.get_cog('Economy')
        if cog is None:
            raise RuntimeError('Economy cog not loaded. Install cogs/economy.py first.')
        return cog

    async def credit(self, guild_id, user_id, amount, reason):
        return await self.economy().add_coins(guild_id, user_id, int(amount), reason)

    async def debit(self, guild_id, user_id, amount, reason):
        return await self.economy().remove_coins(guild_id, user_id, int(amount), reason)

    async def award_shop_item(self, guild_id, user_id, item_id):
        # Atomic stock decrement for limited items, no decrement for unlimited stock.
        row = await self.bot.db.fetchrow('''UPDATE economy_items SET stock=CASE WHEN stock IS NULL THEN NULL ELSE stock-1 END
            WHERE guild_id=$1 AND item_id=$2 AND active=TRUE AND category='Plushies'
            AND (stock IS NULL OR stock>0) RETURNING item_id''', guild_id, item_id)
        if row is None:
            return False
        try:
            await self.bot.db.execute('''INSERT INTO economy_inventory(guild_id,user_id,item_id,quantity)
                VALUES($1,$2,$3,1) ON CONFLICT(guild_id,user_id,item_id)
                DO UPDATE SET quantity=economy_inventory.quantity+1''', guild_id, user_id, item_id)
        except Exception:
            await self.bot.db.execute('''UPDATE economy_items SET stock=stock+1 WHERE item_id=$1 AND stock IS NOT NULL''', item_id)
            raise
        return True

    def release(self, guild_id, user_id, view):
        if self.sessions.get((guild_id, user_id)) is view:
            del self.sessions[(guild_id, user_id)]
        if not any(g == guild_id for g, _ in self.sessions):
            self.bot.loop.create_task(self.reposition(guild_id))

    async def start_game(self, interaction, key):
        if interaction.guild_id is None:
            return await interaction.response.send_message('Use this in a server.', ephemeral=True)
        settings = await self.bot.db.fetchrow('SELECT channel_id FROM palace_arcade_settings WHERE guild_id=$1', interaction.guild_id)
        if not settings or interaction.channel_id != settings['channel_id']:
            return await interaction.response.send_message('Use the dedicated arcade channel to play.', ephemeral=True)
        # Switching games is allowed immediately. End the previous private session.
        old_view = self.sessions.get((interaction.guild_id, interaction.user.id))
        if old_view is not None:
            old_view.close()
            if old_view.message is not None:
                try:
                    await old_view.message.edit(content='🔄 You switched games. This session is closed.', embed=None, view=old_view)
                except (discord.HTTPException, discord.NotFound):
                    pass
        economy = self.economy()
        s = await economy.settings(interaction.guild_id)
        if not s['enabled']:
            return await interaction.response.send_message('The economy is disabled.', ephemeral=True)
        try:
            if key == 'treasure': view = Treasure(self, interaction)
            elif key == 'coinflip': view = CoinFlip(self, interaction)
            elif key == 'dice': view = Dice(self, interaction)
            elif key == 'memory': view = Memory(self, interaction)
            elif key == 'trivia': view = Trivia(self, interaction)
            elif key == 'higherlower': view = HigherLower(self, interaction)
            elif key == 'claw':
                items = await self.bot.db.fetch('''SELECT item_id,name,stock FROM economy_items
                    WHERE guild_id=$1 AND active=TRUE AND category='Plushies'
                    AND (stock IS NULL OR stock>0) ORDER BY item_id LIMIT 25''', interaction.guild_id)
                if not items:
                    return await interaction.response.send_message('No plushies are available in the shop yet.', ephemeral=True)
                view = Claw(self, interaction, items)
            else:
                return await interaction.response.send_message('Unknown game.', ephemeral=True)
            self.sessions[(interaction.guild_id, interaction.user.id)] = view
            desc = {
                'treasure':'Choose one of three treasure chests.',
                'coinflip':'Choose heads or tails, then enter a stake of 10–250 coins.',
                'dice':'Roll against the bot with a stake of 10–250 coins.',
                'claw':'Each attempt costs 50 coins. Pick a shop plushie to grab (35% chance).',
                'memory':'Find all eight pairs. Fewer attempts earn more coins.',
                'trivia':'Choose a category and answer five questions.',
                'higherlower':f'Current number: **{view.number}**. Guess higher or lower, or cash out.',
            }[key]
            await interaction.response.send_message(f'**{GAMES[key][0]}**\n{desc}\n\nYou can switch games at any time using the arcade panel. Session expires after 15 minutes of inactivity.', view=view, ephemeral=True)
            try:
                view.message = await interaction.original_response()
            except discord.HTTPException:
                pass
        except Exception:
            if 'view' in locals():
                view.close()
            raise

    @app_commands.command(name='arcadesetup', description='Set up or repair the Pillow Palace Arcade panel')
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def arcadesetup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        previous = await self.bot.db.fetchrow('SELECT channel_id,message_id FROM palace_arcade_settings WHERE guild_id=$1', interaction.guild_id)
        if previous and previous['channel_id'] and previous['message_id']:
            old = interaction.guild.get_channel(previous['channel_id'])
            if old:
                try:
                    msg = await old.fetch_message(previous['message_id'])
                    await msg.delete()
                except (discord.HTTPException, discord.NotFound, discord.Forbidden):
                    pass
        msg = await channel.send(embed=self.panel_embed(), view=self.panel)
        await self.bot.db.execute('''INSERT INTO palace_arcade_settings(guild_id,channel_id,message_id)
            VALUES($1,$2,$3) ON CONFLICT(guild_id) DO UPDATE
            SET channel_id=EXCLUDED.channel_id,message_id=EXCLUDED.message_id''', interaction.guild_id, channel.id, msg.id)
        await interaction.followup.send(f'🎮 Arcade panel installed in {channel.mention}.', ephemeral=True)

    def panel_embed(self):
        embed = discord.Embed(title='🏰 Pillow Palace | Arcade',
            description='Welcome to the Arcade! Select a game below to play **privately** and earn Palace Coins.\n\n'
                        + '\n'.join(f'{name}' for name,_ in GAMES.values())
                        + '\n\n🔄 Switch games anytime using this panel. Games expire after **15 minutes of inactivity**.',
            color=discord.Color.from_rgb(177,135,219))
        embed.set_footer(text='Pillow Palace • Choose a game using the dropdown')
        return embed

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        row = await self.bot.db.fetchrow('SELECT channel_id FROM palace_arcade_settings WHERE guild_id=$1', message.guild.id)
        if row and row['channel_id'] == message.channel.id:
            self.panel_dirty.add(message.guild.id)
            if not any(g == message.guild.id for g,_ in self.sessions):
                await self.reposition(message.guild.id)

    async def reposition(self, guild_id):
        if any(g == guild_id for g,_ in self.sessions):
            return
        async with self._panel_lock:
            if any(g == guild_id for g,_ in self.sessions):
                return
            row = await self.bot.db.fetchrow('SELECT channel_id,message_id FROM palace_arcade_settings WHERE guild_id=$1', guild_id)
            if not row or not row['channel_id']:
                return
            channel = self.bot.get_channel(row['channel_id'])
            if not isinstance(channel, discord.TextChannel):
                return
            try:
                # Avoid unnecessary delete/repost when panel is already last.
                last = [m async for m in channel.history(limit=1)]
                if last and last[0].id == row['message_id']:
                    self.panel_dirty.discard(guild_id)
                    return
                new = await channel.send(embed=self.panel_embed(), view=self.panel)
                await self.bot.db.execute('''UPDATE palace_arcade_settings SET message_id=$2
                    WHERE guild_id=$1''', guild_id, new.id)
                if row['message_id']:
                    try:
                        old = await channel.fetch_message(row['message_id'])
                        await old.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
                self.panel_dirty.discard(guild_id)
            except (discord.Forbidden, discord.HTTPException):
                LOG.exception('Cannot reposition arcade panel in guild %s', guild_id)

    @tasks.loop(minutes=1)
    async def maintenance(self):
        for guild_id in list(self.panel_dirty):
            if not any(g == guild_id for g,_ in self.sessions):
                await self.reposition(guild_id)

    @maintenance.before_loop
    async def before_maintenance(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(PalaceMinigames(bot))
