from __future__ import annotations

import asyncio
import logging
import random
import re
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
    RecapStats,
    build_code_intro,
    build_code_value,
    build_final_push,
    build_pre_session_base,
    build_pre_session_extra,
    build_result_message,
    build_session_recap_channel,
    build_session_recap_vip,
    build_signal_details,
    build_trade_promo_message,
)
from .plan import (
    DayPlan,
    PlanError,
    SESSION_WINDOWS,
    SignalPlan,
    generate_plan,
    load_plan,
    schedule_signals,
)
from .promo import generate_promo_code
from .proof import format_profit_text, load_proof_dir, render_proof_image
from .state import BotState, Stats, load_state, save_state


@dataclass(frozen=True)
class FlowTimings:
    pre_session_lead: timedelta
    pre_extra_delay_range: tuple[int, int]
    pre_promo_delay_range: tuple[int, int]
    promo_to_signal_delay_range: tuple[int, int]


FLOW = FlowTimings(
    pre_session_lead=timedelta(minutes=5),
    pre_extra_delay_range=(3, 5),
    pre_promo_delay_range=(10, 20),
    promo_to_signal_delay_range=(10, 20),
)

_EXPIRY_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>minutes?|mins?|m|seconds?|secs?|s)",
    re.IGNORECASE,
)

_RNG = random.SystemRandom()


@dataclass(frozen=True)
class SessionContext:
    day: date
    name: str
    start_at: datetime
    end_at: datetime
    signals: list[SignalPlan]
    schedule: list[datetime]


@dataclass(frozen=True)
class SignalContext:
    session: SessionContext
    index: int
    signal: SignalPlan
    scheduled_at: datetime


@dataclass(frozen=True)
class ProfitExample:
    starting_balance: int
    risk_per_trade: int
    win_profit: str
    loss_cost: str
    net_profit: str


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
        await _ensure_authorized(client, config, logger)

        vip_target = None
        if config.vip_channel and mode in {"day", "morning", "evening", "all"}:
            vip_target = await _resolve_vip_target(client, config.vip_channel, logger)

        if mode in {"day", "all"}:
            while True:
                now = datetime.now(tz)
                today = now.date()
                week_id = _week_id(today)
                state = load_state(config.state_path, today.isoformat(), week_id)

                if config.auto_plan:
                    plan = generate_plan(today, config.auto_win_rate)
                else:
                    plan = await _load_plan_or_wait(
                        config, logger, tz, today, once=once
                    )
                    if plan is None:
                        if once:
                            return
                        continue

                await _run_day(client, config, plan, state, logger, tz, vip_target)

                if once:
                    return

                now = datetime.now(tz)
                next_day = datetime.combine(
                    now.date() + timedelta(days=1), time(0, 0), tzinfo=tz
                )
                logger.info("Day complete. Sleeping until %s.", next_day)
                await _wait_until(next_day, tz)
        elif mode in {"morning", "evening"}:
            await _run_mode_once(client, config, logger, tz, vip_target, mode)
        elif mode == "recap":
            logger.info("Recap mode is disabled in the current posting structure.")
            return
        else:
            raise RuntimeError(f"Unknown mode: {mode}")
    finally:
        if client.is_connected():
            await client.disconnect()


async def _ensure_authorized(
    client: TelegramClient,
    config: AppConfig,
    logger: logging.Logger,
) -> None:
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


async def _load_plan_or_wait(
    config: AppConfig,
    logger: logging.Logger,
    tz: ZoneInfo,
    today: date,
    once: bool,
) -> DayPlan | None:
    try:
        return load_plan(
            config.plan_path,
            tz=tz,
            today=today,
            allow_stale_date=config.allow_stale_plan_date,
        )
    except PlanError as exc:
        logger.error("Plan error: %s", exc)
        if once:
            return None
        await _wait_until(datetime.now(tz) + timedelta(seconds=60), tz)
        return None


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

    morning = _build_session_context(plan, tz, today, "morning")
    await _run_session(client, config, morning, state, logger, tz, vip_target)

    evening = _build_session_context(plan, tz, today, "evening")
    await _run_session(client, config, evening, state, logger, tz, vip_target)


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

    context = _build_session_context(plan, tz, today, mode)
    await _run_session(client, config, context, state, logger, tz, vip_target)


def _build_session_context(
    plan: DayPlan, tz: ZoneInfo, today: date, session_name: str
) -> SessionContext:
    signals = plan.sessions[session_name]
    schedule = schedule_signals(session_name, signals, today, tz)
    start_time, end_time = SESSION_WINDOWS[session_name]
    start_at = datetime.combine(today, start_time, tzinfo=tz)
    end_at = datetime.combine(today, end_time, tzinfo=tz)
    return SessionContext(
        day=today,
        name=session_name,
        start_at=start_at,
        end_at=end_at,
        signals=signals,
        schedule=schedule,
    )


async def _run_session(
    client: TelegramClient,
    config: AppConfig,
    context: SessionContext,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
    vip_target: object | None,
) -> None:
    if _is_too_late(context.end_at, config.max_late_seconds, tz):
        logger.info("Skipping %s session (window already closed).", context.name)
        return

    await _post_pre_session(
        client,
        config,
        context,
        state,
        logger,
        tz,
        vip_target,
    )

    for index, (signal, scheduled_at) in enumerate(
        zip(context.signals, context.schedule)
    ):
        signal_ctx = SignalContext(
            session=context,
            index=index,
            signal=signal,
            scheduled_at=scheduled_at,
        )
        if _is_too_late(signal_ctx.scheduled_at, config.max_late_seconds, tz):
            logger.warning(
                "Skipping late signal %s in %s session.",
                index + 1,
                context.name,
            )
            continue

        await _wait_until(signal_ctx.scheduled_at, tz)
        await _post_signal(
            client,
            config,
            signal_ctx,
            state,
            logger,
            tz,
            vip_target,
        )

    await _post_session_recap(client, config, state, logger, context.name, vip_target)
    await _post_final_push(client, config, state, logger, context.name)


async def _post_pre_session(
    client: TelegramClient,
    config: AppConfig,
    context: SessionContext,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
    vip_target: object | None,
) -> None:
    pre_time = context.start_at - FLOW.pre_session_lead
    if _is_too_late(pre_time, config.max_late_seconds, tz):
        logger.warning("Skipping late pre-session post for %s.", context.name)
        return

    await _wait_until(pre_time, tz)

    base_sent = False
    base_sent |= await _send_pre_session_base(
        client, config, state, logger, context, vip_target
    )
    if base_sent:
        await _sleep_range(*FLOW.pre_extra_delay_range)

    extra_sent = False
    extra_sent |= await _send_pre_session_extra(
        client, config, state, logger, context, vip_target
    )
    if extra_sent:
        await _sleep_range(*FLOW.pre_promo_delay_range)

    promo_sent = await _send_trade_promo(client, config, state, logger, context)
    if promo_sent:
        await _sleep_range(*FLOW.promo_to_signal_delay_range)


async def _send_pre_session_base(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    context: SessionContext,
    vip_target: object | None,
) -> bool:
    sent = False
    channel_id = _action_id(context.day, context.name, "pre-base-channel")
    sent |= await _send_once(
        client,
        config,
        state,
        logger,
        channel_id,
        config.channel,
        build_pre_session_base(),
        "pre-session base",
    )

    if vip_target is not None:
        vip_id = _action_id(context.day, context.name, "pre-base-vip")
        sent |= await _send_once(
            client,
            config,
            state,
            logger,
            vip_id,
            vip_target,
            build_pre_session_base(),
            "pre-session base vip",
        )

    return sent


async def _send_pre_session_extra(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    context: SessionContext,
    vip_target: object | None,
) -> bool:
    sent = False
    channel_id = _action_id(context.day, context.name, "pre-extra-channel")
    sent |= await _send_once(
        client,
        config,
        state,
        logger,
        channel_id,
        config.channel,
        build_pre_session_extra(AUDIENCE_CHANNEL),
        "pre-session extra",
    )

    if vip_target is not None:
        vip_id = _action_id(context.day, context.name, "pre-extra-vip")
        sent |= await _send_once(
            client,
            config,
            state,
            logger,
            vip_id,
            vip_target,
            build_pre_session_extra(AUDIENCE_VIP),
            "pre-session extra vip",
        )

    return sent


async def _send_trade_promo(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    context: SessionContext,
) -> bool:
    promo_id = _action_id(context.day, context.name, "promo")
    return await _send_once(
        client,
        config,
        state,
        logger,
        promo_id,
        config.channel,
        build_trade_promo_message(),
        "trade promo",
    )


async def _post_signal(
    client: TelegramClient,
    config: AppConfig,
    context: SignalContext,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
    vip_target: object | None,
) -> None:
    signal_key = _signal_key(context.session.day, context.session.name, context.index)

    if vip_target is not None:
        code = _ensure_signal_code(state, signal_key, config)
        await _send_signal_to_vip(
            client,
            config,
            state,
            logger,
            signal_key,
            context.signal,
            code,
            vip_target,
        )

        if not state.was_executed(f"{signal_key}:channel"):
            await _sleep_seconds(config.free_delay_seconds)

    await _send_signal_to_channel(
        client,
        config,
        state,
        logger,
        signal_key,
        context.signal,
        tz,
    )

    await _post_result_and_proof(
        client,
        config,
        context,
        state,
        logger,
        tz,
        vip_target,
    )


async def _send_signal_to_vip(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    signal_key: str,
    signal: SignalPlan,
    code: str,
    vip_target: object,
) -> None:
    await _send_step(
        client,
        vip_target,
        state,
        config,
        logger,
        f"{signal_key}:vip-details",
        build_signal_details(signal),
    )
    await _send_step(
        client,
        vip_target,
        state,
        config,
        logger,
        f"{signal_key}:vip-code-intro",
        build_code_intro(),
    )
    await _send_step(
        client,
        vip_target,
        state,
        config,
        logger,
        f"{signal_key}:vip-code",
        build_code_value(code),
    )


async def _send_signal_to_channel(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    signal_key: str,
    signal: SignalPlan,
    tz: ZoneInfo,
) -> None:
    channel_id = f"{signal_key}:channel"
    if not state.was_executed(channel_id):
        anchor_time = datetime.now(tz)
        state.set_signal_sent_at(signal_key, anchor_time)
        await _try_send_message(
            client,
            config.channel,
            build_signal_details(signal),
            logger,
            "channel signal",
        )
        state.mark_executed(channel_id)
        save_state(config.state_path, state)
    elif state.get_signal_sent_at(signal_key) is None:
        state.set_signal_sent_at(signal_key, datetime.now(tz))
        save_state(config.state_path, state)


async def _post_result_and_proof(
    client: TelegramClient,
    config: AppConfig,
    context: SignalContext,
    state: BotState,
    logger: logging.Logger,
    tz: ZoneInfo,
    vip_target: object | None,
) -> None:
    signal_key = _signal_key(context.session.day, context.session.name, context.index)

    result_id = f"{signal_key}:result"
    if not state.was_executed(result_id):
        expiry_seconds = _expiry_delay_seconds(context.signal.expiry, config)
        await _wait_for_result(state, signal_key, context.scheduled_at, expiry_seconds, tz)

        result_message = build_result_message(context.signal.result)
        if vip_target is not None:
            await _try_send_message(
                client, vip_target, result_message, logger, "vip result"
            )
        await _try_send_message(
            client, config.channel, result_message, logger, "channel result"
        )

        state.mark_executed(result_id)
        _update_stats_after_result(state, context.session.name, context.signal.result)
        save_state(config.state_path, state)

    proof_id = f"{signal_key}:proof"
    if not state.was_executed(proof_id):
        example_stats = RecapStats(
            total=1,
            wins=1 if context.signal.result.upper() == "WIN" else 0,
            losses=1 if context.signal.result.upper() == "LOSS" else 0,
        )
        example = _profit_example(
            example_stats,
            config.example_start_balance,
            config.example_risk_per_trade,
            config.payout_ratio,
        )
        await _maybe_send_proof(
            client,
            config,
            state,
            signal_key,
            context.scheduled_at,
            context.signal.result,
            example,
            tz,
            vip_target,
        )
        state.mark_executed(proof_id)
        save_state(config.state_path, state)


async def _post_session_recap(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    session_name: str,
    vip_target: object | None,
) -> None:
    action_id = _action_id(date.fromisoformat(state.day), session_name, "session-recap")
    if state.was_executed(action_id):
        return

    stats = state.session_stats.get(session_name)
    if not stats or stats.total <= 0:
        return

    recap = RecapStats(total=stats.total, wins=stats.wins, losses=stats.losses)
    if vip_target is not None:
        await _try_send_message(
            client,
            vip_target,
            build_session_recap_vip(recap),
            logger,
            "vip session recap",
        )
    await _try_send_message(
        client,
        config.channel,
        build_session_recap_channel(recap),
        logger,
        "channel session recap",
    )

    state.mark_executed(action_id)
    save_state(config.state_path, state)


async def _post_final_push(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    session_name: str,
) -> None:
    action_id = _action_id(date.fromisoformat(state.day), session_name, "final-push")
    if state.was_executed(action_id):
        return

    await _try_send_message(
        client,
        config.channel,
        build_final_push(),
        logger,
        "final push",
    )
    state.mark_executed(action_id)
    save_state(config.state_path, state)


async def _wait_for_result(
    state: BotState,
    signal_key: str,
    scheduled_at: datetime,
    delay_seconds: float,
    tz: ZoneInfo,
) -> None:
    sent_at = state.get_signal_sent_at(signal_key) or scheduled_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=tz)
    result_at = sent_at + timedelta(seconds=delay_seconds)
    await _wait_until(result_at, tz)


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
        if vip_target is not None:
            await _try_send_file(client, vip_target, proof_path, "vip proof")
        await _try_send_file(client, config.channel, proof_path, "channel proof")
    finally:
        try:
            proof_path.unlink()
        except FileNotFoundError:
            pass


def _expiry_delay_seconds(expiry: str, config: AppConfig) -> float:
    parsed = _parse_expiry_seconds(expiry)
    if parsed is None:
        return max(0.0, config.result_delay_seconds)
    return max(0.0, parsed)


def _parse_expiry_seconds(expiry: str) -> float | None:
    if not expiry:
        return None
    match = _EXPIRY_RE.search(expiry.strip())
    if not match:
        return None
    value = float(match.group("value"))
    unit = match.group("unit").lower()
    if unit.startswith("m"):
        return value * 60.0
    return value


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
) -> None:
    state.daily.record(result)
    state.weekly.record(result)
    state.session_stats.setdefault(session_name, Stats()).record(result)


async def _sleep_seconds(delay_seconds: float) -> None:
    if delay_seconds <= 0:
        return
    await asyncio.sleep(delay_seconds)


async def _sleep_range(min_seconds: int, max_seconds: int) -> None:
    if max_seconds <= 0:
        return
    delay = _RNG.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def _wait_until(target: datetime, tz: ZoneInfo) -> None:
    while True:
        now = datetime.now(tz)
        if target <= now:
            return
        sleep_for = min(30.0, (target - now).total_seconds())
        await asyncio.sleep(sleep_for)


def _is_too_late(target: datetime, max_late_seconds: float, tz: ZoneInfo) -> bool:
    return datetime.now(tz) > target + timedelta(seconds=max_late_seconds)


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


async def _try_send_message(
    client: TelegramClient,
    channel: object,
    message: str,
    logger: logging.Logger,
    label: str,
):
    try:
        return await _send_message(client, channel, message)
    except Exception as exc:
        logger.warning("Failed to send %s: %s", label, exc)
        return None


async def _try_send_file(
    client: TelegramClient,
    channel: object,
    path: Path,
    label: str,
):
    try:
        await client.send_file(channel, path)
    except Exception:
        return None
    return None


async def _send_once(
    client: TelegramClient,
    config: AppConfig,
    state: BotState,
    logger: logging.Logger,
    action_id: str,
    target: object,
    message: str,
    label: str,
) -> bool:
    if state.was_executed(action_id):
        return False
    await _try_send_message(client, target, message, logger, label)
    state.mark_executed(action_id)
    save_state(config.state_path, state)
    return True


async def _send_step(
    client: TelegramClient,
    target: object,
    state: BotState,
    config: AppConfig,
    logger: logging.Logger,
    action_id: str,
    message: str,
) -> None:
    if state.was_executed(action_id):
        return
    await _try_send_message(client, target, message, logger, action_id)
    state.mark_executed(action_id)
    save_state(config.state_path, state)


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
