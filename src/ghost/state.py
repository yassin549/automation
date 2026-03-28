from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any


@dataclass
class Stats:
    total: int = 0
    wins: int = 0
    losses: int = 0

    def record(self, result: str) -> None:
        self.total += 1
        if result.upper() == "WIN":
            self.wins += 1
        else:
            self.losses += 1


@dataclass
class BotState:
    day: str
    week: str
    executed: set[str] = field(default_factory=set)
    daily: Stats = field(default_factory=Stats)
    weekly: Stats = field(default_factory=Stats)
    session_stats: dict[str, Stats] = field(default_factory=dict)
    channel_daily: Stats = field(default_factory=Stats)
    channel_weekly: Stats = field(default_factory=Stats)
    channel_session_stats: dict[str, Stats] = field(default_factory=dict)
    vip_daily: Stats = field(default_factory=Stats)
    vip_weekly: Stats = field(default_factory=Stats)
    vip_session_stats: dict[str, Stats] = field(default_factory=dict)
    channel_win_streak: int = 0
    win_streak: int = 0
    vip_push_posted_for_streak: bool = False
    conversion_posted: bool = False
    conversion_scarcity_index: int = 0
    session_loss_streak: dict[str, int] = field(default_factory=dict)
    session_stopped: dict[str, bool] = field(default_factory=dict)
    signal_sent_at: dict[str, str] = field(default_factory=dict)
    signal_codes: dict[str, str] = field(default_factory=dict)
    channel_results_posted: int = 0
    vip_welcome_sent: bool = False
    vip_rules_sent: bool = False
    vip_follow_pinned: bool = False

    def was_executed(self, action_id: str) -> bool:
        return action_id in self.executed

    def mark_executed(self, action_id: str) -> None:
        self.executed.add(action_id)

    def set_signal_sent_at(self, signal_id: str, timestamp: datetime) -> None:
        self.signal_sent_at[signal_id] = timestamp.isoformat()

    def get_signal_sent_at(self, signal_id: str) -> datetime | None:
        raw = self.signal_sent_at.get(signal_id)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def get_signal_code(self, signal_id: str) -> str | None:
        return self.signal_codes.get(signal_id)

    def set_signal_code(self, signal_id: str, code: str) -> None:
        self.signal_codes[signal_id] = code


def load_state(path: Path, today: str, week_id: str) -> BotState:
    if not path.exists():
        return _fresh_state(today, week_id)

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("State file is corrupted (expected a JSON object).")

    state = BotState(
        day=str(data.get("day", today)),
        week=str(data.get("week", week_id)),
        executed=set(data.get("executed", [])),
        daily=_load_stats(data.get("daily")),
        weekly=_load_stats(data.get("weekly")),
        session_stats=_load_session_stats(data.get("session_stats")),
        channel_daily=_load_stats(data.get("channel_daily")),
        channel_weekly=_load_stats(data.get("channel_weekly")),
        channel_session_stats=_load_session_stats(data.get("channel_session_stats")),
        vip_daily=_load_stats(data.get("vip_daily")),
        vip_weekly=_load_stats(data.get("vip_weekly")),
        vip_session_stats=_load_session_stats(data.get("vip_session_stats")),
        channel_win_streak=int(data.get("channel_win_streak", 0)),
        win_streak=int(data.get("win_streak", 0)),
        vip_push_posted_for_streak=bool(data.get("vip_push_posted_for_streak", False)),
        conversion_posted=bool(data.get("conversion_posted", False)),
        conversion_scarcity_index=int(data.get("conversion_scarcity_index", 0)),
        session_loss_streak={
            str(key): int(value)
            for key, value in (data.get("session_loss_streak") or {}).items()
        },
        session_stopped={
            str(key): bool(value)
            for key, value in (data.get("session_stopped") or {}).items()
        },
        signal_sent_at={
            str(key): str(value)
            for key, value in (data.get("signal_sent_at") or {}).items()
        },
        signal_codes={
            str(key): str(value) for key, value in (data.get("signal_codes") or {}).items()
        },
        channel_results_posted=int(data.get("channel_results_posted", 0)),
        vip_welcome_sent=bool(data.get("vip_welcome_sent", False)),
        vip_rules_sent=bool(data.get("vip_rules_sent", False)),
        vip_follow_pinned=bool(data.get("vip_follow_pinned", False)),
    )

    if state.week != week_id:
        state.week = week_id
        state.weekly = Stats()
        state.channel_weekly = Stats()
        state.vip_weekly = Stats()

    if state.day != today:
        state.day = today
        state.executed.clear()
        state.daily = Stats()
        state.win_streak = 0
        state.vip_push_posted_for_streak = False
        state.conversion_posted = False
        state.session_loss_streak.clear()
        state.session_stopped.clear()
        state.signal_sent_at.clear()
        state.signal_codes.clear()
        state.session_stats.clear()
        state.channel_daily = Stats()
        state.channel_win_streak = 0
        state.channel_session_stats.clear()
        state.channel_results_posted = 0
        state.vip_daily = Stats()
        state.vip_session_stats.clear()

    return state


def save_state(path: Path, state: BotState) -> None:
    payload: dict[str, Any] = {
        "day": state.day,
        "week": state.week,
        "executed": sorted(state.executed),
        "daily": _dump_stats(state.daily),
        "weekly": _dump_stats(state.weekly),
        "session_stats": _dump_session_stats(state.session_stats),
        "channel_daily": _dump_stats(state.channel_daily),
        "channel_weekly": _dump_stats(state.channel_weekly),
        "channel_session_stats": _dump_session_stats(state.channel_session_stats),
        "vip_daily": _dump_stats(state.vip_daily),
        "vip_weekly": _dump_stats(state.vip_weekly),
        "vip_session_stats": _dump_session_stats(state.vip_session_stats),
        "channel_win_streak": state.channel_win_streak,
        "win_streak": state.win_streak,
        "vip_push_posted_for_streak": state.vip_push_posted_for_streak,
        "conversion_posted": state.conversion_posted,
        "conversion_scarcity_index": state.conversion_scarcity_index,
        "session_loss_streak": state.session_loss_streak,
        "session_stopped": state.session_stopped,
        "signal_sent_at": state.signal_sent_at,
        "signal_codes": state.signal_codes,
        "channel_results_posted": state.channel_results_posted,
        "vip_welcome_sent": state.vip_welcome_sent,
        "vip_rules_sent": state.vip_rules_sent,
        "vip_follow_pinned": state.vip_follow_pinned,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fresh_state(today: str, week_id: str) -> BotState:
    return BotState(day=today, week=week_id)


def _load_stats(raw: Any) -> Stats:
    if not isinstance(raw, dict):
        return Stats()
    return Stats(
        total=int(raw.get("total", 0)),
        wins=int(raw.get("wins", 0)),
        losses=int(raw.get("losses", 0)),
    )


def _dump_stats(stats: Stats) -> dict[str, int]:
    return {"total": stats.total, "wins": stats.wins, "losses": stats.losses}


def _load_session_stats(raw: Any) -> dict[str, Stats]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): _load_stats(value) for key, value in raw.items()}


def _dump_session_stats(stats: dict[str, Stats]) -> dict[str, dict[str, int]]:
    return {key: _dump_stats(value) for key, value in stats.items()}
