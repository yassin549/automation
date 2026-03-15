import os
import time
import random
import logging
import asyncio
from fastapi import FastAPI
from telethon import TelegramClient
from telethon.sessions import StringSession

# -------------------------------
# LOGGING
# -------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ghost")

# -------------------------------
# TELEGRAM CONFIG
# -------------------------------

def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

api_id = int(require_env("API_ID"))
api_hash = require_env("API_HASH")
session_str = require_env("TELEGRAM_SESSION")
channel = require_env("CHANNEL_USERNAME")

client = TelegramClient(StringSession(session_str), api_id, api_hash)
app = FastAPI()
first_deploy_marker = ".first_deploy_sent"
signal_task = None

# -------------------------------
# CODE GENERATOR
# -------------------------------

def generate_compatible_promo(salt=3):
    expiry_timestamp = int(time.time()) + 3600
    hex_time = hex(expiry_timestamp)[2:].zfill(8)

    slots = [0, 5, 10, 15, 20, 25, 30, 35]

    chars = "0123456789abcdef"
    addr = [random.choice(chars) for _ in range(40)]

    for i, slot_index in enumerate(slots):
        addr[slot_index] = hex_time[i]

    time_sum = sum(int(c, 16) for c in hex_time)

    seal_value = (time_sum + salt) % 16
    seal_char = hex(seal_value)[2:]

    addr[39] = seal_char

    return "0x" + "".join(addr)

# -------------------------------
# SEND TELEGRAM SIGNAL
# -------------------------------

async def send_signal():
    code = generate_compatible_promo()

    asset = "EUR/USD"
    side = random.choice(["BUY", "SELL"])
    duration = "5 min"
    message = (
        f"Asset: {asset}\n"
        f"➡️ Direction: {side}\n"
        f"⏱️ Duration: {duration}"
    )
    try:
        await client.send_message(channel, message)
        await client.send_message(channel, code)
        logger.info("Signal sent: %s", code)
    except Exception as exc:
        logger.exception("Error sending signal: %s", exc)

# -------------------------------
# FASTAPI + SCHEDULER
# -------------------------------

@app.on_event("startup")
async def startup_event():
    await client.start()

    # Send a one-time test message on first deployment.
    if not os.path.exists(first_deploy_marker):
        try:
            await client.send_message(channel, "test")
            with open(first_deploy_marker, "w", encoding="utf-8") as handle:
                handle.write("sent\n")
            logger.info("First deploy test message sent.")
        except Exception as exc:
            logger.exception("Error sending first deploy test message: %s", exc)

    # Send immediately, then every 2 hours in a loop.
    async def signal_loop():
        while True:
            await send_signal()
            await asyncio.sleep(2 * 60 * 60)

    global signal_task
    signal_task = asyncio.create_task(signal_loop())
    logger.info("Automation running...")

@app.on_event("shutdown")
async def shutdown_event():
    global signal_task
    if signal_task:
        signal_task.cancel()
        try:
            await signal_task
        except asyncio.CancelledError:
            pass
    await client.disconnect()

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Automation running"}
