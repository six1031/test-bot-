from database.database import db


# --------------------------------------------------
# PANEL FUNCTIONS
# --------------------------------------------------

async def add_panel(guild_id, channel_id, message_id, panel_type):
    await db.add_ticket_panel(
        guild_id,
        channel_id,
        message_id,
        panel_type,
    )


async def get_panels():
    return await db.get_ticket_panels()


async def remove_panel(message_id):
    await db.remove_ticket_panel(message_id)


# --------------------------------------------------
# TICKET FUNCTIONS
# --------------------------------------------------

async def create_ticket(channel_id, owner_id, ticket_type):
    await db.create_ticket(
        channel_id,
        owner_id,
        ticket_type,
    )


async def close_ticket(channel_id):
    await db.close_ticket(channel_id)


async def has_open_ticket(owner_id, ticket_type):
    ticket = await db.get_open_ticket(
        owner_id,
        ticket_type,
    )

    return ticket is not None
