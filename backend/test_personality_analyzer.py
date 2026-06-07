from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.world import personality_analyzer as analyzer  # noqa: E402
from src.core.world.personality_analyzer import (  # noqa: E402
    SessionBehaviorData,
    analyze_session,
    get_profile_response,
    get_trend,
    get_trend_response,
    update_user_profile,
)


class FakeProfileStore:
    def __init__(self) -> None:
        self.rows: dict[int, dict[str, Any]] = {}

    def init_user_profile(self, user_id: int) -> dict[str, Any]:
        return self.rows.setdefault(
            user_id,
            {
                "user_id": user_id,
                "personality_data": {},
                "updated_at": "2026-05-26T00:00:00Z",
            },
        )

    def get_user_profile(self, user_id: int) -> dict[str, Any] | None:
        row = self.rows.get(user_id)
        return deepcopy(row) if row is not None else None

    def update_user_profile(self, user_id: int, personality_data: dict[str, Any]) -> dict[str, Any]:
        row = self.init_user_profile(user_id)
        existing = row.get("personality_data")
        existing_data = existing if isinstance(existing, dict) else {}
        row["personality_data"] = {**existing_data, **deepcopy(personality_data)}
        row["updated_at"] = "2026-05-26T00:00:01Z"
        return deepcopy(row)


def _install_fake_store(monkeypatch: Any) -> FakeProfileStore:
    store = FakeProfileStore()
    monkeypatch.setattr(analyzer, "_profile_store", store)
    return store


def _behavior(session_id: str, openness: int, conscientiousness: int = 50) -> SessionBehaviorData:
    return SessionBehaviorData(
        session_id=session_id,
        big_five={
            "openness": openness,
            "conscientiousness": conscientiousness,
            "extraversion": 50,
            "agreeableness": 50,
            "neuroticism": 50,
        },
        decision_style={
            "rational": openness,
            "emotional": 20,
            "assertive": 50,
            "avoidant": 10,
        },
        behavior_evidence=[],
        summary=f"{session_id} summary",
        source_counts={"report_evidence": 0, "user_inputs": 0},
    )


def test_analyze_session_returns_behavior_data_and_clamped_scores() -> None:
    report = {
        "scores": {"O": 150, "C": -10, "E": 80, "A": 65, "S": 30},
        "trait_summary": "你愿意探索新方案，也会先看数据和风险。",
        "evidence": ["提出新方案", "评估风险"],
    }
    user_inputs = [
        {"raw_text": "我先看数据和成本风险，再拍板推进。"},
        {"action": "和团队对齐后做用户验证"},
    ]

    behavior = analyze_session("session-1", report, user_inputs)

    assert isinstance(behavior, SessionBehaviorData)
    assert behavior.session_id == "session-1"
    assert set(behavior.big_five) == {
        "openness",
        "conscientiousness",
        "extraversion",
        "agreeableness",
        "neuroticism",
    }
    assert set(behavior.decision_style) == {
        "rational",
        "emotional",
        "assertive",
        "avoidant",
    }

    all_scores = list(behavior.big_five.values()) + list(behavior.decision_style.values())
    assert all(0 <= score <= 100 for score in all_scores)


def test_update_user_profile_creates_profile_for_new_user(monkeypatch: Any) -> None:
    store = _install_fake_store(monkeypatch)

    profile = update_user_profile("1001", _behavior("s1", openness=72, conscientiousness=80))

    assert profile["user_id"] == "1001"
    assert profile["session_count"] == 1
    assert profile["latest_session_id"] == "s1"
    assert profile["big_five"]["openness"] == 72
    assert profile["big_five"]["conscientiousness"] == 80
    assert len(profile["session_history"]) == 1
    assert store.get_user_profile(1001)["personality_data"]["session_count"] == 1


def test_update_user_profile_accumulates_weighted_sessions(monkeypatch: Any) -> None:
    _install_fake_store(monkeypatch)

    update_user_profile("1002", _behavior("s1", openness=80))
    profile = update_user_profile("1002", _behavior("s2", openness=40))

    assert profile["session_count"] == 2
    assert profile["big_five"]["openness"] == 60
    assert profile["decision_style"]["rational"] == 60
    assert [item["session_id"] for item in profile["session_history"]] == ["s1", "s2"]


def test_get_trend_returns_multi_session_trend(monkeypatch: Any) -> None:
    _install_fake_store(monkeypatch)

    update_user_profile("1003", _behavior("s1", openness=40, conscientiousness=70))
    update_user_profile("1003", _behavior("s2", openness=55, conscientiousness=60))
    update_user_profile("1003", _behavior("s3", openness=70, conscientiousness=50))

    trend = get_trend("1003")

    assert trend["session_count"] == 3
    assert trend["latest_scores"]["openness"] == 70
    assert trend["delta"]["openness"] == 30
    assert trend["direction"]["openness"] == "up"
    assert trend["delta"]["conscientiousness"] == -20
    assert len(trend["big_five_trend"]["openness"]) == 3


def test_profile_and_trend_responses_are_stable_without_history(monkeypatch: Any) -> None:
    _install_fake_store(monkeypatch)

    profile_response = get_profile_response("404")
    trend_response = get_trend_response("404")

    assert profile_response["user_id"] == "404"
    assert profile_response["has_data"] is False
    assert profile_response["big_five"] == {}
    assert profile_response["latest_scores"] == {}
    assert profile_response["session_history"] == []
    assert profile_response["evidence_summary"]["count"] == 0
    assert profile_response["trend"]["session_count"] == 0
    assert profile_response["generated_at"].endswith("Z")

    assert trend_response["user_id"] == "404"
    assert trend_response["has_data"] is False
    assert trend_response["session_count"] == 0
    assert trend_response["delta"] == {}
    assert trend_response["latest_scores"] == {}
    assert trend_response["generated_at"].endswith("Z")
