import time
import random
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# -------------------------------
# TELEGRAM CONFIG
# -------------------------------

api_id = 33880517
api_hash = "b9dde3f0fbc84c2802a92cc10c0655c6"
session_str = "1BJWap1sBu4Z-MnPHehtkxoCFUZvyCNc6dj34cpZfLfxnmQVLxTLsDcN2Z6l631-WjBlpG-3wq4bZ492qTrcZvSMCY64p_KZISz7zwa2DkDpBX5Z85q2wymhdhHQJByyH55l9No3ezZ2rWjDaEfR5o_95fvshakyEFwna_Y36sKwF_r-Rg67i5CD5ginpRYJBAJx6pfvaehzsXUa_Yh7tS5YqKODeq8vup0YSs-L1FzxeC23O4UgUEgjwAWWGSiEvcCTJQ6MyzoI9j0YC6X4RsVjHrI0hq0luEWlcTxl8cvwHsrbe7wF5eQt0ohDktTnCsO3VgvnewHsmvKjP7HtgYvd8SApdT9Y="
channel = "apexbinarysignalsvip"

client = TelegramClient(StringSession(session_str), api_id, api_hash)

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

async def run_scheduler():
    await client.start()
    scheduler = AsyncIOScheduler()

    # Example: send every day at 09:00
    scheduler.add_job(send_signal, "cron", hour=9, minute=0)

    scheduler.start()
    print("Automation running...")

    # Keep the client running
    await client.run_until_disconnected()

# -------------------------------
# START
# -------------------------------

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(run_scheduler())