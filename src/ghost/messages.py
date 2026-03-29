from __future__ import annotations

from dataclasses import dataclass


Message = str


@dataclass(frozen=True)
class RecapStats:
    total: int
    wins: int
    losses: int
    best_win_streak: int = 0
    best_loss_streak: int = 0


AUDIENCE_CHANNEL = "channel"
AUDIENCE_VIP = "vip"


TRADE_PROMO = (
    "🔥 Why we use Optitrade:\n"
    "\n"
    "• 100% deposit bonus 💰  \n"
    "• Fast withdrawals ⚡  \n"
    "• Smooth execution ✅  \n"
    "\n"
    " https://optitrade.site/?ref=APEX"
)

PRE_SESSION_BASE = "⏳ New trading session starting in 5 minutes..."
PRE_SESSION_CHANNEL_EXTRA = "⚠️ Signals will only be valid during this time, don’t be late."
PRE_SESSION_VIP_EXTRA = "💎 We’ll drop all VIP setups inside this session window, stay ready."

SIGNAL_DETAILS = (
    "🚨 new sinal:\n"
    "\n"
    "Asset: {asset}  \n"
    "Direction: {direction}  \n"
    "Expiry: {expiry}  \n"
    "Entry window: {entry_window}"
)

CODE_INTRO = "🔑 Paste code below to match the entry:"
CODE_VALUE = "{code}"

RESULT_MESSAGE = "{result_emoji} {WIN_OR_LOSS}"

SESSION_RECAP_CHANNEL = (
    "📊 {session_label} recap:\n"
    "\n"
    "Signals: {total}  \n"
    "Wins: {wins}  \n"
    "Losses: {losses}  \n"
    "Win rate: {winrate}%  \n"
    "Best win streak: {best_win_streak}  \n"
    "Worst loss streak: {best_loss_streak}"
)

SESSION_RECAP_VIP = (
    "📊 {session_label} recap:\n"
    "\n"
    "{total} trades  \n"
    "{wins} wins  \n"
    "{losses} losses  \n"
    "{winrate}% win rate  \n"
    "Best run: {best_win_streak} wins  \n"
    "Worst run: {best_loss_streak} losses"
)

DAILY_RECAP = (
    "📅 Daily recap:\n"
    "\n"
    "Session (Morning)\n"
    "\n"
    "🌅 Morning session done:\n"
    "\n"
    "Signals: {morning_total}  \n"
    "Wins: {morning_wins}  \n"
    "Losses: {morning_losses}  \n"
    "Win rate: {morning_win_rate}%\n"
    "\n"
    "Session (Evening)\n"
    "\n"
    "🌙 Evening session done:\n"
    "\n"
    "Signals: {evening_total}  \n"
    "Wins: {evening_wins}  \n"
    "Losses: {evening_losses}  \n"
    "Win rate: {evening_win_rate}%"
)

WEEKLY_RECAP = (
    "📆 Weekly recap:\n"
    "\n"
    "Total: {total}  \n"
    "Wins: {wins}  \n"
    "Losses: {losses}  \n"
    "Win rate: {win_rate}%\n"
    "\n"
    "Example:\n"
    "\n"
    "Start: ${starting_balance}  \n"
    "Net: {net_profit}"
)

CONVERSION_SOFT = (
    "🟢 Soft\n"
    "\n"
    "VIP gives you:\n"
    "\n"
    "• Earlier entries  \n"
    "• Full reasoning  \n"
    "• Priority help  \n"
    "\n"
    "Message \"VIP\" or \"TRIAL\" if you want in."
)

CONVERSION_TRIAL = (
    "🧪 Trial\n"
    "\n"
    "Try VIP for 24h\n"
    "\n"
    "Access: $10\n"
    "\n"
    "Reply \"TRIAL\" to start."
)

CONVERSION_SCARCITY_OPTIONS = (
    "Join VIP to get the best entries.",
    "Limited VIP spots for $50 one-time purchase.",
    "Join VIP to get 10 signals every day.",
)

WIN_STREAK_PUSH = (
    "🔥 {streak} wins back-to-back\n"
    "\n"
    "💎 VIP got in earlier on every one.\n"
    "\n"
    "⏳ Free signals come later for a reason."
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


def build_session_recap_channel(session_name: str, stats: RecapStats) -> str:
    return SESSION_RECAP_CHANNEL.format(
        session_label=_session_label(session_name),
        total=stats.total,
        wins=stats.wins,
        losses=stats.losses,
        winrate=_win_rate(stats),
        best_win_streak=stats.best_win_streak,
        best_loss_streak=stats.best_loss_streak,
    )


def build_session_recap_vip(session_name: str, stats: RecapStats) -> str:
    return SESSION_RECAP_VIP.format(
        session_label=_session_label(session_name),
        total=stats.total,
        wins=stats.wins,
        losses=stats.losses,
        winrate=_win_rate(stats),
        best_win_streak=stats.best_win_streak,
        best_loss_streak=stats.best_loss_streak,
    )


def build_daily_recap(morning: RecapStats, evening: RecapStats) -> str:
    return DAILY_RECAP.format(
        morning_total=morning.total,
        morning_wins=morning.wins,
        morning_losses=morning.losses,
        morning_win_rate=_win_rate(morning),
        evening_total=evening.total,
        evening_wins=evening.wins,
        evening_losses=evening.losses,
        evening_win_rate=_win_rate(evening),
    )


def build_weekly_recap(
    stats: RecapStats, starting_balance: int, net_profit: str
) -> str:
    return WEEKLY_RECAP.format(
        total=stats.total,
        wins=stats.wins,
        losses=stats.losses,
        win_rate=_win_rate(stats),
        starting_balance=starting_balance,
        net_profit=net_profit,
    )


def build_conversion_soft() -> str:
    return CONVERSION_SOFT


def build_conversion_trial() -> str:
    return CONVERSION_TRIAL


def build_conversion_scarcity(index: int) -> str:
    if not CONVERSION_SCARCITY_OPTIONS:
        return ""
    return CONVERSION_SCARCITY_OPTIONS[index % len(CONVERSION_SCARCITY_OPTIONS)]


def conversion_scarcity_count() -> int:
    return len(CONVERSION_SCARCITY_OPTIONS)


def build_win_streak_push(streak: int) -> str:
    return WIN_STREAK_PUSH.format(streak=streak)


def _win_rate(stats: RecapStats) -> int:
    if stats.total <= 0:
        return 0
    return round(stats.wins / stats.total * 100)


def _session_label(session_name: str) -> str:
    return session_name.replace("_", " ").title()
