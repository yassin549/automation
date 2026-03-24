from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import time
from pathlib import Path

from .config import load_config
from .sender import run_sender

DEFAULT_RESULT_DELAY_SECONDS = 75.0
DEFAULT_FREE_DELAY_SECONDS = 150.0
DEFAULT_DAILY_RECAP_TIME = time(18, 0)
DEFAULT_WEEKLY_RECAP_TIME = time(19, 0)
DEFAULT_CONVERSION_TIME = time(13, 0)
DEFAULT_EXAMPLE_START_BALANCE = 100
DEFAULT_EXAMPLE_RISK_PER_TRADE = 10
DEFAULT_PAYOUT_RATIO = 0.8
DEFAULT_AUTO_WIN_RATE = 0.9
DEFAULT_MAX_LATE_SECONDS = 60.0
DEFAULT_TIMEZONE = "Africa/Tunis"


def _positive_float(value: float, name: str, parser: argparse.ArgumentParser) -> float:
    if value <= 0:
        parser.error(f"{name} must be greater than 0.")
    return value


def _positive_int(value: int, name: str, parser: argparse.ArgumentParser) -> int:
    if value <= 0:
        parser.error(f"{name} must be greater than 0.")
    return value


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _parse_time(value: str, name: str, parser: argparse.ArgumentParser) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError:
        parser.error(f"{name} must be in HH:MM format.")
    raise RuntimeError("Unreachable")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send Telegram trading signals.")
    parser.add_argument("--once", action="store_true", help="Run one day and exit.")
    parser.add_argument(
        "--mode",
        choices=["day", "morning", "evening", "recap"],
        default="day",
        help="Run mode (default: day).",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path.cwd() / "plan.json",
        help="Path to the daily plan JSON (default: ./plan.json).",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path.cwd() / ".ghost_state.json",
        help="Path to persist state (default: ./.ghost_state.json).",
    )
    parser.add_argument(
        "--vip-channel",
        type=str,
        help="Optional VIP channel username or ID.",
    )
    parser.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help="Timezone for schedule (default: Africa/Tunis).",
    )
    parser.add_argument(
        "--result-delay",
        type=float,
        default=DEFAULT_RESULT_DELAY_SECONDS,
        help="Seconds to wait before posting results (default: 75).",
    )
    parser.add_argument(
        "--free-delay",
        type=float,
        default=DEFAULT_FREE_DELAY_SECONDS,
        help="Seconds to delay free signals after VIP (default: 150).",
    )
    parser.add_argument(
        "--daily-recap-time",
        type=str,
        default=DEFAULT_DAILY_RECAP_TIME.isoformat(timespec="minutes"),
        help="Daily recap time HH:MM (default: 18:00).",
    )
    parser.add_argument(
        "--weekly-recap-time",
        type=str,
        default=DEFAULT_WEEKLY_RECAP_TIME.isoformat(timespec="minutes"),
        help="Weekly recap time HH:MM (default: 19:00).",
    )
    parser.add_argument(
        "--conversion-time",
        type=str,
        default=DEFAULT_CONVERSION_TIME.isoformat(timespec="minutes"),
        help="Conversion post time HH:MM (default: 13:00).",
    )
    parser.add_argument(
        "--auto-plan",
        action="store_true",
        help="Generate signals automatically (random direction, win-rate biased).",
    )
    parser.add_argument(
        "--auto-win-rate",
        type=float,
        default=DEFAULT_AUTO_WIN_RATE,
        help="Win rate for auto plan (default: 0.9).",
    )
    parser.add_argument(
        "--example-start-balance",
        type=int,
        default=DEFAULT_EXAMPLE_START_BALANCE,
        help="Example starting balance for recaps (default: 100).",
    )
    parser.add_argument(
        "--example-risk",
        type=int,
        default=DEFAULT_EXAMPLE_RISK_PER_TRADE,
        help="Example risk per trade for recaps (default: 10).",
    )
    parser.add_argument(
        "--payout-ratio",
        type=float,
        default=DEFAULT_PAYOUT_RATIO,
        help="Payout ratio for profit examples (default: 0.8).",
    )
    parser.add_argument(
        "--post-rules",
        action="store_true",
        help="Post the rules message at startup.",
    )
    parser.add_argument(
        "--post-checklist",
        action="store_true",
        help="Post the assistant checklist at startup.",
    )
    parser.add_argument(
        "--pin-rules",
        action="store_true",
        help="Pin the rules message when posting it.",
    )
    parser.add_argument(
        "--max-late-seconds",
        type=float,
        default=DEFAULT_MAX_LATE_SECONDS,
        help="Max seconds late before skipping a scheduled post (default: 60).",
    )
    parser.add_argument(
        "--allow-stale-plan-date",
        action="store_true",
        help="Allow running a plan file whose date doesn't match today.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)

    args.plan = _resolve_path(args.plan)
    args.state = _resolve_path(args.state)
    args.result_delay = _positive_float(args.result_delay, "--result-delay", parser)
    args.free_delay = _positive_float(args.free_delay, "--free-delay", parser)
    args.example_start_balance = _positive_int(
        args.example_start_balance, "--example-start-balance", parser
    )
    args.example_risk = _positive_int(args.example_risk, "--example-risk", parser)
    if not (0 < args.payout_ratio <= 1.5):
        parser.error("--payout-ratio must be between 0 and 1.5.")
    if not (0 <= args.auto_win_rate <= 1):
        parser.error("--auto-win-rate must be between 0 and 1.")

    args.daily_recap_time = _parse_time(
        args.daily_recap_time, "--daily-recap-time", parser
    )
    args.weekly_recap_time = _parse_time(
        args.weekly_recap_time, "--weekly-recap-time", parser
    )
    args.conversion_time = _parse_time(
        args.conversion_time, "--conversion-time", parser
    )

    args.max_late_seconds = _positive_float(
        args.max_late_seconds, "--max-late-seconds", parser
    )
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger("ghost")

    config = load_config(
        plan_path=args.plan,
        state_path=args.state,
        timezone=args.timezone,
        result_delay_seconds=args.result_delay,
        free_delay_seconds=args.free_delay,
        daily_recap_time=args.daily_recap_time,
        weekly_recap_time=args.weekly_recap_time,
        conversion_time=args.conversion_time,
        auto_plan=args.auto_plan,
        auto_win_rate=args.auto_win_rate,
        example_start_balance=args.example_start_balance,
        example_risk_per_trade=args.example_risk,
        payout_ratio=args.payout_ratio,
        post_rules_on_start=args.post_rules,
        post_checklist_on_start=args.post_checklist,
        pin_rules=args.pin_rules,
        max_late_seconds=args.max_late_seconds,
        allow_stale_plan_date=args.allow_stale_plan_date,
        vip_channel=args.vip_channel,
    )

    try:
        asyncio.run(run_sender(config, logger, once=args.once, mode=args.mode))
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")


if __name__ == "__main__":
    main()
