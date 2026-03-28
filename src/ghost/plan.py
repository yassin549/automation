from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import random
from typing import Any

from zoneinfo import ZoneInfo

SESSION_WINDOWS: dict[str, tuple[time, time]] = {
    "morning": (time(9, 0), time(11, 0)),
    "evening": (time(15, 30), time(17, 30)),
}

DEFAULT_ASSET = "EUR/USD (OTC)"
DEFAULT_EXPIRY = "1 Minute"
DEFAULT_ENTRY_WINDOW = "NOW - 10s"
DEFAULT_ENTRY = "NOW"
DEFAULT_CONFIDENCE = 85
DEFAULT_MARKET_CONDITION = "Rejection Zone"
DEFAULT_INSIGHT = "Liquidity sweep -> bearish continuation"

MIN_SIGNALS_PER_SESSION = 3
MAX_SIGNALS_PER_SESSION = 6
MIN_SIGNALS_PER_DAY = 6
MAX_SIGNALS_PER_DAY = 12

MIN_SESSION_MINUTES = 20
MAX_SESSION_MINUTES = 60
DEFAULT_PRE_SIGNAL_BUFFER_SECONDS = 60


@dataclass(frozen=True)
class SignalPlan:
    asset: str
    direction: str
    expiry: str
    entry_window: str
    entry: str
    confidence: int
    market_condition: str
    insight: str
    result: str
    signal_time: time | None


@dataclass(frozen=True)
class DayPlan:
    date: date | None
    sessions: dict[str, list[SignalPlan]]


class PlanError(RuntimeError):
    pass


def load_plan(path: Path, tz: ZoneInfo, today: date, allow_stale_date: bool) -> DayPlan:
    if not path.exists():
        raise PlanError(f"Plan file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PlanError("Plan file must contain a JSON object.")

    plan_date = _parse_plan_date(data.get("date"))
    if plan_date and plan_date != today and not allow_stale_date:
        raise PlanError(
            f"Plan date {plan_date.isoformat()} does not match today {today.isoformat()}."
        )

    sessions_raw = data.get("sessions")
    if not isinstance(sessions_raw, dict):
        raise PlanError("Plan must include a 'sessions' object.")

    sessions: dict[str, list[SignalPlan]] = {}
    for session_name in SESSION_WINDOWS.keys():
        signals_raw = sessions_raw.get(session_name)
        if not isinstance(signals_raw, list):
            raise PlanError(f"Session '{session_name}' must be a list of signals.")
        signals = [_parse_signal(item) for item in signals_raw]
        _validate_session(session_name, signals, tz, today)
        sessions[session_name] = signals

    _validate_daily_counts(sessions)
    return DayPlan(date=plan_date, sessions=sessions)


def generate_plan(today: date, win_rate: float) -> DayPlan:
    if not (0 <= win_rate <= 1):
        raise PlanError("Auto win rate must be between 0 and 1.")

    rng = random.Random(f"{today.isoformat()}:auto")
    counts = _auto_counts(rng)
    total = sum(counts.values())
    win_target = max(0, min(total, int(round(total * win_rate))))
    results = ["WIN"] * win_target + ["LOSS"] * (total - win_target)
    rng.shuffle(results)

    sessions: dict[str, list[SignalPlan]] = {}
    result_index = 0
    for session_name in SESSION_WINDOWS.keys():
        signals: list[SignalPlan] = []
        for _ in range(counts[session_name]):
            direction = rng.choice(["PUT", "CALL"])
            result = results[result_index]
            result_index += 1
            signals.append(
                SignalPlan(
                    asset=DEFAULT_ASSET,
                    direction=direction,
                    expiry=DEFAULT_EXPIRY,
                    entry_window=DEFAULT_ENTRY_WINDOW,
                    entry=DEFAULT_ENTRY,
                    confidence=DEFAULT_CONFIDENCE,
                    market_condition=DEFAULT_MARKET_CONDITION,
                    insight=DEFAULT_INSIGHT,
                    result=result,
                    signal_time=None,
                )
            )
        sessions[session_name] = signals

    _validate_daily_counts(sessions)
    return DayPlan(date=today, sessions=sessions)


def schedule_signals(
    session_name: str,
    signals: list[SignalPlan],
    session_date: date,
    tz: ZoneInfo,
) -> list[datetime]:
    start_time, end_time = SESSION_WINDOWS[session_name]
    start_dt = datetime.combine(session_date, start_time, tzinfo=tz)
    end_dt = datetime.combine(session_date, end_time, tzinfo=tz)

    if all(signal.signal_time is None for signal in signals):
        count = len(signals)
        if count == 0:
            return []
        window = (end_dt - start_dt).total_seconds()
        buffer_seconds = min(DEFAULT_PRE_SIGNAL_BUFFER_SECONDS, max(0, window))
        max_duration = min(MAX_SESSION_MINUTES * 60, max(0, window - buffer_seconds))
        min_duration = min(MIN_SESSION_MINUTES * 60, max_duration)
        rng = random.Random(f"{session_date.isoformat()}:{session_name}")
        duration = max_duration if max_duration == min_duration else rng.uniform(
            min_duration, max_duration
        )
        base_start = start_dt + timedelta(seconds=buffer_seconds)
        if count == 1:
            return [base_start + timedelta(seconds=duration / 2)]
        step = duration / (count - 1)
        offsets = [i * step for i in range(count)]
        return [base_start + timedelta(seconds=offset) for offset in offsets]

    scheduled: list[datetime] = []
    for signal in signals:
        if signal.signal_time is None:
            raise PlanError(
                f"Session '{session_name}' mixes timed and untimed signals."
            )
        scheduled.append(datetime.combine(session_date, signal.signal_time, tzinfo=tz))

    scheduled.sort()
    if len(scheduled) >= 2:
        duration = (scheduled[-1] - scheduled[0]).total_seconds()
        if duration < MIN_SESSION_MINUTES * 60 or duration > MAX_SESSION_MINUTES * 60:
            raise PlanError(
                f"Session '{session_name}' duration must be {MIN_SESSION_MINUTES}-"
                f"{MAX_SESSION_MINUTES} minutes."
            )
    return scheduled


def _parse_plan_date(value: Any) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PlanError("Plan date must be a string in YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PlanError("Plan date must be in YYYY-MM-DD format.") from exc


def _parse_signal(raw: Any) -> SignalPlan:
    if not isinstance(raw, dict):
        raise PlanError("Each signal must be an object.")

    direction = _require_str(raw.get("direction"), "direction").upper()
    if direction not in {"PUT", "CALL"}:
        raise PlanError("Signal direction must be PUT or CALL.")

    result = _require_str(raw.get("result"), "result").upper()
    if result not in {"WIN", "LOSS"}:
        raise PlanError("Signal result must be WIN or LOSS.")

    confidence = raw.get("confidence", DEFAULT_CONFIDENCE)
    if not isinstance(confidence, int) or not (1 <= confidence <= 100):
        raise PlanError("Signal confidence must be an integer between 1 and 100.")

    signal_time = _parse_time(raw.get("time"))

    return SignalPlan(
        asset=_optional_str(raw.get("asset"), DEFAULT_ASSET),
        direction=direction,
        expiry=_optional_str(raw.get("expiry"), DEFAULT_EXPIRY),
        entry_window=_optional_str(raw.get("entry_window"), DEFAULT_ENTRY_WINDOW),
        entry=_optional_str(raw.get("entry"), DEFAULT_ENTRY),
        confidence=confidence,
        market_condition=_optional_str(
            raw.get("market_condition"), DEFAULT_MARKET_CONDITION
        ),
        insight=_optional_str(raw.get("insight"), DEFAULT_INSIGHT),
        result=result,
        signal_time=signal_time,
    )


def _parse_time(value: Any) -> time | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PlanError("Signal time must be a string in HH:MM format.")
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise PlanError("Signal time must be in HH:MM format.") from exc


def _validate_session(
    session_name: str, signals: list[SignalPlan], tz: ZoneInfo, today: date
) -> None:
    count = len(signals)
    if not (MIN_SIGNALS_PER_SESSION <= count <= MAX_SIGNALS_PER_SESSION):
        raise PlanError(
            f"Session '{session_name}' must have {MIN_SIGNALS_PER_SESSION}-"
            f"{MAX_SIGNALS_PER_SESSION} signals."
        )

    scheduled = [
        datetime.combine(today, signal.signal_time, tzinfo=tz)
        for signal in signals
        if signal.signal_time is not None
    ]
    if scheduled:
        start_time, end_time = SESSION_WINDOWS[session_name]
        start_dt = datetime.combine(today, start_time, tzinfo=tz)
        end_dt = datetime.combine(today, end_time, tzinfo=tz)
        for timestamp in scheduled:
            if timestamp < start_dt or timestamp > end_dt:
                raise PlanError(
                    f"Signal time {timestamp.time()} is outside the {session_name} window."
                )


def _validate_daily_counts(sessions: dict[str, list[SignalPlan]]) -> None:
    total = sum(len(signals) for signals in sessions.values())
    if not (MIN_SIGNALS_PER_DAY <= total <= MAX_SIGNALS_PER_DAY):
        raise PlanError(
            f"Daily total signals must be {MIN_SIGNALS_PER_DAY}-{MAX_SIGNALS_PER_DAY}."
        )


def _require_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"Signal field '{name}' is required.")
    return value.strip()


def _optional_str(value: Any, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise PlanError("Signal fields must be strings.")
    cleaned = value.strip()
    return cleaned if cleaned else default


def _auto_counts(rng: random.Random) -> dict[str, int]:
    morning = rng.randint(MIN_SIGNALS_PER_SESSION, MAX_SIGNALS_PER_SESSION)
    min_evening = max(MIN_SIGNALS_PER_SESSION, MIN_SIGNALS_PER_DAY - morning)
    max_evening = min(MAX_SIGNALS_PER_SESSION, MAX_SIGNALS_PER_DAY - morning)
    if min_evening > max_evening:
        morning = rng.randint(MIN_SIGNALS_PER_SESSION, MAX_SIGNALS_PER_SESSION)
        min_evening = max(MIN_SIGNALS_PER_SESSION, MIN_SIGNALS_PER_DAY - morning)
        max_evening = min(MAX_SIGNALS_PER_SESSION, MAX_SIGNALS_PER_DAY - morning)
    evening = rng.randint(min_evening, max_evening)
    return {"morning": morning, "evening": evening}
