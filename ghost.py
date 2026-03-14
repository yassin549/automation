import time
import random
import asyncio

from telethon import TelegramClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler


# -------------------------------
# TELEGRAM CONFIG
# -------------------------------

api_id = 33880517
api_hash = "b9dde3f0fbc84c2802a92cc10c0655c6"
channel = "apexbinarysignalsvip"

client = TelegramClient("session", api_id, api_hash)


# -------------------------------
# CODE GENERATOR (your script)
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

    message = f"""
📈 TRADE SIGNAL

Code: {code}
Asset: EUR/USD
Direction: CALL
Expiry: 5 Minutes
"""

    await client.send_message(channel, message)

    print("Signal sent:", code)


# -------------------------------
# SCHEDULER
# -------------------------------

async def main():

    scheduler = AsyncIOScheduler()

    # example: send every day at 09:00
    scheduler.add_job(send_signal, "cron", hour=9, minute=0)

    scheduler.start()

    print("Automation running...")

    await client.run_until_disconnected()


with client:
    client.loop.run_until_complete(main())