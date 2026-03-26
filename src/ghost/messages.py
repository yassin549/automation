from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecapStats:
    total: int
    wins: int
    losses: int


PRE_SESSION_MESSAGE = (
    "🕒 We're live for this session. 👋\n\n"
    "Signals will drop during this window. Keep alerts on. 🔔"
)


def build_signal_message(signal: "SignalLike") -> str:
    return (
        "🚨 New signal\n\n"
        f"Setup: {signal.asset} — {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Entry window: {signal.entry_window}\n\n"
        f"Confidence: {signal.confidence}%\n"
        f"Market: {signal.market_condition}\n"
        f"Insight: {signal.insight}\n\n"
        "If the entry window passes, skip it and wait for the next setup."
    )


def build_result_message(
    signal: "SignalLike", result: str, example: "ProfitExample"
) -> str:
    direction = signal.direction
    asset = _short_asset(signal.asset)
    if result.upper() == "WIN":
        outcome = "Result: WIN ✅"
        tone = "Nice trade if you caught it."
    else:
        outcome = "Result: LOSS ❌"
        tone = "No stress. We reset and wait for the next setup."
    profit = _signed_money(example.net_profit)
    return (
        "📊 Result\n\n"
        f"{asset} — {direction}\n"
        f"{outcome}\n"
        f"{tone}\n\n"
        f"Example P&L (using ${example.starting_balance}):\n"
        f"Net: {profit}"
    )


def build_vip_push_message() -> str:
    return (
        "🔥 Two wins in a row.\n\n"
        "VIP members got the earlier entries.\n"
        "Free signals arrive with a delay.\n\n"
        'Want early alerts? Reply "VIP" or "TRIAL".'
    )


def build_vip_signal_message(signal: "SignalLike") -> str:
    return (
        "👑 VIP signal\n\n"
        f"Setup: {signal.asset} — {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Entry: {signal.entry}\n\n"
        f"Confidence: {signal.confidence}%"
    )


def build_code_message(code: str) -> str:
    return code


def build_free_delayed_message(signal: "SignalLike") -> str:
    return (
        "⏳ Free signal (delayed)\n\n"
        "VIP received this earlier.\n\n"
        f"Setup: {_short_asset(signal.asset)} — {signal.direction}\n"
        f"Expiry: {signal.expiry}\n\n"
        "If the entry window already passed, skip this one."
    )


def build_daily_recap_message(stats: RecapStats, example: "ProfitExample") -> str:
    win_rate = _win_rate(stats)
    return (
        "📅 Daily recap\n\n"
        f"Signals: {stats.total}\n"
        f"Wins: {stats.wins} ✅\n"
        f"Losses: {stats.losses} ❌\n"
        f"Win rate: {win_rate}%\n\n"
        "Example P&L (using the sizing below):\n"
        f"Starting balance: ${example.starting_balance}\n"
        f"Risk per trade: ${example.risk_per_trade}\n\n"
        f"Wins: +${example.win_profit}\n"
        f"Losses: -${example.loss_cost}\n\n"
        f"Net: {_signed_money(example.net_profit)}\n\n"
        "Thanks for trading with us today."
    )


def build_weekly_recap_message(stats: RecapStats, examples: list["ProfitExample"]) -> str:
    win_rate = _win_rate(stats)
    lines = [
        "🗓️ Weekly recap",
        "",
        f"Signals: {stats.total}",
        f"Wins: {stats.wins} ✅",
        f"Losses: {stats.losses} ❌",
        "",
        f"Win rate: {win_rate}%",
        "",
    ]
    for example in examples:
        lines.append(f"Example P&L (starting ${example.starting_balance}):")
        lines.append(f"Net: {_signed_money(example.net_profit)}")
        lines.append("")
    lines.extend(
        [
            "Thanks for a solid week. ✅",
            "",
            'Want earlier entries and full details? Reply "VIP". 👑',
        ]
    )
    return "\n".join(lines)


def build_session_recap_message(session_name: str, stats: RecapStats) -> str:
    win_rate = _win_rate(stats)
    label = "Morning" if session_name == "morning" else "Evening"
    return (
        f"🕒 {label} session recap\n\n"
        f"Signals: {stats.total}\n"
        f"Wins: {stats.wins} ✅\n"
        f"Losses: {stats.losses} ❌\n"
        f"Win rate: {win_rate}%"
    )


CONVERSION_SOFT = (
    "👋 Thinking about VIP?\n\n"
    "VIP members get earlier entries, full details, and priority support.\n\n"
    'If you want access, reply "VIP". 👑'
)

CONVERSION_TRIAL = (
    "🧪 Want to try VIP first?\n\n"
    "Grab a 24h trial for $10 and see the difference.\n\n"
    'Reply "TRIAL" to start.'
)

CONVERSION_SCARCITY = (
    "⚠️ VIP spots are limited.\n\n"
    "We keep the group small so entries stay fast and support stays responsive.\n\n"
    'Reply "VIP" to request a spot.'
)


@dataclass(frozen=True)
class ProfitExample:
    starting_balance: int
    risk_per_trade: int
    win_profit: str
    loss_cost: str
    net_profit: str


class SignalLike:
    asset: str
    direction: str
    expiry: str
    entry_window: str
    entry: str
    confidence: int
    market_condition: str
    insight: str


def _short_asset(asset: str) -> str:
    return asset.replace(" (OTC)", "")


def _signed_money(value: str) -> str:
    if value.startswith("-"):
        return f"-${value[1:]}"
    return f"+${value}"


def _win_rate(stats: RecapStats) -> int:
    if stats.total <= 0:
        return 0
    return round(stats.wins / stats.total * 100)
