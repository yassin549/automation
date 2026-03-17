import os
import time
import random
import logging
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ghost")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def generate_compatible_promo(salt: int = 3) -> str:
    expiry_timestamp = int(time.time()) + 3600
    hex_time = hex(expiry_timestamp)[2:].zfill(8)

    slots = [0, 5, 10, 15, 20, 25, 30, 35]
    chars = "0123456789abcdef"
    addr = [random.choice(chars) for _ in range(40)]

    for i, slot_index in enumerate(slots):
        addr[slot_index] = hex_time[i]

    time_sum = sum(int(c, 16) for c in hex_time)
    seal_value = (time_sum + salt) % 16
    addr[39] = hex(seal_value)[2:]

    return "0x" + "".join(addr)


async def send_signal() -> None:
    api_id = int(require_env("API_ID"))
    api_hash = require_env("API_HASH")
    session_str = require_env("TELEGRAM_SESSION")
    channel = require_env("CHANNEL_USERNAME")

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram client not authorized. Check TELEGRAM_SESSION.")

        code = generate_compatible_promo()

        asset = "EUR/USD"
        side = random.choice(["BUY", "SELL"])
        duration = "5 min"

        message = (
            f"Asset: {asset}\n"
            f"Direction: {side}\n"
            f"Duration: {duration}"
        )

        await client.send_message(channel, message)
        await client.send_message(channel, code)
        logger.info("Signal sent: %s", code)
    finally:
        if client.is_connected():
            await client.disconnect()


if __name__ == "__main__":
    asyncio.run(send_signal())
