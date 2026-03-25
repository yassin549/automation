# Ghost Signal Sender

Telegram signal scheduler that enforces the daily structure and rules you specified (pre-session, signals, results, VIP push, recaps) on the Tunisia trading windows.

**Requirements**
- Python 3.11+
- Telethon credentials and an authorized StringSession

**Environment Variables**
Required:
- `API_ID`: Telegram API ID (integer)
- `API_HASH`: Telegram API hash
- `CHANNEL_USERNAME`: Free channel username or ID (for example `@mychannel`)

Authentication (choose one):
- `TELEGRAM_SESSION`: Telethon StringSession for a user account (recommended)
- `TELEGRAM_BOT_TOKEN`: Telegram bot token (bot must be added to channels)

Optional:
- `VIP_CHANNEL_USERNAME`: VIP channel username/ID or an invite link (for example `https://t.me/+T3eNT7Ph6J5kNGJk`). If you use an invite link, the account in `TELEGRAM_SESSION` must have permission to join.

**Schedule (Tunisia time)**
- Morning session: 09:00 – 11:00
- Evening session: 15:30 – 17:30

**Plan File**
Provide a daily plan in JSON (default: `./plan.json`). Each signal includes direction and result; other fields have defaults that match the template.
Each signal also posts a separate codes message containing both the promo code and VIP access code.
If you prefer auto-generated signals, use `--auto-plan --auto-win-rate 0.9` and no plan file is required.

Example `plan.json`:
```json
{
  "date": "2026-03-24",
  "sessions": {
    "morning": [
      {
        "direction": "PUT",
        "result": "WIN",
        "confidence": 85,
        "market_condition": "Rejection Zone",
        "insight": "Liquidity sweep → bearish continuation"
      },
      {"direction": "PUT", "result": "WIN"},
      {"direction": "CALL", "result": "LOSS"}
    ],
    "evening": [
      {"direction": "PUT", "result": "WIN"},
      {"direction": "CALL", "result": "WIN"},
      {"direction": "PUT", "result": "LOSS"},
      {"direction": "PUT", "result": "WIN"},
      {"direction": "CALL", "result": "WIN"}
    ]
  }
}
```

Fields (optional unless marked required):
- `direction` (required): `PUT` or `CALL`
- `result` (required): `WIN` or `LOSS`
- `asset` (default `EUR/USD (OTC)`)
- `expiry` (default `1 Minute`)
- `entry_window` (default `NOW – 10s`)
- `entry` (default `NOW`)
- `confidence` (default `85`)
- `market_condition` (default `Rejection Zone`)
- `insight` (default `Liquidity sweep → bearish continuation`)
- `time` (optional `HH:MM` in Tunisia time; if omitted, signals are randomized inside the session window)

**Run Locally**
Install dependencies:
```bash
python -m pip install -r requirements.txt
```

Run continuously (recommended for strict schedule):
```bash
python -m ghost.cli
```

Run one day and exit:
```bash
python -m ghost.cli --once
```

**Useful Options**
- `--plan PATH`: plan file path (default `./plan.json`)
- `--vip-channel @vipchannel`: send VIP signals first and delayed free signals after
- `--auto-plan`: generate random directions with a win-rate bias
- `--auto-win-rate 0.9`: win rate for auto plan (0–1)
- `--mode day|morning|evening|recap`: run a specific schedule slice (default `day`)
- `--result-delay 75`: seconds before posting result
- `--free-delay 150`: seconds to delay free signals after VIP
- `--daily-recap-time 18:00`: recap time in Tunisia time
- `--weekly-recap-time 19:00`: weekly recap time (Sunday)
- `--conversion-time 13:00`: daily conversion post time

**GitHub Actions**
The workflow in `.github/workflows/telegram.yml` runs short jobs on a UTC schedule using `--mode`:
- Morning session job
- Evening session job
- Recap job (conversion, daily recap, weekly recap if due)

State is persisted between runs via the Actions cache (`.ghost_state.json`).

Note: GitHub cron schedules use UTC. If Tunisia's UTC offset changes, update the cron times.
