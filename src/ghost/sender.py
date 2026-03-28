from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl import functions, types
from zoneinfo import ZoneInfo

from .config import AppConfig
from .messages import (
    AUDIENCE_CHANNEL,
    AUDIENCE_VIP,
    CONVERSION_SCARCITY,
    CONVERSION_SOFT,
    CONVERSION_TRIAL,
    ProfitExample,
    RecapStats,
    build_pre_session_message,
    build_follow_instructions_message,
    build_code_message,
    build_daily_recap_message,
    build_free_delayed_message,
    build_result_message,
    build_session_recap_message,
    build_signal_message,
    build_channel_promo_message,
    build_vip_promo_message,
    build_vip_push_message,
    build_vip_signal_message,
    build_vip_welcome_message,
    build_vip_rules_message,
    build_vip_follow_message,
    build_weekly_recap_message,
)
from .plan import (
    DayPlan,
    PlanError,
    SESSION_WINDOWS,
    generate_plan,
    load_plan,
    schedule_signals,
)
from .promo import generate_promo_code
from .proof import format_profit_text, load_proof_dir, render_proof_image
from .state import BotState, Stats, load_state, save_state

VIP_SIGNALS_PER_SESSION = 5
CHANNEL_SIGNALS_PER_SESSION = 1
FOLLOW_INSTRUCTIONS_EVERY = 4
PROMO_INTERVAL_HOURS = 2
PROMO_CHECK_INTERVAL_SECONDS = 60


@dataclass(frozen=True)
class PromoContext:
    client: TelegramClient
    config: AppConfig
    state: BotState
    logger: logging.Logger
    tz: ZoneInfo
    vip_target: object | None
    enabled: bool = True


async def run_sender(
    config: AppConfig,
    logger: logging.Logger,
    once: bool,
    mode: str,
) -> None:
    tz = ZoneInfo(config.timezone)
    client = TelegramClient(StringSession(config.session or ""), config.api_id, config.api_hash)

    await client.connect()
    try:
        if config.bot_token:
            if config.session:
                if not await client.is_user_authorized():
                    logger.warning(
                        "Session not authorized; attempting bot token authentication."
                    )
                    await client.start(bot_token=config.bot_token)
            else:
                logger.info("Using bot token authentication.")
                await client.start(bot_token=config.bot_token)

        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telegram client not authorized. Provide TELEGRAM_SESSION (authorized "
                "StringSession) or TELEGRAM_BOT_TOKEN."
            )

        vip_target = None
        if config.vip_channel and mode in {"day", "morning", "evening", "recap", "all"}:
            vip_target = await _resolve_vip_target(client, config.vip_channel, logger)

        if mode in {"day", "all"}:
            while True:
                now = datetime.now(tz)
                today = now.date()
                week_id = _week_id(today)
                state = load_state(config.state_path, today.isoformat(), week_id)
                promo = PromoContext(
                    client=client,
                    config=config,
                    state=state,
                    logger=logger,
                    tz=tz,
                    vip_target=vip_target,
                    enabled=True,
                )

                if config.auto_plan:
                    plan = generate_plan(today, config.auto_win_rate)
                else:
                    try:
                        plan = load_plan(
                            config.plan_path,
                            tz=tz,
                            today=today,
                            allow_stale_date=config.allow_stale_plan_date,
                        )
                    except PlanError as exc:
                        logger.error("Plan error: %s", exc)
                        if once:
                            return
                        await _wait_until(
                            datetime.now(tz) + timedelta(seconds=60), tz, promo
                        )
                        continue

                if vip_target is not None:
                    await _ensure_vip_onboarding(client, config, state, logger, vip_target)

                await _run_day(client, config, plan, state, logger, tz, vip_target, promo)

                if once:
                    return

                now = datetime.now(tz)
                next_day = datetime.combine(
                    now.date() + timedelta(days=1), time(0, 0), tzinfo=tz
                )
                logger.info("Day complete. Sleeping until %s.", next_day)
                await _wait_until(next_day, tz, promo)
        else:
            await _run_mode_once(client, config, logger, tz, vip_target, mode)
    finally:
        if client.is_connected():
            await client.disconnect()


async def _run_day(
    client: TelegramClient,
    config: AppConfig,
    plan: DayPlan,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
    vip_target: object | None,
    promo: PromoContext | None,
) -> None:
    today = datetime.now(tz).date()

    await _run_session(
        client,
        config,
        plan,
        state,
        logger,
        tz,
        today,
        "morning",
        vip_target,
        promo,
    )

    await _run_session(
        client,
        config,
        plan,
        state,
        logger,
        tz,
        today,
        "evening",
        vip_target,
        promo,
    )

    await _post_end_of_day_actions(
        client, config, state, logger, tz, today, vip_target, promo
    )


async def _run_session(
    client: TelegramClient,
    config: AppConfig,
    plan: DayPlan,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
    today: date,
    session_name: str,
    vip_target: object | None,
    promo: PromoContext | None,
) -> None:
    signals = plan.sessions[session_name]
    if vip_target is not None:
        signals = signals[:VIP_SIGNALS_PER_SESSION]
    schedule = schedule_signals(session_name, signals, today, tz)
    start_time, end_time = SESSION_WINDOWS[session_name]
    start_dt = datetime.combine(today, start_time, tzinfo=tz)
    end_dt = datetime.combine(today, end_time, tzinfo=tz)

    now = datetime.now(tz)
    if now > end_dt + timedelta(seconds=config.max_late_seconds):
        logger.info("Skipping %s session (window already closed).", session_name)
        return

    state.session_loss_streak.setdefault(session_name, 0)
    if session_name not in state.session_stopped:
        state.session_stopped[session_name] = False

    pre_channel_id = _action_id(today, session_name, "pre-channel")
    pre_vip_id = _action_id(today, session_name, "pre-vip")
    pre_channel_done = state.was_executed(pre_channel_id)
    pre_vip_done = vip_target is None or state.was_executed(pre_vip_id)
    if not (pre_channel_done and pre_vip_done):
        if datetime.now(tz) <= start_dt + timedelta(seconds=config.max_late_seconds):
            await _wait_until(start_dt, tz, promo)
            pre_sent = False
            if vip_target is not None and not state.was_executed(pre_vip_id):
                await _send_message(
                    client, vip_target, build_pre_session_message(AUDIENCE_VIP)
                )
                state.mark_executed(pre_vip_id)
                pre_sent = True
            if not state.was_executed(pre_channel_id):
                await _send_message(
                    client, config.channel, build_pre_session_message(AUDIENCE_CHANNEL)
                )
                state.mark_executed(pre_channel_id)
                pre_sent = True
            if pre_sent:
                state.session_loss_streak[session_name] = 0
                state.session_stopped[session_name] = False
                save_state(config.state_path, state)
        else:
            logger.warning("Skipping late pre-session post for %s.", session_name)

    if vip_target is not None:
        channel_indexes = set(range(min(CHANNEL_SIGNALS_PER_SESSION, len(signals))))
    else:
        channel_indexes = set(range(len(signals)))
    vip_extra_count = max(0, len(signals) - len(channel_indexes)) if vip_target else 0

    for index, (signal, scheduled_at) in enumerate(zip(signals, schedule)):
        if state.session_stopped.get(session_name, False):
            logger.warning("Stopping %s session after consecutive losses.", session_name)
            break

        signal_key = _signal_key(today, session_name, index)
        if datetime.now(tz) > scheduled_at + timedelta(seconds=config.max_late_seconds):
            logger.warning("Skipping late signal %s in %s session.", index + 1, session_name)
            continue

        await _wait_until(scheduled_at, tz, promo)

        code = _ensure_signal_code(state, signal_key, config)

        send_to_channel = index in channel_indexes

        if vip_target is not None:
            vip_id = f"{signal_key}:vip"
            if not state.was_executed(vip_id):
                await _send_message(client, vip_target, build_vip_signal_message(signal))
                state.mark_executed(vip_id)
                save_state(config.state_path, state)

            vip_code_id = f"{signal_key}:vip-code"
            if not state.was_executed(vip_code_id):
                await _send_message(
                    client,
                    vip_target,
                    build_code_message(code),
                )
                state.mark_executed(vip_code_id)
                save_state(config.state_path, state)

            if send_to_channel:
                free_id = f"{signal_key}:free"
                if not state.was_executed(free_id):
                    await asyncio.sleep(config.free_delay_seconds)
                    await _send_message(
                        client,
                        config.channel,
                        build_free_delayed_message(signal, vip_extra_count),
                    )
                    state.mark_executed(free_id)
                    save_state(config.state_path, state)

                free_code_id = f"{signal_key}:free-code"
                if not state.was_executed(free_code_id):
                    await _send_message(
                        client,
                        config.channel,
                        build_code_message(code),
                    )
                    state.mark_executed(free_code_id)
                    save_state(config.state_path, state)

            if state.get_signal_sent_at(signal_key) is None:
                state.set_signal_sent_at(signal_key, datetime.now(tz))
                save_state(config.state_path, state)
        else:
            free_id = f"{signal_key}:free"
            if not state.was_executed(free_id):
                await _send_message(
                    client, config.channel, build_signal_message(signal, AUDIENCE_CHANNEL)
                )
                state.mark_executed(free_id)
                save_state(config.state_path, state)

            free_code_id = f"{signal_key}:free-code"
            if not state.was_executed(free_code_id):
                await _send_message(
                    client,
                    config.channel,
                    build_code_message(code),
                )
                state.mark_executed(free_code_id)
                save_state(config.state_path, state)

            if state.get_signal_sent_at(signal_key) is None:
                state.set_signal_sent_at(signal_key, datetime.now(tz))
                save_state(config.state_path, state)

        result_id = f"{signal_key}:result"
        if not state.was_executed(result_id):
            await _wait_for_result(state, signal_key, scheduled_at, config, tz, promo)
            example_stats = RecapStats(
                total=1,
                wins=1 if signal.result.upper() == "WIN" else 0,
                losses=1 if signal.result.upper() == "LOSS" else 0,
            )
            example = _profit_example(
                example_stats,
                config.example_start_balance,
                config.example_risk_per_trade,
                config.payout_ratio,
            )
            if send_to_channel:
                result_message = build_result_message(
                    signal, signal.result, example, AUDIENCE_CHANNEL
                )
                await _send_message(client, config.channel, result_message)
                state.channel_results_posted += 1
                await _maybe_post_follow_instructions(client, config, state, logger)
                await _maybe_post_conversion_after_win(
                    client,
                    config,
                    state,
                    logger,
                    today,
                    session_name,
                    signal.result,
                )
            if vip_target is not None:
                result_message_vip = build_result_message(
                    signal, signal.result, example, AUDIENCE_VIP
                )
                await _send_message(client, vip_target, result_message_vip)
            await _maybe_send_proof(
                client,
                config,
                state,
                signal_key,
                scheduled_at,
                signal.result,
                example,
                tz,
                vip_target,
                send_to_channel,
            )
            state.mark_executed(result_id)
            _update_stats_after_result(
                state,
                session_name,
                signal.result,
                send_to_channel,
                vip_target is not None,
            )
            if send_to_channel:
                await _maybe_post_vip_push(client, config, state, logger)
            save_state(config.state_path, state)

    await _maybe_post_session_recap(client, config, state, logger, session_name)
    if vip_target is not None:
        await _maybe_post_vip_session_recap(
            client, config, state, logger, session_name, vip_target
        )


async def _wait_for_result(
    state: BotState,
    signal_key: str,
    scheduled_at: datetime,
    config: AppConfig,
    tz: ZoneInfo,
    promo: PromoContext | None,
) -> None:
    sent_at = state.get_signal_sent_at(signal_key) or scheduled_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=tz)
    result_at = sent_at + timedelta(seconds=config.result_delay_seconds)
    await _wait_until(result_at, tz, promo)


async def _maybe_post_vip_push(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
) -> None:
    if state.channel_win_streak < 2 or state.vip_push_posted_for_streak:
        return

    action_id = f"{state.day}:vip-push:{state.channel_win_streak}"
    if state.was_executed(action_id):
        return

    await _send_message(client, config.channel, build_vip_push_message())
    state.mark_executed(action_id)
    state.vip_push_posted_for_streak = True
    save_state(config.state_path, state)
    logger.info("VIP push sent after win streak.")


async def _maybe_post_follow_instructions(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
) -> None:
    if (
        state.channel_results_posted <= 0
        or state.channel_results_posted % FOLLOW_INSTRUCTIONS_EVERY != 0
    ):
        return

    action_id = f"{state.day}:follow:{state.channel_results_posted}"
    if state.was_executed(action_id):
        return

    await _send_message(
        client, config.channel, build_follow_instructions_message(AUDIENCE_CHANNEL)
    )
    state.mark_executed(action_id)
    save_state(config.state_path, state)
    logger.info("Follow instructions sent.")


async def _ensure_vip_onboarding(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    vip_target: object,
) -> None:
    if not state.vip_welcome_sent:
        await _send_message(client, vip_target, build_vip_welcome_message())
        state.vip_welcome_sent = True
        save_state(config.state_path, state)
        logger.info("VIP welcome message sent.")

    if not state.vip_rules_sent:
        await _send_message(client, vip_target, build_vip_rules_message())
        state.vip_rules_sent = True
        save_state(config.state_path, state)
        logger.info("VIP rules message sent.")

    if not state.vip_follow_pinned:
        message = await _send_message(client, vip_target, build_vip_follow_message())
        try:
            await client.pin_message(vip_target, message, notify=False)
            logger.info("VIP follow message pinned.")
        except Exception as exc:
            logger.warning("Failed to pin VIP follow message: %s", exc)
        state.vip_follow_pinned = True
        save_state(config.state_path, state)


async def _maybe_post_conversion_after_win(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    today: date,
    session_name: str,
    result: str,
) -> None:
    if state.conversion_posted:
        return
    if result.upper() != "WIN":
        return

    action_id = f"{state.day}:{session_name}:conversion"
    if state.was_executed(action_id):
        return

    message = _conversion_message_for_day(today)
    await _send_message(client, config.channel, message)
    state.mark_executed(action_id)
    state.conversion_posted = True
    save_state(config.state_path, state)
    logger.info("Conversion post sent after channel win.")


async def _maybe_post_daily_recap(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
) -> None:
    action_id = f"{state.day}:daily-recap"
    if state.was_executed(action_id):
        return

    stats = RecapStats(
        total=state.channel_daily.total,
        wins=state.channel_daily.wins,
        losses=state.channel_daily.losses,
    )
    example = _profit_example(
        stats,
        config.example_start_balance,
        config.example_risk_per_trade,
        config.payout_ratio,
    )
    await _send_message(
        client,
        config.channel,
        build_daily_recap_message(stats, example, AUDIENCE_CHANNEL),
    )
    state.mark_executed(action_id)
    save_state(config.state_path, state)
    logger.info("Daily recap sent.")


async def _maybe_post_vip_daily_recap(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    vip_target: object | None,
) -> None:
    if vip_target is None:
        return

    stats = RecapStats(
        total=state.vip_daily.total,
        wins=state.vip_daily.wins,
        losses=state.vip_daily.losses,
    )
    if stats.total <= 0:
        return

    action_id = f"{state.day}:daily-recap:vip"
    if state.was_executed(action_id):
        return

    example = _profit_example(
        stats,
        config.example_start_balance,
        config.example_risk_per_trade,
        config.payout_ratio,
    )
    await _send_message(
        client,
        vip_target,
        build_daily_recap_message(stats, example, AUDIENCE_VIP),
    )
    state.mark_executed(action_id)
    save_state(config.state_path, state)
    logger.info("VIP daily recap sent.")


async def _maybe_post_session_recap(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    session_name: str,
) -> None:
    action_id = f"{state.day}:{session_name}:session-recap"
    if state.was_executed(action_id):
        return

    stats = state.channel_session_stats.get(session_name)
    if not stats or stats.total <= 0:
        return

    recap = RecapStats(total=stats.total, wins=stats.wins, losses=stats.losses)
    await _send_message(
        client,
        config.channel,
        build_session_recap_message(session_name, recap, AUDIENCE_CHANNEL),
    )
    state.mark_executed(action_id)
    save_state(config.state_path, state)
    logger.info("Session recap sent for %s.", session_name)


async def _maybe_post_vip_session_recap(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    session_name: str,
    vip_target: object | None,
) -> None:
    if vip_target is None:
        return

    stats = state.vip_session_stats.get(session_name)
    if not stats or stats.total <= 0:
        return

    action_id = f"{state.day}:{session_name}:session-recap:vip"
    if state.was_executed(action_id):
        return

    recap = RecapStats(total=stats.total, wins=stats.wins, losses=stats.losses)
    await _send_message(
        client,
        vip_target,
        build_session_recap_message(session_name, recap, AUDIENCE_VIP),
    )
    state.mark_executed(action_id)
    save_state(config.state_path, state)
    logger.info("VIP session recap sent for %s.", session_name)


async def _maybe_post_weekly_recap(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    today: date,
) -> None:
    if today.weekday() != 6:
        return

    action_id = f"{state.week}:weekly-recap"
    if state.was_executed(action_id):
        return

    stats = RecapStats(
        total=state.channel_weekly.total,
        wins=state.channel_weekly.wins,
        losses=state.channel_weekly.losses,
    )
    examples = _weekly_examples(config, stats)
    await _send_message(
        client,
        config.channel,
        build_weekly_recap_message(stats, examples, AUDIENCE_CHANNEL),
    )
    state.mark_executed(action_id)
    save_state(config.state_path, state)
    logger.info("Weekly recap sent.")


async def _maybe_post_vip_weekly_recap(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    today: date,
    vip_target: object | None,
) -> None:
    if vip_target is None:
        return
    if today.weekday() != 6:
        return

    stats = RecapStats(
        total=state.vip_weekly.total,
        wins=state.vip_weekly.wins,
        losses=state.vip_weekly.losses,
    )
    if stats.total <= 0:
        return

    action_id = f"{state.week}:weekly-recap:vip"
    if state.was_executed(action_id):
        return

    examples = _weekly_examples(config, stats)
    await _send_message(
        client,
        vip_target,
        build_weekly_recap_message(stats, examples, AUDIENCE_VIP),
    )
    state.mark_executed(action_id)
    save_state(config.state_path, state)
    logger.info("VIP weekly recap sent.")


async def _maybe_send_proof(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    signal_key: str,
    scheduled_at: datetime,
    result: str,
    example: ProfitExample,
    tz: ZoneInfo,
    vip_target: object | None,
    send_channel_proof: bool,
) -> None:
    sent_at = state.get_signal_sent_at(signal_key) or scheduled_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=tz)

    proof_dir = load_proof_dir(Path.cwd())
    profit_text = format_profit_text(result, example.win_profit, example.loss_cost)
    profit_value = _profit_value(result, example.win_profit, example.loss_cost)
    payout_value = example.risk_per_trade + profit_value
    stake_text = f"${_format_amount(example.risk_per_trade)}"
    payout_text = f"${_format_amount(payout_value)}"
    proof_path = render_proof_image(
        proof_dir,
        result,
        sent_at,
        profit_text,
        stake_text,
        payout_text,
    )
    if not proof_path:
        return
    try:
        if send_channel_proof:
            await client.send_file(config.channel, proof_path)
        if vip_target is not None:
            await client.send_file(vip_target, proof_path)
    finally:
        try:
            proof_path.unlink()
        except FileNotFoundError:
            pass


async def _post_end_of_day_actions(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
    today: date,
    vip_target: object | None,
    promo: PromoContext | None,
) -> None:
    actions: list[tuple[datetime, str]] = [
        (datetime.combine(today, config.daily_recap_time, tzinfo=tz), "daily"),
    ]
    if today.weekday() == 6:
        actions.append((datetime.combine(today, config.weekly_recap_time, tzinfo=tz), "weekly"))

    actions.sort(key=lambda item: item[0])
    for scheduled_at, name in actions:
        await _wait_until(scheduled_at, tz, promo)
        if name == "daily":
            await _maybe_post_daily_recap(client, config, state, logger)
            await _maybe_post_vip_daily_recap(client, config, state, logger, vip_target)
        else:
            await _maybe_post_weekly_recap(client, config, state, logger, today)
            await _maybe_post_vip_weekly_recap(
                client, config, state, logger, today, vip_target
            )


def _weekly_examples(config: AppConfig, stats: RecapStats) -> list[ProfitExample]:
    examples: list[ProfitExample] = []
    risk_percent = config.example_risk_per_trade / config.example_start_balance
    for starting_balance in (50,):
        risk_per_trade = int(round(starting_balance * risk_percent))
        examples.append(
            _profit_example(stats, starting_balance, risk_per_trade, config.payout_ratio)
        )
    return examples


def _profit_example(
    stats: RecapStats, starting_balance: int, risk_per_trade: int, payout_ratio: float
) -> ProfitExample:
    win_profit = stats.wins * risk_per_trade * payout_ratio
    loss_cost = stats.losses * risk_per_trade
    net_profit = win_profit - loss_cost
    return ProfitExample(
        starting_balance=starting_balance,
        risk_per_trade=risk_per_trade,
        win_profit=_format_money(win_profit),
        loss_cost=_format_money(loss_cost),
        net_profit=_format_money(net_profit),
    )


def _format_money(value: float) -> str:
    rounded = round(value, 2)
    if isinstance(rounded, int):
        return str(rounded)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}"


def _format_amount(value: float) -> str:
    return f"{value:.2f}"


def _profit_value(result: str, win_profit: str, loss_cost: str) -> float:
    try:
        if result.upper() == "WIN":
            return float(win_profit)
        return -float(loss_cost)
    except ValueError:
        return 0.0


def _update_stats_after_result(
    state: BotState,
    session_name: str,
    result: str,
    send_to_channel: bool,
    send_to_vip: bool,
) -> None:
    state.daily.record(result)
    state.weekly.record(result)
    state.session_stats.setdefault(session_name, Stats()).record(result)
    if result.upper() == "WIN":
        state.win_streak += 1
        state.session_loss_streak[session_name] = 0
    else:
        state.win_streak = 0
        state.session_loss_streak[session_name] = state.session_loss_streak.get(session_name, 0) + 1
        if state.session_loss_streak[session_name] >= 2:
            state.session_stopped[session_name] = True

    if send_to_channel:
        state.channel_daily.record(result)
        state.channel_weekly.record(result)
        state.channel_session_stats.setdefault(session_name, Stats()).record(result)
        if result.upper() == "WIN":
            state.channel_win_streak += 1
        else:
            state.channel_win_streak = 0
            state.vip_push_posted_for_streak = False

    if send_to_vip:
        state.vip_daily.record(result)
        state.vip_weekly.record(result)
        state.vip_session_stats.setdefault(session_name, Stats()).record(result)


def _promo_slot(now: datetime) -> tuple[int, datetime]:
    slot_hour = (now.hour // PROMO_INTERVAL_HOURS) * PROMO_INTERVAL_HOURS
    slot_time = datetime.combine(
        now.date(), time(slot_hour, 0), tzinfo=now.tzinfo
    )
    return slot_hour, slot_time


async def _maybe_post_promos(promo: PromoContext) -> None:
    if not promo.enabled:
        return

    now = datetime.now(promo.tz)
    if promo.state.day != now.date().isoformat():
        return

    slot_hour, slot_time = _promo_slot(now)
    if now < slot_time:
        return

    slot_key = f"{promo.state.day}:promo:{slot_hour:02d}"
    channel_id = f"{slot_key}:channel"
    if not promo.state.was_executed(channel_id):
        await _send_message(
            promo.client,
            promo.config.channel,
            build_channel_promo_message(slot_key),
        )
        promo.state.mark_executed(channel_id)
        save_state(promo.config.state_path, promo.state)
        promo.logger.info("Channel promo sent for slot %02d.", slot_hour)

    if promo.vip_target is None:
        return

    vip_id = f"{slot_key}:vip"
    if promo.state.was_executed(vip_id):
        return

    await _send_message(
        promo.client,
        promo.vip_target,
        build_vip_promo_message(slot_key),
    )
    promo.state.mark_executed(vip_id)
    save_state(promo.config.state_path, promo.state)
    promo.logger.info("VIP promo sent for slot %02d.", slot_hour)


async def _wait_until(
    target: datetime, tz: ZoneInfo, promo: PromoContext | None = None
) -> None:
    while True:
        now = datetime.now(tz)
        if promo is not None:
            await _maybe_post_promos(promo)
        if target <= now:
            return
        sleep_for = min(PROMO_CHECK_INTERVAL_SECONDS, (target - now).total_seconds())
        await asyncio.sleep(sleep_for)


def _contains_url(message: str) -> bool:
    return "http://" in message or "https://" in message


async def _send_message(client: TelegramClient, channel: object, message: str | list[str]):
    if isinstance(message, list):
        first_message = None
        for part in message:
            if not part:
                continue
            sent = await _send_message(client, channel, part)
            if first_message is None:
                first_message = sent
        return first_message
    return await client.send_message(
        channel, message, link_preview=not _contains_url(message)
    )


async def _run_mode_once(
    client: TelegramClient,
    config: AppConfig,
    logger: logging.Logger,
    tz: ZoneInfo,
    vip_target: object | None,
    mode: str,
) -> None:
    now = datetime.now(tz)
    today = now.date()
    week_id = _week_id(today)
    state = load_state(config.state_path, today.isoformat(), week_id)

    if vip_target is not None and mode in {"day", "morning", "evening"}:
        await _ensure_vip_onboarding(client, config, state, logger, vip_target)

    if mode in {"morning", "evening"}:
        if config.auto_plan:
            plan = generate_plan(today, config.auto_win_rate)
        else:
            try:
                plan = load_plan(
                    config.plan_path,
                    tz=tz,
                    today=today,
                    allow_stale_date=config.allow_stale_plan_date,
                )
            except PlanError as exc:
                logger.error("Plan error: %s", exc)
                return

        await _run_session(
            client, config, plan, state, logger, tz, today, mode, vip_target, None
        )
        return

    if mode == "recap":
        await _post_actions_if_due(client, config, state, logger, tz, today, vip_target)
        return

    raise RuntimeError(f"Unknown mode: {mode}")


async def _post_actions_if_due(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
    today: date,
    vip_target: object | None,
) -> None:
    now = datetime.now(tz)
    daily_dt = datetime.combine(today, config.daily_recap_time, tzinfo=tz)
    weekly_dt = datetime.combine(today, config.weekly_recap_time, tzinfo=tz)

    if now >= daily_dt:
        await _maybe_post_daily_recap(client, config, state, logger)
        await _maybe_post_vip_daily_recap(client, config, state, logger, vip_target)
    if today.weekday() == 6 and now >= weekly_dt:
        await _maybe_post_weekly_recap(client, config, state, logger, today)
        await _maybe_post_vip_weekly_recap(
            client, config, state, logger, today, vip_target
        )


async def _resolve_vip_target(
    client: TelegramClient,
    vip_channel: str,
    logger: logging.Logger,
) -> object:
    invite_hash = _extract_invite_hash(vip_channel)
    if not invite_hash:
        return vip_channel

    try:
        check = await client(functions.messages.CheckChatInviteRequest(invite_hash))
        if isinstance(check, types.ChatInviteAlready):
            logger.info("VIP invite already joined: %s", check.chat.title)
            return check.chat
    except errors.InviteHashExpiredError as exc:
        raise RuntimeError("VIP invite link expired.") from exc

    try:
        updates = await client(functions.messages.ImportChatInviteRequest(invite_hash))
    except errors.UserAlreadyParticipantError:
        check = await client(functions.messages.CheckChatInviteRequest(invite_hash))
        if isinstance(check, types.ChatInviteAlready):
            return check.chat
        raise RuntimeError("VIP invite link already joined but chat not resolved.")

    chats = getattr(updates, "chats", [])
    if chats:
        logger.info("Joined VIP chat via invite link.")
        return chats[0]

    raise RuntimeError("Failed to resolve VIP chat from invite link.")


def _extract_invite_hash(value: str) -> str | None:
    cleaned = value.strip()
    if cleaned.startswith("https://"):
        cleaned = cleaned[len("https://") :]
    if cleaned.startswith("http://"):
        cleaned = cleaned[len("http://") :]
    cleaned = cleaned.lstrip("/")
    if cleaned.startswith("t.me/"):
        cleaned = cleaned[len("t.me/") :]
    if cleaned.startswith("telegram.me/"):
        cleaned = cleaned[len("telegram.me/") :]
    cleaned = cleaned.split("?")[0]
    if cleaned.startswith("+"):
        return cleaned[1:]
    if cleaned.startswith("joinchat/"):
        return cleaned[len("joinchat/") :]
    return None


def _conversion_message_for_day(today: date) -> str:
    index = today.toordinal() % 3
    if index == 0:
        return CONVERSION_SOFT
    if index == 1:
        return CONVERSION_TRIAL
    return CONVERSION_SCARCITY


def _week_id(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _action_id(day: date, session_name: str, label: str) -> str:
    return f"{day.isoformat()}:{session_name}:{label}"


def _signal_key(day: date, session_name: str, index: int) -> str:
    return f"{day.isoformat()}:{session_name}:signal:{index}"


def _ensure_signal_code(state: BotState, signal_key: str, config: AppConfig) -> str:
    existing = state.get_signal_code(signal_key)
    if existing:
        return existing
    code = generate_promo_code()
    state.set_signal_code(signal_key, code)
    save_state(config.state_path, state)
    return code
