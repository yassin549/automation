from ghost.messages import ProfitExample, build_result_message, build_signal_message
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
    message = build_signal_message(signal)
    assert signal.direction in message
    assert signal.asset in message


def test_build_result_message_win_loss() -> None:
    signal = _sample_signal(result="WIN")
    example = ProfitExample(
        starting_balance=100,
        risk_per_trade=10,
        win_profit="8",
        loss_cost="10",
        net_profit="8",
    )
    assert "Result: WIN" in build_result_message(signal, "WIN", example)
    assert "Result: LOSS" in build_result_message(signal, "LOSS", example)
