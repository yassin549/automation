from __future__ import annotations

from dataclasses import dataclass
import hashlib


Message = str | list[str]


@dataclass(frozen=True)
class RecapStats:
    total: int
    wins: int
    losses: int


AUDIENCE_CHANNEL = "channel"
AUDIENCE_VIP = "vip"

WEBSITE_URL = "https://optitrade.site/?ref=APEX"


def _trade_promo_message() -> str:
    return (
        "Optitrade perks: 100% deposit bonus, instant withdrawals.\n"
        f"More benefits: {WEBSITE_URL}"
    )


def _vip_cta_message() -> str:
    return 'VIP gets early entries and full details.\nReply "VIP" or "TRIAL".'


def build_pre_session_message(audience: str) -> list[str]:
    if audience == AUDIENCE_VIP:
        base = "VIP session starts in 5 minutes.\nFull signals follow in this window."
    else:
        base = "New trading session starts in 5 minutes.\nSignals are valid only in the window."
    return [base, _trade_promo_message()]


def build_signal_message(
    signal: "SignalLike", audience: str = AUDIENCE_CHANNEL
) -> list[str]:
    details = (
        f"Signal: {signal.asset} {signal.direction}\n"
        f"Expiry: {signal.expiry} | Window: {signal.entry_window}"
    )
    context = (
        f"Confidence: {signal.confidence}% | Market: {signal.market_condition}\n"
        f"Insight: {signal.insight} | Skip if late; code next."
    )
    return [details, context, _trade_promo_message()]


def build_result_message(
    signal: "SignalLike",
    result: str,
    example: "ProfitExample",
    audience: str = AUDIENCE_CHANNEL,
) -> list[str]:
    direction = signal.direction
    asset = _short_asset(signal.asset)
    outcome = "WIN" if result.upper() == "WIN" else "LOSS"
    profit = _signed_money(example.net_profit)
    result_line = (
        f"Result: {outcome} | {asset} {direction}\n"
        f"Example P&L (start ${example.starting_balance}): Net {profit}\n"
        "All outcomes are posted."
    )
    return [result_line, _trade_promo_message()]


def build_vip_push_message() -> list[str]:
    return [
        "Win streak: 2 in a row.\nVIP got early entries; free signals are delayed.",
        _vip_cta_message(),
        _trade_promo_message(),
    ]


def build_vip_signal_message(signal: "SignalLike") -> list[str]:
    details = (
        f"VIP signal: {signal.asset} {signal.direction}\n"
        f"Expiry: {signal.expiry} | Window: {signal.entry_window} | Entry: {signal.entry}"
    )
    context = (
        f"Confidence: {signal.confidence}% | Market: {signal.market_condition}\n"
        f"Insight: {signal.insight} | Code next."
    )
    return [details, context, _trade_promo_message()]


def build_code_message(code: str) -> str:
    return code


def build_free_delayed_message(signal: "SignalLike", vip_extra_count: int) -> list[str]:
    note = "Free signal (delayed).\nVIP received this earlier."
    if vip_extra_count > 0:
        note = f"{note}\nVIP had {vip_extra_count} extra signals this session."
    details = (
        f"Signal: {_short_asset(signal.asset)} {signal.direction}\n"
        f"Expiry: {signal.expiry} | Window: {signal.entry_window} | Confidence: {signal.confidence}%\n"
        f"Market: {signal.market_condition} | Insight: {signal.insight} | Skip if late; code next."
    )
    return [note, details, _trade_promo_message()]


def build_daily_recap_message(
    stats: RecapStats, example: "ProfitExample", audience: str = AUDIENCE_CHANNEL
) -> list[str]:
    win_rate = _win_rate(stats)
    summary = (
        "Daily recap\n"
        f"Signals {stats.total} | Wins {stats.wins} | Losses {stats.losses} | "
        f"Win rate {win_rate}%"
    )
    pnl = (
        f"Example P&L (start ${example.starting_balance}, risk ${example.risk_per_trade})\n"
        f"+${example.win_profit} / -${example.loss_cost} / Net {_signed_money(example.net_profit)}"
    )
    return [summary, pnl, _trade_promo_message()]


def build_weekly_recap_message(
    stats: RecapStats, examples: list["ProfitExample"], audience: str = AUDIENCE_CHANNEL
) -> list[str]:
    win_rate = _win_rate(stats)
    lines = [
        (
            "Weekly recap\n"
            f"Signals {stats.total} | Wins {stats.wins} | Losses {stats.losses} | "
            f"Win rate {win_rate}%"
        )
    ]
    for example in examples:
        lines.append(
            f"Example P&L (start ${example.starting_balance})\n"
            f"Net {_signed_money(example.net_profit)}"
        )
    lines.append(_trade_promo_message())
    return lines


def build_session_recap_message(
    session_name: str, stats: RecapStats, audience: str = AUDIENCE_CHANNEL
) -> list[str]:
    win_rate = _win_rate(stats)
    label = "Morning" if session_name == "morning" else "Evening"
    summary = (
        f"{label} session recap\n"
        f"Signals {stats.total} | Wins {stats.wins} | "
        f"Losses {stats.losses} | Win rate {win_rate}%"
    )
    return [summary, _trade_promo_message()]


CONVERSION_SOFT = [
    "VIP gives early entries, full details, priority support.\n"
    'Reply "VIP" or "TRIAL" to join.',
    _trade_promo_message(),
]

CONVERSION_TRIAL = [
    "VIP trial: 24h for $10.\n"
    'Reply "VIP" or "TRIAL" to start.',
    _trade_promo_message(),
]

CONVERSION_SCARCITY = [
    "VIP spots are limited to keep entries fast.\n"
    'Reply "VIP" or "TRIAL" to join.',
    _trade_promo_message(),
]


CHANNEL_PROMO_LINES = [
    "VIP delivers the earliest entries.\nFull context included.",
    "VIP sends entries first.\nFull details included.",
    "VIP: earliest alerts.\nFull breakdown included.",
    "VIP gives priority access.\nAll setups included.",
]

CHANNEL_PROMO_CTA = [
    'Reply "VIP" or "TRIAL" for access.',
    'Message "VIP" or "TRIAL" to join.',
    'Want in? Reply "VIP" or "TRIAL".',
]

VIP_REMINDER_LINES = [
    "Reminder: enter only within the window.\nLate entries reduce accuracy.",
    "Reminder: match expiry and direction exactly.\nDouble-check before entry.",
    "Reminder: skip late entries and wait for the next setup.\nProtect timing.",
]


def build_follow_instructions_message(audience: str = AUDIENCE_CHANNEL) -> list[str]:
    steps = (
        "Follow steps:\n"
        "1) Register on Optitrade\n"
        "2) Deposit $50+\n"
        "3) Match expiry and window"
    )
    note = "Signals are optimized for our platform."
    return [steps, note, _trade_promo_message()]


def build_vip_welcome_message() -> list[str]:
    return [
        "Welcome to VIP. Early entries, full details, priority support.",
        _trade_promo_message(),
    ]


def build_vip_rules_message() -> list[str]:
    rules = (
        "VIP rules:\n"
        "1) Enter only in the window\n"
        "2) Match expiry and direction\n"
        "3) Skip late entries\n"
        "4) Keep risk consistent"
    )
    return [rules, _trade_promo_message()]


def build_vip_follow_message() -> list[str]:
    steps = (
        "Follow VIP:\n"
        "1) Trade on Optitrade\n"
        "2) Match expiry, window, direction\n"
        "3) Paste the code"
    )
    return [steps, _trade_promo_message()]


def build_channel_promo_message(seed: str) -> list[str]:
    intro = _pick_line(CHANNEL_PROMO_LINES, seed)
    cta = _pick_line(CHANNEL_PROMO_CTA, seed + ":cta")
    return [f"{intro}\n{cta}", _trade_promo_message()]


def build_vip_promo_message(seed: str) -> list[str]:
    reminder = _pick_line(VIP_REMINDER_LINES, seed)
    return [reminder, _trade_promo_message()]


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


def _pick_line(lines: list[str], seed: str) -> str:
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(lines)
    return lines[index]


def _win_rate(stats: RecapStats) -> int:
    if stats.total <= 0:
        return 0
    return round(stats.wins / stats.total * 100)
