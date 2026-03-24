from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta

from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl import functions, types
from zoneinfo import ZoneInfo

from .config import AppConfig
from .messages import (
    CHECKLIST_MESSAGE,
    CONVERSION_SCARCITY,
    CONVERSION_SOFT,
    CONVERSION_TRIAL,
    PRE_SESSION_MESSAGE,
    RULES_MESSAGE,
    ProfitExample,
    RecapStats,
    build_code_message,
    build_daily_recap_message,
    build_free_delayed_message,
    build_result_message,
    build_signal_message,
    build_vip_push_message,
    build_vip_signal_message,
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
from .state import BotState, load_state, save_state


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
        if config.vip_channel and mode in {"day", "morning", "evening"}:
            vip_target = await _resolve_vip_target(client, config.vip_channel, logger)

        if mode == "day":
            while True:
                now = datetime.now(tz)
                today = now.date()
                week_id = _week_id(today)
                state = load_state(config.state_path, today.isoformat(), week_id)

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
                        await asyncio.sleep(60)
                        continue

                await _run_day(client, config, plan, state, logger, tz, vip_target)

                if once:
                    return

                now = datetime.now(tz)
                next_day = datetime.combine(
                    now.date() + timedelta(days=1), time(0, 0), tzinfo=tz
                )
                sleep_for = max(0, (next_day - now).total_seconds())
                logger.info(
                    "Day complete. Sleeping %.0f seconds until %s.",
                    sleep_for,
                    next_day,
                )
                await asyncio.sleep(sleep_for)
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
) -> None:
    today = datetime.now(tz).date()

    if config.post_rules_on_start:
        await _maybe_post_rules(client, config, state, logger)
    if config.post_checklist_on_start:
        await _maybe_post_checklist(client, config, state)

    await _run_session(
        client, config, plan, state, logger, tz, today, "morning", vip_target
    )

    conversion_dt = datetime.combine(today, config.conversion_time, tzinfo=tz)
    evening_start = datetime.combine(today, SESSION_WINDOWS["evening"][0], tzinfo=tz)
    if conversion_dt <= evening_start:
        await _wait_until(conversion_dt, tz)
        await _maybe_post_conversion(client, config, state, logger, tz)

    await _run_session(
        client, config, plan, state, logger, tz, today, "evening", vip_target
    )

    await _post_end_of_day_actions(client, config, state, logger, tz, today)


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
) -> None:
    signals = plan.sessions[session_name]
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

    pre_id = _action_id(today, session_name, "pre")
    if not state.was_executed(pre_id):
        if datetime.now(tz) <= start_dt + timedelta(seconds=config.max_late_seconds):
            await _wait_until(start_dt, tz)
            await _send_message(client, config.channel, PRE_SESSION_MESSAGE)
            state.mark_executed(pre_id)
            state.session_loss_streak[session_name] = 0
            state.session_stopped[session_name] = False
            save_state(config.state_path, state)
        else:
            logger.warning("Skipping late pre-session post for %s.", session_name)

    for index, (signal, scheduled_at) in enumerate(zip(signals, schedule)):
        if state.session_stopped.get(session_name, False):
            logger.warning("Stopping %s session after consecutive losses.", session_name)
            break

        signal_key = _signal_key(today, session_name, index)
        if datetime.now(tz) > scheduled_at + timedelta(seconds=config.max_late_seconds):
            logger.warning("Skipping late signal %s in %s session.", index + 1, session_name)
            continue

        await _wait_until(scheduled_at, tz)

        code = _ensure_signal_code(state, signal_key, config)

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
                    build_code_message(code, vip=True),
                    logger=logger,
                )
                state.mark_executed(vip_code_id)
                save_state(config.state_path, state)

            free_id = f"{signal_key}:free"
            if not state.was_executed(free_id):
                await asyncio.sleep(config.free_delay_seconds)
                await _send_message(client, config.channel, build_free_delayed_message(signal))
                state.mark_executed(free_id)
                save_state(config.state_path, state)

            free_code_id = f"{signal_key}:free-code"
            if not state.was_executed(free_code_id):
                await _send_message(
                    client,
                    config.channel,
                    build_code_message(code, vip=False),
                    logger=logger,
                )
                state.mark_executed(free_code_id)
                save_state(config.state_path, state)

            if state.get_signal_sent_at(signal_key) is None:
                state.set_signal_sent_at(signal_key, datetime.now(tz))
                save_state(config.state_path, state)
        else:
            free_id = f"{signal_key}:free"
            if not state.was_executed(free_id):
                await _send_message(client, config.channel, build_signal_message(signal))
                state.mark_executed(free_id)
                save_state(config.state_path, state)

            free_code_id = f"{signal_key}:free-code"
            if not state.was_executed(free_code_id):
                await _send_message(
                    client,
                    config.channel,
                    build_code_message(code, vip=False),
                    logger=logger,
                )
                state.mark_executed(free_code_id)
                save_state(config.state_path, state)

            if state.get_signal_sent_at(signal_key) is None:
                state.set_signal_sent_at(signal_key, datetime.now(tz))
                save_state(config.state_path, state)

        result_id = f"{signal_key}:result"
        if not state.was_executed(result_id):
            await _wait_for_result(state, signal_key, scheduled_at, config, tz)
            await _send_message(client, config.channel, build_result_message(signal, signal.result))
            state.mark_executed(result_id)
            _update_stats_after_result(state, session_name, signal.result)
            await _maybe_post_vip_push(client, config, state, logger)
            save_state(config.state_path, state)


async def _wait_for_result(
    state: BotState,
    signal_key: str,
    scheduled_at: datetime,
    config: AppConfig,
    tz: ZoneInfo,
) -> None:
    sent_at = state.get_signal_sent_at(signal_key) or scheduled_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=tz)
    result_at = sent_at + timedelta(seconds=config.result_delay_seconds)
    await _wait_until(result_at, tz)


async def _maybe_post_rules(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
) -> None:
    today = state.day
    action_id = f"{today}:rules"
    if state.was_executed(action_id):
        return
    message = await _send_message(client, config.channel, RULES_MESSAGE)
    if config.pin_rules:
        try:
            await client.pin_message(config.channel, message, notify=False)
        except Exception:
            logger.exception("Failed to pin rules message")
    state.mark_executed(action_id)
    save_state(config.state_path, state)


async def _maybe_post_checklist(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
) -> None:
    action_id = f"{state.day}:checklist"
    if state.was_executed(action_id):
        return
    await _send_message(client, config.channel, CHECKLIST_MESSAGE)
    state.mark_executed(action_id)
    save_state(config.state_path, state)


async def _maybe_post_vip_push(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
) -> None:
    if state.win_streak < 2 or state.vip_push_posted_for_streak:
        return

    action_id = f"{state.day}:vip-push:{state.win_streak}"
    if state.was_executed(action_id):
        return

    await _send_message(client, config.channel, build_vip_push_message())
    state.mark_executed(action_id)
    state.vip_push_posted_for_streak = True
    save_state(config.state_path, state)
    logger.info("VIP push sent after win streak.")


async def _maybe_post_conversion(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
) -> None:
    if state.conversion_posted:
        return

    now = datetime.now(tz)
    conversion_dt = datetime.combine(now.date(), config.conversion_time, tzinfo=tz)
    if now < conversion_dt:
        return

    action_id = f"{state.day}:conversion"
    if state.was_executed(action_id):
        state.conversion_posted = True
        return

    message = _conversion_message_for_day(now.date())
    await _send_message(client, config.channel, message)
    state.mark_executed(action_id)
    state.conversion_posted = True
    save_state(config.state_path, state)
    logger.info("Conversion post sent.")


async def _maybe_post_daily_recap(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
) -> None:
    action_id = f"{state.day}:daily-recap"
    if state.was_executed(action_id):
        return

    stats = RecapStats(total=state.daily.total, wins=state.daily.wins, losses=state.daily.losses)
    example = _profit_example(
        stats,
        config.example_start_balance,
        config.example_risk_per_trade,
        config.payout_ratio,
    )
    await _send_message(client, config.channel, build_daily_recap_message(stats, example))
    state.mark_executed(action_id)
    save_state(config.state_path, state)
    logger.info("Daily recap sent.")


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

    stats = RecapStats(total=state.weekly.total, wins=state.weekly.wins, losses=state.weekly.losses)
    examples = _weekly_examples(config, stats)
    await _send_message(client, config.channel, build_weekly_recap_message(stats, examples))
    state.mark_executed(action_id)
    save_state(config.state_path, state)
    logger.info("Weekly recap sent.")


async def _post_end_of_day_actions(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
    today: date,
) -> None:
    actions: list[tuple[datetime, str]] = [
        (datetime.combine(today, config.conversion_time, tzinfo=tz), "conversion"),
        (datetime.combine(today, config.daily_recap_time, tzinfo=tz), "daily"),
    ]
    if today.weekday() == 6:
        actions.append((datetime.combine(today, config.weekly_recap_time, tzinfo=tz), "weekly"))

    actions.sort(key=lambda item: item[0])
    for scheduled_at, name in actions:
        await _wait_until(scheduled_at, tz)
        if name == "conversion":
            await _maybe_post_conversion(client, config, state, logger, tz)
        elif name == "daily":
            await _maybe_post_daily_recap(client, config, state, logger)
        else:
            await _maybe_post_weekly_recap(client, config, state, logger, today)


def _weekly_examples(config: AppConfig, stats: RecapStats) -> list[ProfitExample]:
    examples: list[ProfitExample] = []
    risk_percent = config.example_risk_per_trade / config.example_start_balance
    for starting_balance in (100, 500):
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
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}"


def _update_stats_after_result(state: BotState, session_name: str, result: str) -> None:
    state.daily.record(result)
    state.weekly.record(result)
    if result.upper() == "WIN":
        state.win_streak += 1
        state.session_loss_streak[session_name] = 0
    else:
        state.win_streak = 0
        state.vip_push_posted_for_streak = False
        state.session_loss_streak[session_name] = state.session_loss_streak.get(session_name, 0) + 1
        if state.session_loss_streak[session_name] >= 2:
            state.session_stopped[session_name] = True


async def _wait_until(target: datetime, tz: ZoneInfo) -> None:
    now = datetime.now(tz)
    if target <= now:
        return
    await asyncio.sleep((target - now).total_seconds())


async def _send_message(client: TelegramClient, channel: object, message: str):
    return await client.send_message(channel, message)


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

        if config.post_rules_on_start:
            await _maybe_post_rules(client, config, state, logger)
        if config.post_checklist_on_start:
            await _maybe_post_checklist(client, config, state)

        await _run_session(
            client, config, plan, state, logger, tz, today, mode, vip_target
        )
        return

    if mode == "recap":
        await _post_actions_if_due(client, config, state, logger, tz, today)
        return

    raise RuntimeError(f"Unknown mode: {mode}")


async def _post_actions_if_due(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
    today: date,
) -> None:
    now = datetime.now(tz)
    conversion_dt = datetime.combine(today, config.conversion_time, tzinfo=tz)
    daily_dt = datetime.combine(today, config.daily_recap_time, tzinfo=tz)
    weekly_dt = datetime.combine(today, config.weekly_recap_time, tzinfo=tz)

    if now >= conversion_dt:
        await _maybe_post_conversion(client, config, state, logger, tz)
    if now >= daily_dt:
        await _maybe_post_daily_recap(client, config, state, logger)
    if today.weekday() == 6 and now >= weekly_dt:
        await _maybe_post_weekly_recap(client, config, state, logger, today)


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
