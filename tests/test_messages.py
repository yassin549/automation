from ghost.messages import build_result_message, build_signal_details
from ghost.plan import (
    DEFAULT_ASSET,
    DEFAULT_CONFIDENCE,
    DEFAULT_ENTRY,
    DEFAULT_ENTRY_WINDOW,
    DEFAULT_EXPIRY,
    DEFAULT_INSIGHT,
    DEFAULT_MARKET_CONDITION,
    SignalPlan,
)

from ghost.messages import build_win_streak_push
from ghost.messages import RecapStats, build_session_recap_channel


def _sample_signal(result: str = "WIN") -> SignalPlan:
    return SignalPlan(
        asset=DEFAULT_ASSET,
        direction="PUT",
        expiry=DEFAULT_EXPIRY,
        entry_window=DEFAULT_ENTRY_WINDOW,
        entry=DEFAULT_ENTRY,
        confidence=DEFAULT_CONFIDENCE,
        market_condition=DEFAULT_MARKET_CONDITION,
        insight=DEFAULT_INSIGHT,
        result=result,
        signal_time=None,
    )


def test_build_signal_message_contains_direction() -> None:
    signal = _sample_signal()
    message = build_signal_details(signal)
    assert signal.direction in message
    assert signal.asset in message


def test_build_result_message_win_loss() -> None:
    win_message = build_result_message("WIN")
    loss_message = build_result_message("LOSS")
    assert "✅ WIN" in win_message
    assert "❌ LOSS" in loss_message


def test_build_win_streak_push_uses_current_streak() -> None:
    message = build_win_streak_push(4)
    assert "🔥 4 wins back-to-back" in message
    assert "💎 VIP got in earlier on every one." in message
    assert "⏳ Free signals come later for a reason." in message


def test_build_session_recap_channel_includes_session_streaks() -> None:
    message = build_session_recap_channel(
        "morning",
        RecapStats(
            total=5,
            wins=4,
            losses=1,
            best_win_streak=3,
            best_loss_streak=1,
        ),
    )
    assert "📊 Morning recap:" in message
    assert "Signals: 5" in message
    assert "Win rate: 80%" in message
    assert "Best win streak: 3" in message
    assert "Worst loss streak: 1" in message
