from datetime import date
import json

from zoneinfo import ZoneInfo

from ghost.plan import DEFAULT_ASSET, load_plan


def test_load_plan_defaults(tmp_path):
    plan_path = tmp_path / "plan.json"
    payload = {
        "sessions": {
            "morning": [
                {"direction": "PUT", "result": "WIN"},
                {"direction": "PUT", "result": "WIN"},
                {"direction": "PUT", "result": "LOSS"},
                {"direction": "CALL", "result": "WIN"},
                {"direction": "CALL", "result": "LOSS"},
            ],
            "evening": [
                {"direction": "CALL", "result": "WIN"},
                {"direction": "CALL", "result": "LOSS"},
                {"direction": "CALL", "result": "WIN"},
                {"direction": "CALL", "result": "WIN"},
                {"direction": "CALL", "result": "LOSS"},
            ],
        }
    }
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    plan = load_plan(
        plan_path, tz=ZoneInfo("Africa/Tunis"), today=date.today(), allow_stale_date=True
    )
    assert plan.sessions["morning"][0].asset == DEFAULT_ASSET
