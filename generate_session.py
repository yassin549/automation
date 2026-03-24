from __future__ import annotations

import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    print("This will generate a Telethon StringSession.")
    print("You will be prompted for your phone number and login code.")
    api_id = int(input("API_ID: ").strip())
    api_hash = input("API_HASH: ").strip()

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        session = client.session.save()

    print("\nYour TELEGRAM_SESSION string is:\n")
    print(session)
    print("\nSave it in your secrets as TELEGRAM_SESSION.")


if __name__ == "__main__":
    asyncio.run(main())
