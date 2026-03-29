from ghost.state import BotState


def test_update_session_win_streak_tracks_consecutive_wins() -> None:
    state = BotState(day="2026-03-29", week="2026-W13")

    assert state.update_session_win_streak("morning", "WIN") == 1
    assert state.update_session_win_streak("morning", "WIN") == 2
    assert state.update_session_win_streak("morning", "LOSS") == 0
    assert state.update_session_win_streak("morning", "WIN") == 1
    assert state.session_win_streak["morning"] == 1
    assert state.session_best_win_streak["morning"] == 2
    assert state.session_best_loss_streak["morning"] == 1


def test_update_session_win_streak_is_scoped_per_session() -> None:
    state = BotState(day="2026-03-29", week="2026-W13")

    state.update_session_win_streak("morning", "WIN")
    state.update_session_win_streak("morning", "WIN")
    state.update_session_win_streak("evening", "WIN")

    assert state.session_win_streak["morning"] == 2
    assert state.session_win_streak["evening"] == 1
