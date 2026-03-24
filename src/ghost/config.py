from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from pathlib import Path
import os


@dataclass(frozen=True)
class AppConfig:
    api_id: int
    api_hash: str
    session: str
    channel: str
    vip_channel: str | None
    plan_path: Path
    state_path: Path
    timezone: str
    result_delay_seconds: float
    free_delay_seconds: float
    daily_recap_time: time
    weekly_recap_time: time
    conversion_time: time
    auto_plan: bool
    auto_win_rate: float
    example_start_balance: int
    example_risk_per_trade: int
    payout_ratio: float
    post_rules_on_start: bool
    post_checklist_on_start: bool
    pin_rules: bool
    max_late_seconds: float
    allow_stale_plan_date: bool


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    value = value.strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_config(
    plan_path: Path,
    state_path: Path,
    timezone: str,
    result_delay_seconds: float,
    free_delay_seconds: float,
    daily_recap_time: time,
    weekly_recap_time: time,
    conversion_time: time,
    auto_plan: bool,
    auto_win_rate: float,
    example_start_balance: int,
    example_risk_per_trade: int,
    payout_ratio: float,
    post_rules_on_start: bool,
    post_checklist_on_start: bool,
    pin_rules: bool,
    max_late_seconds: float,
    allow_stale_plan_date: bool,
    vip_channel: str | None,
) -> AppConfig:
    api_id_raw = require_env("API_ID")
    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise RuntimeError("API_ID must be an integer.") from exc

    resolved_vip = vip_channel or optional_env("VIP_CHANNEL_USERNAME")

    return AppConfig(
        api_id=api_id,
        api_hash=require_env("API_HASH"),
        session=require_env("TELEGRAM_SESSION"),
        channel=require_env("CHANNEL_USERNAME"),
        vip_channel=resolved_vip,
        plan_path=plan_path,
        state_path=state_path,
        timezone=timezone,
        result_delay_seconds=result_delay_seconds,
        free_delay_seconds=free_delay_seconds,
        daily_recap_time=daily_recap_time,
        weekly_recap_time=weekly_recap_time,
        conversion_time=conversion_time,
        auto_plan=auto_plan,
        auto_win_rate=auto_win_rate,
        example_start_balance=example_start_balance,
        example_risk_per_trade=example_risk_per_trade,
        payout_ratio=payout_ratio,
        post_rules_on_start=post_rules_on_start,
        post_checklist_on_start=post_checklist_on_start,
        pin_rules=pin_rules,
        max_late_seconds=max_late_seconds,
        allow_stale_plan_date=allow_stale_plan_date,
    )
