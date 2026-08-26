import discord
from discord.ext import commands
from discord import app_commands

from database.games import (
    get_game_state,
    save_counting,
    save_wordchain,
    save_settings,
)


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_data(
        self,
        guild: discord.Guild,
    ):
        return await get_game_state(
            guild.id
        )

    # ==================================================
    # ADMIN CHECK
    # ==================================================

    async def is_admin(
        self,
        interaction: discord.Interaction,
    ):
        """
        Allow:
        - Discord Administrator permission
        - configured Admin role from /setup
        """

        guild = interaction.guild

        if guild is None:
            return False

        member = interaction.user

        if not isinstance(
            member,
            discord.Member,
        ):
            return False

        # Discord Administrator fallback
        if member.guild_permissions.administrator:
            return True

        try:
            settings = (
                await self.bot.db
                .get_guild_settings(
                    guild.id
                )
            )

        except Exception as e:
            print(
                f"GAMES ADMIN CHECK ERROR: {e}"
            )
            return False

        if not settings:
            return False

        admin_role_id = settings.get(
            "admin_role"
        )

        if not admin_role_id:
            return False

        return any(
            role.id == admin_role_id
            for role in member.roles
        )

    # --------------------------------------------------
    # COUNTING COMMAND
    # --------------------------------------------------

    @app_commands.command(
        name="counting",
        description="Configure the counting game",
    )
    @app_commands.describe(
        setchannel="Select the counting channel",
        toggle="Enable or disable counting",
    )
    async def counting(
        self,
        interaction: discord.Interaction,
        setchannel: discord.TextChannel | None,
        toggle: bool | None,
    ):

        # ==================================================
        # ADMIN ONLY
        # ==================================================

        if not await self.is_admin(
            interaction
        ):
            return await interaction.response.send_message(
                (
                    "❌ Only the configured "
                    "**Admin role** can use "
                    "`/counting`."
                ),
                ephemeral=True,
            )

        try:
            state = await self.get_data(
                interaction.guild
            )

            if setchannel is not None:
                state[
                    "counting_channel"
                ] = setchannel.id

                await save_settings(
                    interaction.guild.id,
                    state[
                        "counting_channel"
                    ],
                    state[
                        "counting_enabled"
                    ],
                    state[
                        "wordchain_channel"
                    ],
                    state[
                        "wordchain_enabled"
                    ],
                )

                await interaction.response.send_message(
                    (
                        "📌 Counting channel "
                        f"set to <#{setchannel.id}>"
                    ),
                    ephemeral=True,
                )

                return

            if toggle is not None:
                state[
                    "counting_enabled"
                ] = toggle

                await save_settings(
                    interaction.guild.id,
                    state[
                        "counting_channel"
                    ],
                    state[
                        "counting_enabled"
                    ],
                    state[
                        "wordchain_channel"
                    ],
                    state[
                        "wordchain_enabled"
                    ],
                )

                await interaction.response.send_message(
                    (
                        "Counting game is now "
                        f"**{'enabled' if toggle else 'disabled'}**."
                    ),
                    ephemeral=True,
                )

                return

            await interaction.response.send_message(
                (
                    "❌ You must specify "
                    "at least one option."
                ),
                ephemeral=True,
            )

        except Exception as e:
            print(
                f"COUNTING ERROR: {e}"
            )
            raise

    # --------------------------------------------------
    # WORDCHAIN COMMAND
    # --------------------------------------------------

    @app_commands.command(
        name="wordchain",
        description="Configure the word-chain game",
    )
    @app_commands.describe(
        setchannel="Select the word-chain channel",
        toggle="Enable or disable word-chain",
    )
    async def wordchain(
        self,
        interaction: discord.Interaction,
        setchannel: discord.TextChannel | None,
        toggle: bool | None,
    ):

        # ==================================================
        # ADMIN ONLY
        # ==================================================

        if not await self.is_admin(
            interaction
        ):
            return await interaction.response.send_message(
                (
                    "❌ Only the configured "
                    "**Admin role** can use "
                    "`/wordchain`."
                ),
                ephemeral=True,
            )

        state = await self.get_data(
            interaction.guild
        )

        if setchannel is not None:
            state[
                "wordchain_channel"
            ] = setchannel.id

            await save_settings(
                interaction.guild.id,
                state[
                    "counting_channel"
                ],
                state[
                    "counting_enabled"
                ],
                state[
                    "wordchain_channel"
                ],
                state[
                    "wordchain_enabled"
                ],
            )

            await interaction.response.send_message(
                (
                    "📌 Word-chain channel "
                    f"set to <#{setchannel.id}>"
                ),
                ephemeral=True,
            )

            return

        if toggle is not None:
            state[
                "wordchain_enabled"
            ] = toggle

            await save_settings(
                interaction.guild.id,
                state[
                    "counting_channel"
                ],
                state[
                    "counting_enabled"
                ],
                state[
                    "wordchain_channel"
                ],
                state[
                    "wordchain_enabled"
                ],
            )

            await interaction.response.send_message(
                (
                    "Word-chain game is now "
                    f"**{'enabled' if toggle else 'disabled'}**."
                ),
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            (
                "❌ You must specify "
                "at least one option."
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # MESSAGE LISTENER
    # --------------------------------------------------

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message,
    ):

        if (
            message.author.bot
            or not message.guild
        ):
            return

        state = await self.get_data(
            message.guild
        )

        # -------------------------
        # COUNTING LOGIC
        # -------------------------

        if (
            state[
                "counting_enabled"
            ]
            and state[
                "counting_channel"
            ]
            and message.channel.id
            == state[
                "counting_channel"
            ]
        ):

            try:
                number = int(
                    message.content.strip()
                )

            except ValueError:

                await message.channel.send(
                    (
                        f"{message.author.mention} "
                        "❌ Not a number! "
                        "Count reset to 0."
                    )
                )

                state[
                    "current_count"
                ] = 0

                state[
                    "last_counter"
                ] = None

                await save_counting(
                    message.guild.id,
                    state[
                        "current_count"
                    ],
                    state[
                        "last_counter"
                    ],
                )

                return

            if (
                message.author.id
                == state[
                    "last_counter"
                ]
            ):

                await message.channel.send(
                    (
                        f"{message.author.mention} "
                        "❌ You cannot count "
                        "twice in a row! "
                        "Reset to 0."
                    )
                )

                state[
                    "current_count"
                ] = 0

                state[
                    "last_counter"
                ] = None

                await save_counting(
                    message.guild.id,
                    state[
                        "current_count"
                    ],
                    state[
                        "last_counter"
                    ],
                )

                return

            if (
                number
                == state[
                    "current_count"
                ] + 1
            ):

                state[
                    "current_count"
                ] += 1

                state[
                    "last_counter"
                ] = message.author.id

                await save_counting(
                    message.guild.id,
                    state[
                        "current_count"
                    ],
                    state[
                        "last_counter"
                    ],
                )

                await message.add_reaction(
                    "✅"
                )

            else:

                await message.channel.send(
                    (
                        f"{message.author.mention} "
                        "❌ Wrong number! "
                        "Expected "
                        f"**{state['current_count'] + 1}**. "
                        "Reset to 0."
                    )
                )

                state[
                    "current_count"
                ] = 0

                state[
                    "last_counter"
                ] = None

                await save_counting(
                    message.guild.id,
                    state[
                        "current_count"
                    ],
                    state[
                        "last_counter"
                    ],
                )

        # -------------------------
        # WORDCHAIN LOGIC
        # -------------------------

        if (
            state[
                "wordchain_enabled"
            ]
            and state[
                "wordchain_channel"
            ]
            and message.channel.id
            == state[
                "wordchain_channel"
            ]
        ):

            words = (
                message.content
                .lower()
                .strip()
                .split()
            )

            if not words:
                return

            word = words[-1]

            if (
                message.author.id
                == state[
                    "word_last_counter"
                ]
            ):

                await message.channel.send(
                    (
                        f"{message.author.mention} "
                        "❌ You cannot play "
                        "twice in a row! "
                        "Chain reset."
                    )
                )

                state[
                    "last_word"
                ] = ""

                state[
                    "used_words"
                ] = []

                state[
                    "word_last_counter"
                ] = None

                await save_wordchain(
                    message.guild.id,
                    state[
                        "last_word"
                    ],
                    state[
                        "used_words"
                    ],
                    state[
                        "word_last_counter"
                    ],
                )

                return

            if (
                word
                in state[
                    "used_words"
                ]
            ):

                await message.channel.send(
                    (
                        f"{message.author.mention} "
                        "❌ That word was "
                        "already used! "
                        "Chain reset."
                    )
                )

                state[
                    "last_word"
                ] = ""

                state[
                    "used_words"
                ] = []

                state[
                    "word_last_counter"
                ] = None

                await save_wordchain(
                    message.guild.id,
                    state[
                        "last_word"
                    ],
                    state[
                        "used_words"
                    ],
                    state[
                        "word_last_counter"
                    ],
                )

                return

            if (
                state[
                    "last_word"
                ] == ""
            ):

                state[
                    "last_word"
                ] = word

                state[
                    "used_words"
                ].append(
                    word
                )

                state[
                    "word_last_counter"
                ] = message.author.id

                await save_wordchain(
                    message.guild.id,
                    state[
                        "last_word"
                    ],
                    state[
                        "used_words"
                    ],
                    state[
                        "word_last_counter"
                    ],
                )

                await message.add_reaction(
                    "🟦"
                )

                return

            if (
                word[0]
                != state[
                    "last_word"
                ][-1]
            ):

                await message.channel.send(
                    (
                        f"{message.author.mention} "
                        "❌ Wrong letter! "
                        "Word must start with "
                        f"**{state['last_word'][-1]}**. "
                        "Chain reset."
                    )
                )

                state[
                    "last_word"
                ] = ""

                state[
                    "used_words"
                ] = []

                state[
                    "word_last_counter"
                ] = None

                await save_wordchain(
                    message.guild.id,
                    state[
                        "last_word"
                    ],
                    state[
                        "used_words"
                    ],
                    state[
                        "word_last_counter"
                    ],
                )

                return

            state[
                "last_word"
            ] = word

            state[
                "used_words"
            ].append(
                word
            )

            state[
                "word_last_counter"
            ] = message.author.id

            await save_wordchain(
                message.guild.id,
                state[
                    "last_word"
                ],
                state[
                    "used_words"
                ],
                state[
                    "word_last_counter"
                ],
            )

            await message.add_reaction(
                "🟩"
            )


async def setup(bot):
    await bot.add_cog(
        Games(bot)
    )
