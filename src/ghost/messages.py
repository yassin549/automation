from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecapStats:
    total: int
    wins: int
    losses: int


PRE_SESSION_MESSAGE = (
    "Trading Session Starting\n\n"
    "We'll be taking high-probability setups only today.\n\n"
    "⚠️ Rules:\n\n"
    "Max 2% risk per trade\n\n"
    "Wait for confirmation\n\n"
    "No overtrading\n\n"
    "Let's stay disciplined and execute"
)


def build_signal_message(signal: "SignalLike") -> str:
    return (
        "SIGNAL ALERT\n\n"
        f"Asset: {signal.asset}\n"
        f"Direction: {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Entry Window: {signal.entry_window}\n\n"
        f"Confidence: {signal.confidence}%\n"
        f"Market Condition: {signal.market_condition}\n\n"
        "⚠️ Risk: 1–2% only\n\n"
        "━━━━━━━━━━━━━━━\n"
        f"Insight: {signal.insight}\n\n"
        "Execute."
    )


def build_result_message(signal: "SignalLike", result: str) -> str:
    direction = signal.direction
    asset = _short_asset(signal.asset)
    if result.upper() == "WIN":
        outcome = "✅ WIN"
        note = "Clean move as expected.\nNext setup soon."
    else:
        outcome = "❌ LOSS"
        note = "Market invalidated setup.\nWe stay disciplined — next trade."
    return f"RESULT\n\n{asset} — {direction}\n\n{outcome}\n\n{note}"


def build_vip_push_message() -> str:
    return (
        "2 CLEAN WINS BACK-TO-BACK\n\n"
        "VIP already secured these early.\n\n"
        "If you're still on free signals, you're getting delayed entries.\n\n"
        "VIP = Faster + Higher Accuracy\n\n"
        'Type "VIP" or "TRIAL" to join.'
    )


def build_vip_signal_message(signal: "SignalLike") -> str:
    return (
        "VIP SIGNAL\n\n"
        f"Asset: {signal.asset}\n"
        f"Direction: {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Entry: {signal.entry}\n\n"
        f"Confidence: {signal.confidence}%\n\n"
        "⚠️ Strict execution — no late entries"
    )


def build_free_delayed_message(signal: "SignalLike") -> str:
    return (
        "FREE SIGNAL (DELAYED)\n\n"
        "VIP already entered this trade earlier\n\n"
        f"Asset: {_short_asset(signal.asset)}\n"
        f"Direction: {signal.direction}\n"
        f"Expiry: {signal.expiry}\n\n"
        "⚠️ Late entry = higher risk"
    )


def build_daily_recap_message(stats: RecapStats, example: "ProfitExample") -> str:
    win_rate = _win_rate(stats)
    return (
        "DAILY RESULTS\n\n"
        f"Total Signals: {stats.total}\n"
        f"Wins: {stats.wins} ✅\n"
        f"Losses: {stats.losses} ❌\n\n"
        f"Win Rate: {win_rate}%\n\n"
        "Example Profit:\n"
        f"Starting Balance: ${example.starting_balance}\n"
        f"Risk per trade: ${example.risk_per_trade}\n\n"
        f"Wins: +${example.win_profit}\n"
        f"Losses: -${example.loss_cost}\n\n"
        f"Net Profit: +${example.net_profit}\n\n"
        "Consistent execution = growth"
    )


def build_weekly_recap_message(stats: RecapStats, examples: list["ProfitExample"]) -> str:
    win_rate = _win_rate(stats)
    lines = [
        "WEEKLY PERFORMANCE",
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
            "This is what consistency looks like.",
            "",
            "VIP members are compounding every week",
        ]
    )
    return "\n".join(lines)


RULES_MESSAGE = (
    "GROUP RULES\n\n"
    "Risk only 1–2% per trade\n\n"
    "Do NOT enter late\n\n"
    "Follow signals exactly\n\n"
    "No overtrading\n\n"
    "Losses are part of the system\n\n"
    "Consistency > Emotion\n\n"
    "Respect the process."
)


CHECKLIST_MESSAGE = (
    "ASSISTANT CHECKLIST (IMPORTANT)\n\n"
    "Every day you MUST:\n\n"
    "Post 1 pre-session message\n"
    "Post 3–5 signals per session\n"
    "Post result for EVERY signal\n"
    "Post at least 1 VIP promotion\n"
    "Post daily recap\n\n"
    "Every week:\n\n"
    "Post weekly recap\n"
    "Post profit examples"
)


CONVERSION_SOFT = (
    "Most people watch.\n"
    "Few execute.\n\n"
    "VIP members act — and get paid.\n\n"
    'Type "VIP" to join.'
)

CONVERSION_TRIAL = (
    "Not sure yet?\n\n"
    "Test VIP for 24H (only $10)\n\n"
    "See results yourself -> then decide.\n\n"
    "DM: TRIAL"
)

CONVERSION_SCARCITY = (
    "⚠️ VIP slots filling fast\n\n"
    "We limit members to maintain quality\n\n"
    "Once full -> access closes\n\n"
    "Don't wait."
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


def _win_rate(stats: RecapStats) -> int:
    if stats.total <= 0:
        return 0
    return round(stats.wins / stats.total * 100)
