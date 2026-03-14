import os
import time
import random
import logging
from fastapi import FastAPI
from telethon import TelegramClient
from telethon.sessions import StringSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
scheduler = AsyncIOScheduler()
app = FastAPI()

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

    message = (
        "TRADE SIGNAL\n\n"
        f"Code: {code}\n"
        "Asset: EUR/USD\n"
        "Direction: CALL\n"
        "Expiry: 5 Minutes"
    )
    try:
        await client.send_message(channel, message)
        logger.info("Signal sent: %s", code)
    except Exception as exc:
        logger.exception("Error sending signal: %s", exc)

# -------------------------------
# FASTAPI + SCHEDULER
# -------------------------------

@app.on_event("startup")
async def startup_event():
    await client.start()

    # Example: send every day at 09:00
    scheduler.add_job(
        send_signal,
        "cron",
        hour=9,
        minute=0,
        id="daily_signal",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Automation running...")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown(wait=False)
    await client.disconnect()

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Automation running"}
