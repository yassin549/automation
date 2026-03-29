import logging
from datetime import date, datetime, time
from pathlib import Path

import pytest
from zoneinfo import ZoneInfo

from ghost.config import AppConfig
from ghost.sender import SessionContext, _post_pre_session, _send_once
from ghost.state import BotState


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        api_id=1,
        api_hash="hash",
        session="session",
        bot_token=None,
        channel="@channel",
        vip_channel="@vip",
        plan_path=tmp_path / "plan.json",
        state_path=tmp_path / "state.json",
        timezone="Africa/Tunis",
        result_delay_seconds=75,
        free_delay_seconds=150,
        daily_recap_time=time(18, 0),
        weekly_recap_time=time(19, 0),
        conversion_time=time(13, 0),
        auto_plan=False,
        auto_win_rate=0.9,
        example_start_balance=100,
        example_risk_per_trade=10,
        payout_ratio=0.8,
        max_late_seconds=60,
        allow_stale_plan_date=False,
    )


@pytest.mark.asyncio
async def test_send_once_does_not_mark_executed_when_send_fails(
    tmp_path, monkeypatch
) -> None:
    async def fake_try_send_message(*args, **kwargs):
        return None

    monkeypatch.setattr("ghost.sender._try_send_message", fake_try_send_message)

    state = BotState(day="2026-03-29", week="2026-W13")
    config = _config(tmp_path)

    sent = await _send_once(
        client=object(),
        config=config,
        state=state,
        logger=logging.getLogger("test"),
        action_id="test-action",
        target="@channel",
        message="hello",
        label="test",
    )

    assert sent is False
    assert state.was_executed("test-action") is False


@pytest.mark.asyncio
async def test_post_pre_session_sends_immediately_when_inside_pre_window(
    tmp_path, monkeypatch
) -> None:
    tz = ZoneInfo("Africa/Tunis")
    now = datetime(2026, 3, 29, 8, 57, tzinfo=tz)
    context = SessionContext(
        day=date(2026, 3, 29),
        name="morning",
        start_at=datetime(2026, 3, 29, 9, 0, tzinfo=tz),
        end_at=datetime(2026, 3, 29, 11, 0, tzinfo=tz),
        signals=[],
        schedule=[],
    )

    class FakeDateTime:
        @staticmethod
        def now(tzinfo):
            return now

    wait_called = False
    base_called = False
    extra_called = False
    promo_called = False

    async def fake_wait_until(*args, **kwargs):
        nonlocal wait_called
        wait_called = True

    async def fake_send_pre_session_base(*args, **kwargs):
        nonlocal base_called
        base_called = True
        return True

    async def fake_send_pre_session_extra(*args, **kwargs):
        nonlocal extra_called
        extra_called = True
        return True

    async def fake_send_trade_promo(*args, **kwargs):
        nonlocal promo_called
        promo_called = True
        return False

    async def fake_sleep_range(*args, **kwargs):
        return None

    monkeypatch.setattr("ghost.sender.datetime", FakeDateTime)
    monkeypatch.setattr("ghost.sender._wait_until", fake_wait_until)
    monkeypatch.setattr("ghost.sender._send_pre_session_base", fake_send_pre_session_base)
    monkeypatch.setattr("ghost.sender._send_pre_session_extra", fake_send_pre_session_extra)
    monkeypatch.setattr("ghost.sender._send_trade_promo", fake_send_trade_promo)
    monkeypatch.setattr("ghost.sender._sleep_range", fake_sleep_range)

    await _post_pre_session(
        client=object(),
        config=_config(tmp_path),
        context=context,
        state=BotState(day="2026-03-29", week="2026-W13"),
        logger=logging.getLogger("test"),
        tz=tz,
        vip_target="@vip",
    )

    assert wait_called is False
    assert base_called is True
    assert extra_called is True
    assert promo_called is True
