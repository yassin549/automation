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
        "Why we use Optitrade:\n"
        "\n"
        "• 100% deposit bonus\n"
        "• Fast withdrawals\n"
        "• Smooth execution\n"
        "\n"
        f"Get access: {WEBSITE_URL}"
    )


def _vip_cta_message() -> str:
    return (
        "Want earlier entries + full breakdowns?\n"
        "\n"
        "Just reply: VIP\n"
        "(or TRIAL if you want to test it first)"
    )


def build_pre_session_message(audience: str) -> list[str]:
    if audience == AUDIENCE_VIP:
        base = (
            "⏳ Starting in 5 min\n"
            "\n"
            "We’ll drop all VIP setups inside this session window — stay ready."
        )
    else:
        base = (
            "⏳ Session starts in 5 min\n"
            "\n"
            "Signals will only be valid during this time, don’t be late."
        )
    return [base, _trade_promo_message()]


def build_signal_message(
    signal: "SignalLike", audience: str = AUDIENCE_CHANNEL
) -> list[str]:
    details = (
        "New setup\n"
        "\n"
        f"Asset: {signal.asset}\n"
        f"Direction: {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Entry window: {signal.entry_window}"
    )
    return [details, _trade_promo_message()]


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
    status_emoji = "✅" if outcome == "WIN" else "❌"
    result_line = (
        f"{status_emoji} {outcome}\n"
        "\n"
        f"{asset} • {direction}\n"
        "\n"
        "Example result:\n"
        f"Start: ${example.starting_balance}\n"
        f"Net: {profit}\n"
        "\n"
        "We post everything transparently."
    )
    return [result_line, _trade_promo_message()]


def build_vip_push_message() -> list[str]:
    return [
        "2 wins back-to-back\n"
        "\n"
        "VIP got in earlier on both.\n"
        "\n"
        "Free signals come later for a reason.",
        _vip_cta_message(),
        _trade_promo_message(),
    ]


def build_vip_signal_message(signal: "SignalLike") -> list[str]:
    details = (
        "VIP setup\n"
        "\n"
        f"Asset: {signal.asset}\n"
        f"Direction: {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Window: {signal.entry_window}\n"
        "\n"
        f"Entry price: {signal.entry}"
    )
    context = (
        f"Confidence: {signal.confidence}%\n"
        f"Market: {signal.market_condition}\n"
        "\n"
        f"Reason: {signal.insight}\n"
        "\n"
        "Stay sharp — next code coming."
    )
    return [details, context, _trade_promo_message()]


def build_code_message(code: str) -> str:
    return f"Code: {code}"


def build_free_delayed_message(signal: "SignalLike", vip_extra_count: int) -> list[str]:
    note = (
        "This one is delayed\n"
        "\n"
        "VIP already took it earlier."
    )
    if vip_extra_count > 0:
        note = f"{note}\n\n+ they had {vip_extra_count} extra setups this session."
    details = (
        "Setup\n"
        "\n"
        f"Asset: {_short_asset(signal.asset)}\n"
        f"Direction: {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Window: {signal.entry_window}\n"
        "\n"
        f"Confidence: {signal.confidence}%\n"
        f"Market: {signal.market_condition}\n"
        "\n"
        f"Note: {signal.insight}\n"
        "\n"
        "Skip if late."
    )
    return [note, details, _trade_promo_message()]


def build_daily_recap_message(
    stats: RecapStats, example: "ProfitExample", audience: str = AUDIENCE_CHANNEL
) -> list[str]:
    win_rate = _win_rate(stats)
    summary = (
        "Today’s results:\n"
        "\n"
        f"Total: {stats.total}\n"
        f"Wins: {stats.wins}\n"
        f"Losses: {stats.losses}\n"
        f"Win rate: {win_rate}%"
    )
    pnl = (
        "Example:\n"
        "\n"
        f"Start: ${example.starting_balance}\n"
        f"Risk/trade: ${example.risk_per_trade}\n"
        "\n"
        f"Win: +${example.win_profit}\n"
        f"Loss: -${example.loss_cost}\n"
        "\n"
        f"Net: {_signed_money(example.net_profit)}"
    )
    return [summary, pnl, _trade_promo_message()]


def build_weekly_recap_message(
    stats: RecapStats, examples: list["ProfitExample"], audience: str = AUDIENCE_CHANNEL
) -> list[str]:
    win_rate = _win_rate(stats)
    lines = [
        (
            "Weekly recap:\n"
            "\n"
            f"Total: {stats.total}\n"
            f"Wins: {stats.wins}\n"
            f"Losses: {stats.losses}\n"
            f"Win rate: {win_rate}%"
        )
    ]
    for example in examples:
        lines.append(
            "Example:\n"
            "\n"
            f"Start: ${example.starting_balance}\n"
            f"Net: {_signed_money(example.net_profit)}"
        )
    lines.append(_trade_promo_message())
    return lines


def build_session_recap_message(
    session_name: str, stats: RecapStats, audience: str = AUDIENCE_CHANNEL
) -> list[str]:
    win_rate = _win_rate(stats)
    label = "Morning" if session_name == "morning" else "Evening"
    summary = (
        f"{label} session done:\n"
        "\n"
        f"Signals: {stats.total}\n"
        f"Wins: {stats.wins}\n"
        f"Losses: {stats.losses}\n"
        f"Win rate: {win_rate}%"
    )
    return [summary, _trade_promo_message()]


CONVERSION_SOFT = [
    "VIP gives you:\n"
    "\n"
    "• Earlier entries\n"
    "• Full reasoning\n"
    "• Priority help\n"
    "\n"
    'Message "VIP" or "TRIAL" if you want in.',
    _trade_promo_message(),
]

CONVERSION_TRIAL = [
    "Try VIP for 24h\n"
    "\n"
    "Access: $10\n"
    "\n"
    'Reply "TRIAL" to start.',
    _trade_promo_message(),
]

CONVERSION_SCARCITY = [
    "VIP isn’t unlimited\n"
    "\n"
    "Too many people = worse entries.\n"
    "\n"
    'If you want in, message "VIP" or "TRIAL".',
    _trade_promo_message(),
]


CHANNEL_PROMO_LINES = [
    "VIP gets entries first\n+ full explanations",
    "⚡ VIP sees setups earlier\n+ full context",
    "VIP = faster entries\n+ clearer reasoning",
    "VIP gets priority access\n+ complete breakdowns",
]

CHANNEL_PROMO_CTA = [
    'Message "VIP" or "TRIAL"',
    'Want access? Send "VIP"',
    'Type "TRIAL" if you want to test it',
]

VIP_REMINDER_LINES = [
    "⏱️ Quick reminder:\n\nOnly enter inside the window.\nLate = lower accuracy.",
    "Reminder:\n\nMatch direction + expiry exactly.\nDouble check before entering.",
    "⏳ Reminder:\n\nMissed it? Skip.\nThere’s always another setup.",
]


def build_follow_instructions_message(audience: str = AUDIENCE_CHANNEL) -> list[str]:
    steps = (
        "How to follow:\n"
        "\n"
        "1) Create your account on Optitrade\n"
        "2) Deposit at least $50\n"
        "3) Copy expiry + timing exactly"
    )
    note = "⚠️ Signals are optimized for this platform."
    return [steps, note, _trade_promo_message()]


def build_vip_welcome_message() -> list[str]:
    return [
        "You’re in.\n"
        "\n"
        "Here’s what you get:\n"
        "\n"
        "• Earlier entries\n"
        "• Full breakdowns\n"
        "• Priority support\n"
        "\n"
        "Stay active — session starts soon.",
        _trade_promo_message(),
    ]


def build_vip_rules_message() -> list[str]:
    rules = (
        "Keep it simple:\n"
        "\n"
        "1) Only enter inside the window\n"
        "2) Match expiry + direction\n"
        "3) Skip late trades\n"
        "4) Stay consistent with risk"
    )
    return [rules, _trade_promo_message()]


def build_vip_follow_message() -> list[str]:
    steps = (
        "How to execute:\n"
        "\n"
        "1) Use Optitrade\n"
        "2) Match everything exactly\n"
        "3) Paste the code when provided"
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
