from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecapStats:
    total: int
    wins: int
    losses: int


PRE_SESSION_MESSAGE = (
    "🕒 Session is live. 👋\n\n"
    "Signals will be posted during this window."
)


def build_signal_message(signal: "SignalLike") -> str:
    return (
        "🚨 Signal\n\n"
        f"Asset: {signal.asset}\n"
        f"Direction: {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Entry Window: {signal.entry_window}\n\n"
        f"Confidence: {signal.confidence}%\n"
        f"Market Condition: {signal.market_condition}\n\n"
        f"Insight: {signal.insight}"
    )


def build_result_message(
    signal: "SignalLike", result: str, example: "ProfitExample"
) -> str:
    direction = signal.direction
    asset = _short_asset(signal.asset)
    if result.upper() == "WIN":
        outcome = "Result: WIN ✅"
    else:
        outcome = "Result: LOSS ❌"
    profit = _signed_money(example.net_profit)
    return (
        "📊 Result\n\n"
        f"{asset} — {direction}\n\n"
        f"{outcome}\n\n"
        f"If you traded with ${example.starting_balance}:\n"
        f"Estimated Profit: {profit}"
    )


def build_vip_push_message() -> str:
    return (
        "🔥 Two wins in a row.\n\n"
        "VIP entries were earlier.\n"
        "Free signals arrive with a delay.\n\n"
        'VIP access: message "VIP" or "TRIAL". 👑'
    )


def build_vip_signal_message(signal: "SignalLike") -> str:
    return (
        "👑 VIP signal:\n\n"
        f"Asset: {signal.asset}\n"
        f"Direction: {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Entry: {signal.entry}\n\n"
        f"Confidence: {signal.confidence}%"
    )

def build_code_message(code: str) -> str:
    return code


def build_free_delayed_message(signal: "SignalLike") -> str:
    return (
        "⏳ Free signal (delayed):\n\n"
        "VIP entered earlier.\n\n"
        f"Asset: {_short_asset(signal.asset)}\n"
        f"Direction: {signal.direction}\n"
        f"Expiry: {signal.expiry}"
    )


def build_daily_recap_message(stats: RecapStats, example: "ProfitExample") -> str:
    win_rate = _win_rate(stats)
    return (
        "📅 Daily recap:\n\n"
        "Summary:\n\n"
        f"Signals: {stats.total}\n"
        f"Wins: {stats.wins} ✅\n"
        f"Losses: {stats.losses} ❌\n"
        f"Win Rate: {win_rate}%\n\n"
        "💰 Example P&L:\n"
        f"Starting Balance: ${example.starting_balance}\n"
        f"Risk per trade: ${example.risk_per_trade}\n\n"
        f"Wins: +${example.win_profit}\n"
        f"Losses: -${example.loss_cost}\n\n"
        f"Net Profit: +${example.net_profit}"
    )


def build_weekly_recap_message(stats: RecapStats, examples: list["ProfitExample"]) -> str:
    win_rate = _win_rate(stats)
    lines = [
        "🗓️ Weekly recap:",
        "",
        f"Total Signals: {stats.total}",
        f"Wins: {stats.wins} ✅",
        f"Losses: {stats.losses} ❌",
        "",
        f"Win Rate: {win_rate}%",
        "",
    ]
    for example in examples:
        lines.append(f"If you traded with ${example.starting_balance}:")
        lines.append(f"Estimated Profit: +${example.net_profit}")
        lines.append("")
    lines.extend(
        [
            "Weekly summary complete. ✅",
            "",
            "VIP members get the earliest entries each session. 👑",
        ]
    )
    return "\n".join(lines)


def build_session_recap_message(session_name: str, stats: RecapStats) -> str:
    win_rate = _win_rate(stats)
    label = "MORNING" if session_name == "morning" else "EVENING"
    return (
        f"🕒 {label} session recap:\n\n"
        "Summary:\n\n"
        f"Signals: {stats.total}\n"
        f"Wins: {stats.wins} ✅\n"
        f"Losses: {stats.losses} ❌\n"
        f"Win Rate: {win_rate}%"
    )


CONVERSION_SOFT = (
    "👀 Most people watch. Few act.\n\n"
    "VIP members get in earlier and stay consistent.\n\n"
    'VIP access available: "VIP". 👑'
)

CONVERSION_TRIAL = (
    "🤔 Not sure yet?\n\n"
    "Test VIP for 24H (only $10).\n\n"
    "See it for yourself, then decide.\n\n"
    'VIP trial available: "TRIAL" 💬'
)

CONVERSION_SCARCITY = (
    "⚠️ VIP spots are filling up.\n\n"
    "We keep the group small to maintain quality.\n\n"
    "When it’s full, we close access.\n\n"
    "Availability changes quickly."
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
