import discord
import traceback

DEBUG_CHANNEL_ID = 1535749792385212447


async def debug_log(bot, message, level="INFO"):
    channel = bot.get_channel(DEBUG_CHANNEL_ID)

    if channel is None:
        print(f"[{level}] {message}")
        return

    icons = {
        "INFO": "🔵",
        "SUCCESS": "🟢",
        "WARNING": "🟡",
        "ERROR": "🔴",
        "DEBUG": "🔧",
    }

    icon = icons.get(level, "🔵")

    try:
        await channel.send(f"{icon} **{level}** — {message}")
    except Exception as e:
        print(f"Failed to send debug log: {e}")


async def debug_exception(bot, title, error):
    traceback_text = "".join(
        traceback.format_exception(
            type(error),
            error,
            error.__traceback__,
        )
    )

    # Discord message limit
    if len(traceback_text) > 1900:
        traceback_text = traceback_text[-1900:]

    await debug_log(
        bot,
        f"**{title}**\n```py\n{traceback_text}\n```",
        "ERROR",
    )
