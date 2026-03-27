from __future__ import annotations

from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class RecapStats:
    total: int
    wins: int
    losses: int


AUDIENCE_CHANNEL = "channel"
AUDIENCE_VIP = "vip"

WEBSITE_URL = "https://optitrade.site/?ref=APEX"


def _promo_block(audience: str) -> str:
    if audience == AUDIENCE_VIP:
        return f"🌐 Trade here to match the entries:\n{WEBSITE_URL}"
    return (
        '👑 Want earlier entries and full details? Reply "VIP" or "TRIAL".\n'
        f"🌐 Trade here: {WEBSITE_URL}"
    )


def build_pre_session_message(audience: str) -> str:
    if audience == AUDIENCE_VIP:
        return (
            "👑 VIP session is live.\n\n"
            "Full signals start now. Stay sharp. ⚡\n\n"
            "Why: entries are time-sensitive, so alerts matter.\n\n"
            f"{_promo_block(audience)}"
        )
    return (
        "🕒 Session is live.\n\n"
        "Sample signals will appear during this window.\n"
        "VIP gets early entries. 🔔\n\n"
        "Why: signals are only valid inside this session window.\n\n"
        f"{_promo_block(audience)}"
    )


def build_signal_message(signal: "SignalLike", audience: str = AUDIENCE_CHANNEL) -> str:
    return (
        "🚨 New signal\n\n"
        f"Setup: {signal.asset} — {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Entry window: {signal.entry_window}\n\n"
        f"Confidence: {signal.confidence}%\n"
        f"Market: {signal.market_condition}\n"
        f"Insight: {signal.insight}\n\n"
        "If the entry window passes, skip it and wait for the next setup.\n\n"
        "Copy the code below and paste it inside the website.\n\n"
        "Why: this setup is only valid inside the entry window.\n\n"
        f"{_promo_block(audience)}"
    )


def build_result_message(
    signal: "SignalLike",
    result: str,
    example: "ProfitExample",
    audience: str = AUDIENCE_CHANNEL,
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
    seed = f"{signal.asset}-{signal.direction}-{result}"
    intro = _pick_line(INTRO_LINES, seed)
    motivation = _pick_line(MOTIVATION_LINES, seed + ":motivation")
    promo = ""
    if audience != AUDIENCE_VIP:
        promo = _pick_line(PROMO_LINES, seed + ":promo")
    lines = [
        "📊 Result",
        "",
        f"{asset} — {direction}",
        f"{outcome}",
        f"{tone}",
        "",
        f"Example P&L (using ${example.starting_balance}):",
        f"Net: {profit}",
        "",
        f"{intro}",
        f"{motivation}",
    ]
    if promo:
        lines.append(promo)
    lines.extend(
        [
            "",
            "Why: we publish every outcome for transparency.",
            "",
            _promo_block(audience),
        ]
    )
    return "\n".join(lines)


def build_vip_push_message() -> str:
    return (
        "🔥 Two wins in a row.\n\n"
        "VIP members got the earlier entries.\n"
        "Free signals arrive with a delay.\n\n"
        "Why: speed matters on these entries.\n\n"
        f"{_promo_block(AUDIENCE_CHANNEL)}"
    )


def build_vip_signal_message(signal: "SignalLike") -> str:
    return (
        "👑 VIP signal\n\n"
        f"Setup: {signal.asset} — {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Entry window: {signal.entry_window}\n"
        f"Entry: {signal.entry}\n\n"
        f"Confidence: {signal.confidence}%\n"
        f"Market: {signal.market_condition}\n"
        f"Insight: {signal.insight}\n\n"
        "Copy the code below and paste it inside the website.\n\n"
        "Why: VIP gets full details and fastest entries.\n\n"
        f"{_promo_block(AUDIENCE_VIP)}"
    )


def build_code_message(code: str) -> str:
    return code


def build_free_delayed_message(signal: "SignalLike", vip_extra_count: int) -> str:
    extra_line = ""
    if vip_extra_count > 0:
        extra_line = f"VIP got {vip_extra_count} additional signals this session.\n\n"
    return (
        "⏳ Free signal (delayed)\n\n"
        "VIP received this earlier.\n\n"
        f"{extra_line}"
        f"Setup: {_short_asset(signal.asset)} — {signal.direction}\n"
        f"Expiry: {signal.expiry}\n"
        f"Entry window: {signal.entry_window}\n"
        f"Confidence: {signal.confidence}%\n"
        f"Market: {signal.market_condition}\n"
        f"Insight: {signal.insight}\n\n"
        "Copy the code below and paste it inside the website.\n\n"
        "If the entry window already passed, skip this one.\n\n"
        "Why: free signals are delayed to protect VIP speed.\n\n"
        f"{_promo_block(AUDIENCE_CHANNEL)}"
    )


def build_daily_recap_message(
    stats: RecapStats, example: "ProfitExample", audience: str = AUDIENCE_CHANNEL
) -> str:
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
        "Thanks for trading with us today. 🙏\n\n"
        "Why: recaps keep results clear and consistent.\n\n"
        f"{_promo_block(audience)}"
    )


def build_weekly_recap_message(
    stats: RecapStats, examples: list["ProfitExample"], audience: str = AUDIENCE_CHANNEL
) -> str:
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
            "Why: weekly recaps show the bigger picture.",
            "",
            _promo_block(audience),
        ]
    )
    return "\n".join(lines)


def build_session_recap_message(
    session_name: str, stats: RecapStats, audience: str = AUDIENCE_CHANNEL
) -> str:
    win_rate = _win_rate(stats)
    label = "Morning" if session_name == "morning" else "Evening"
    return (
        f"🕒 {label} session recap\n\n"
        f"Signals: {stats.total}\n"
        f"Wins: {stats.wins} ✅\n"
        f"Losses: {stats.losses} ❌\n"
        f"Win rate: {win_rate}%\n\n"
        "Why: session recaps help you stay disciplined.\n\n"
        f"{_promo_block(audience)}"
    )


CONVERSION_SOFT = (
    "👋 Thinking about VIP?\n\n"
    "VIP members get earlier entries, full details, and priority support.\n\n"
    "Why: speed + detail = better execution.\n\n"
    f"{_promo_block(AUDIENCE_CHANNEL)}"
)

CONVERSION_TRIAL = (
    "🧪 Want to try VIP first?\n\n"
    "Grab a 24h trial for $10 and see the difference.\n\n"
    "Why: the trial shows you the speed and details.\n\n"
    f"{_promo_block(AUDIENCE_CHANNEL)}"
)

CONVERSION_SCARCITY = (
    "⚠️ VIP spots are limited.\n\n"
    "We keep the group small so entries stay fast and support stays responsive.\n\n"
    "Why: smaller groups keep entries clean.\n\n"
    f"{_promo_block(AUDIENCE_CHANNEL)}"
)


INTRO_LINES = [
    "Optitrade Signals — clear setups, clear expiry, and transparent results.",
    "APEX signals: simple entries, consistent rules, and honest recaps.",
    "We focus on quality setups and clean execution, not noise.",
    "Trade smart: one setup at a time, same rules every session.",
]

MOTIVATION_LINES = [
    "Discipline beats hype. Stick to the plan and let the edge play out.",
    "Protect capital first. The wins follow the process.",
    "One trade doesn’t define the day — consistency does.",
    "Patience pays. Wait for your window and execute cleanly.",
]

PROMO_LINES = [
    'VIP gets earlier entries and full details. Reply "VIP" to upgrade.',
    'Want the earliest alerts? Message "VIP" or "TRIAL".',
    "VIP members see entries first and get priority support.",
    "Upgrade to VIP for early entries and fewer delays.",
]


def build_follow_instructions_message(audience: str = AUDIENCE_CHANNEL) -> str:
    lines = [
        "✅ How to follow signals correctly:",
        "1. Register here: https://optitrade.site/?ref=APEX",
        "2. Deposit minimum $50",
        "3. Use the same expiry & entry",
        "",
        "⚠️ Signals only work properly on our platform.",
        "",
        "Why: matching the platform keeps entries consistent.",
        "",
        _promo_block(audience),
    ]
    return "\n".join(lines)


def build_vip_welcome_message() -> str:
    return (
        "👑 Welcome to VIP!\n\n"
        "You’ll get early entries, full details, and priority support. 🚀\n\n"
        "Why: the edge is speed + clean execution.\n\n"
        f"{_promo_block(AUDIENCE_VIP)}"
    )


def build_vip_rules_message() -> str:
    lines = [
        "📌 VIP rules to get the best results:",
        "1. Only take signals inside the entry window.",
        "2. Use the exact expiry & direction we send.",
        "3. Skip late entries — wait for the next setup.",
        "4. Keep risk per trade consistent.",
        "",
        "Why: consistency protects the edge.",
        "",
        _promo_block(AUDIENCE_VIP),
    ]
    return "\n".join(lines)


def build_vip_follow_message() -> str:
    lines = [
        "🧭 How to follow VIP signals:",
        "1. Trade on the official platform.",
        "2. Match expiry, entry window, and direction exactly.",
        "3. Copy the code we send and paste it on the website.",
        "",
        "Why: the code links the signal to the correct entry.",
        "",
        _promo_block(AUDIENCE_VIP),
    ]
    return "\n".join(lines)


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
