import argparse
import os
import time
import random
import logging
import asyncio
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ghost")
DEFAULT_INTERVAL_HOURS = 8.0


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


FIRST_MESSAGE = (
    "???? Only serious traders

"
    "? Next session starting in 10 minutes

"
    "? If you're not registered, you will miss signals

"
    "?? https://optitrade.site/?ref=APEX"
)

SECOND_MESSAGE = (
    "?? New Trading Session Starting

"
    "? To follow signals correctly:

"
    "1. ?? Register here  https://optitrade.site/?ref=APEX
"
    "2. ?? Deposit minimum $50
"
    "3. ?? Use same expiry & entry

"
    "?? Signals only work properly on our platform"
)


def build_third_message(direction: str) -> str:
    return (
        "?? EUR/USD (OTC)
"
        "?? Expiry: 1 min
"
        f"?? Direction: {direction}

"
        "? Entry: NOW"
    )


def pick_proof_image(proof_dir: Path) -> Path | None:
    if not proof_dir.exists():
        return None

    allowed = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    files = [
        path
        for path in proof_dir.iterdir()
        if path.is_file() and path.suffix.lower() in allowed
    ]
    if not files:
        return None
    return random.choice(files)


async def send_signal(interval_hours: float | None = DEFAULT_INTERVAL_HOURS) -> None:
    api_id = int(require_env("API_ID"))
    api_hash = require_env("API_HASH")
    session_str = require_env("TELEGRAM_SESSION")
    channel = require_env("CHANNEL_USERNAME")

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    proof_dir = Path(__file__).resolve().parent / "proof"
    loop = asyncio.get_running_loop()

    while True:
        cycle_start = loop.time()
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError("Telegram client not authorized. Check TELEGRAM_SESSION.")

            code = generate_compatible_promo()
            direction = random.choice(["CALL ??", "PUT ??"])
            third_message = build_third_message(direction)

            await client.send_message(channel, FIRST_MESSAGE)
            await client.send_message(channel, SECOND_MESSAGE)
            await client.send_message(channel, third_message)
            await client.send_message(channel, code)
            logger.info("Signal sent with direction %s and code %s", direction, code)

            await asyncio.sleep(60)

            await client.send_message(channel, "WIN ✅")
            proof_image = pick_proof_image(proof_dir)
            if proof_image:
                await client.send_file(channel, str(proof_image))
                logger.info("Proof image sent: %s", proof_image.name)
            else:
                logger.warning("No proof images found in %s", proof_dir)
        except Exception:
            logger.exception("Signal cycle failed")
        finally:
            if client.is_connected():
                await client.disconnect()

        if interval_hours is None:
            break

        elapsed = loop.time() - cycle_start
        sleep_for = max(0, interval_hours * 60 * 60 - elapsed)
        logger.info("Next cycle in %.0f seconds", sleep_for)
        await asyncio.sleep(sleep_for)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send Telegram trading signals.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--once", action="store_true", help="Run a single cycle and exit.")
    group.add_argument(
        "--interval-hours",
        type=float,
        help=f"Hours between cycles when running continuously (default: {DEFAULT_INTERVAL_HOURS}).",
    )
    args = parser.parse_args()

    if args.once:
        interval = None
    elif args.interval_hours is not None:
        if args.interval_hours <= 0:
            parser.error("--interval-hours must be greater than 0.")
        interval = args.interval_hours
    else:
        interval = DEFAULT_INTERVAL_HOURS

    asyncio.run(send_signal(interval))
