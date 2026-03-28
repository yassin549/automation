from __future__ import annotations

from dataclasses import dataclass


Message = str


@dataclass(frozen=True)
class RecapStats:
    total: int
    wins: int
    losses: int


AUDIENCE_CHANNEL = "channel"
AUDIENCE_VIP = "vip"


TRADE_PROMO = (
    " Why we use Optitrade:\n"
    "\n"
    "• 100% deposit bonus  \n"
    "• Fast withdrawals  \n"
    "• Smooth execution  \n"
    "\n"
    " https://optitrade.site/?ref=APEX"
)

PRE_SESSION_BASE = "⏳ New trading session starting in 5 minutes..."
PRE_SESSION_CHANNEL_EXTRA = "Signals will only be valid during this time, don’t be late."
PRE_SESSION_VIP_EXTRA = "We’ll drop all VIP setups inside this session window, stay ready."

SIGNAL_DETAILS = (
    " New setup\n"
    "\n"
    "Asset: {asset}  \n"
    "Direction: {direction}  \n"
    "Expiry: {expiry}  \n"
    "Entry window: {entry_window}"
)

CODE_INTRO = "Paste code below to match the entry:"
CODE_VALUE = "{code}"

RESULT_MESSAGE = "{result_emoji} {WIN_OR_LOSS}"

SESSION_RECAP_CHANNEL = (
    "Session recap:\n"
    "\n"
    "Signals: {total}  \n"
    "Wins: {wins}  \n"
    "Losses: {losses}  \n"
    "Win rate: {winrate}%"
)

SESSION_RECAP_VIP = (
    "Session done:\n"
    "\n"
    "{total} trades  \n"
    "{wins} wins  \n"
    "{losses} losses"
)

FINAL_PUSH = (
    " Solid session today\n"
    "\n"
    "VIP caught the best entries again.\n"
    "\n"
    "Free signals are always delayed.\n"
    "\n"
    "Message 'VIP'"
)


class SignalLike:
    asset: str
    direction: str
    expiry: str
    entry_window: str


def build_trade_promo_message() -> str:
    return TRADE_PROMO


def build_pre_session_base() -> str:
    return PRE_SESSION_BASE


def build_pre_session_extra(audience: str) -> str:
    if audience == AUDIENCE_VIP:
        return PRE_SESSION_VIP_EXTRA
    return PRE_SESSION_CHANNEL_EXTRA


def build_signal_details(signal: "SignalLike") -> str:
    return SIGNAL_DETAILS.format(
        asset=signal.asset,
        direction=signal.direction,
        expiry=signal.expiry,
        entry_window=signal.entry_window,
    )


def build_code_intro() -> str:
    return CODE_INTRO


def build_code_value(code: str) -> str:
    return CODE_VALUE.format(code=code)


def build_result_message(result: str) -> str:
    outcome = "WIN" if result.upper() == "WIN" else "LOSS"
    emoji = "✅" if outcome == "WIN" else "❌"
    return RESULT_MESSAGE.format(result_emoji=emoji, WIN_OR_LOSS=outcome)


def build_session_recap_channel(stats: RecapStats) -> str:
    return SESSION_RECAP_CHANNEL.format(
        total=stats.total,
        wins=stats.wins,
        losses=stats.losses,
        winrate=_win_rate(stats),
    )


def build_session_recap_vip(stats: RecapStats) -> str:
    return SESSION_RECAP_VIP.format(
        total=stats.total,
        wins=stats.wins,
        losses=stats.losses,
    )


def build_final_push() -> str:
    return FINAL_PUSH


def _win_rate(stats: RecapStats) -> int:
    if stats.total <= 0:
        return 0
    return round(stats.wins / stats.total * 100)
