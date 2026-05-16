import wavelink
import asyncio
import os

from reo.console.logging import logger



running = False
async def on_node(bot):
    global running
    while not bot.is_ready():
        await asyncio.sleep(1)
    if running:
        await wavelink.Pool.reconnect()
        return logger.info("Reconnected to Lavalink nodes")
    running = True

    lavalink_uri = os.getenv("LAVALINK_URI", "http://localhost:2333")
    lavalink_password = os.getenv("LAVALINK_PASSWORD", "iscompxsls")

    nodes = [
        wavelink.Node(uri=lavalink_uri, password=lavalink_password, retries=3)
    ]
    await wavelink.Pool.connect(
        nodes=nodes,
        client=bot
    )
    logger.info(f"Connected to Lavalink with {len(nodes)} nodes")
