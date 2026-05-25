from __future__ import annotations

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.world.personality_analyzer import (  # noqa: E402
    analyze_session,
    get_profile_response,
    get_trend,
    get_trend_response,
    update_user_profile,
)


def _session(session_id: str, openness: int, conscientiousness: int = 50) -> dict:
    return {
        "session_id": session_id,
        "big_five": {
            "openness": openness,
            "conscientiousness": conscientiousness,
            "extraversion": 50,
            "agreeableness": 50,
            "neuroticism": 50,
        },
        "decision_style": {
            "rational": openness,
            "emotional": 20,
            "assertive": 50,
            "avoidant": 10,
        },
        "behavior_evidence": [],
        "summary": f"{session_id} summary",
    }


def test_first_profile_creation() -> None:
    session_result = _session("s1", openness=72, conscientiousness=80)

    profile = update_user_profile("user-1", None, session_result)

    assert profile["user_id"] == "user-1"
    assert profile["session_count"] == 1
    assert profile["latest_session_id"] == "s1"
    assert profile["big_five"]["openness"] == 72
    assert profile["big_five"]["conscientiousness"] == 80
    assert len(profile["session_history"]) == 1


def test_multi_session_weighted_update() -> None:
    profile = update_user_profile("user-1", None, _session("s1", openness=80))

    profile = update_user_profile("user-1", profile, _session("s2", openness=40))

    assert profile["session_count"] == 2
    assert profile["big_five"]["openness"] == 60
    assert profile["decision_style"]["rational"] == 60
    assert [item["session_id"] for item in profile["session_history"]] == ["s1", "s2"]


def test_scores_are_clamped_to_0_100() -> None:
    session_result = {
        "session_id": "wild",
        "big_five": {
            "openness": -10,
            "conscientiousness": 130,
            "extraversion": 101,
            "agreeableness": -1,
            "neuroticism": 999,
        },
        "decision_style": {
            "rational": -5,
            "emotional": 140,
            "assertive": 65,
            "avoidant": 999,
        },
    }

    profile = update_user_profile("user-1", None, session_result)

    all_scores = list(profile["big_five"].values()) + list(profile["decision_style"].values())
    history_scores = list(profile["session_history"][0]["big_five"].values())
    history_scores += list(profile["session_history"][0]["decision_style"].values())

    assert all(0 <= score <= 100 for score in all_scores)
    assert all(0 <= score <= 100 for score in history_scores)
    assert profile["big_five"]["openness"] == 0
    assert profile["big_five"]["conscientiousness"] == 100


def test_trend_calculation() -> None:
    sessions = [
        _session("s1", openness=40, conscientiousness=70),
        _session("s2", openness=55, conscientiousness=60),
        _session("s3", openness=70, conscientiousness=50),
    ]

    trend = get_trend(sessions)

    assert trend["session_count"] == 3
    assert trend["latest_scores"]["openness"] == 70
    assert trend["delta"]["openness"] == 30
    assert trend["direction"]["openness"] == "up"
    assert trend["delta"]["conscientiousness"] == -20
    assert len(trend["big_five_trend"]["openness"]) == 3


def test_empty_data_fallbacks() -> None:
    trend = get_trend(None)
    profile_response = get_profile_response("user-empty", None)
    trend_response = get_trend_response("user-empty", None)

    assert trend["session_count"] == 0
    assert trend["latest_scores"] == {}
    assert profile_response["has_data"] is False
    assert profile_response["big_five"] == {}
    assert profile_response["latest_scores"] == {}
    assert profile_response["session_history"] == []
    assert profile_response["evidence_summary"]["count"] == 0
    assert profile_response["updated_at"].endswith("Z")
    assert profile_response["generated_at"].endswith("Z")
    assert profile_response["trend"]["session_count"] == 0
    assert trend_response["has_data"] is False
    assert trend_response["delta"] == {}
    assert trend_response["generated_at"].endswith("Z")


def test_analyze_session_extracts_report_and_user_input_signals() -> None:
    report = {
        "scores": {"O": 82, "C": 74, "E": 50, "A": 66, "S": 80},
        "trait_summary": "你在混乱中保持冷静，也愿意提出新方案。",
        "letter_body": "今天你先评估风险，再和团队对齐。",
        "evidence": ["提出新方案并评估风险", "安抚团队并建立共识"],
    }
    user_inputs = [
        {
            "clock": "10:00",
            "raw_text": "我先看数据和成本风险，再拍板推进新方案，和团队对齐。",
        },
        {
            "clock": "11:00",
            "action": "暂缓上线，先做用户验证",
            "behavior": ["主动协调技术和市场"],
        },
    ]

    result = analyze_session("session-1", report, user_inputs)

    assert result["session_id"] == "session-1"
    assert set(result["big_five"]) == {
        "openness",
        "conscientiousness",
        "extraversion",
        "agreeableness",
        "neuroticism",
    }
    assert result["big_five"]["openness"] > 60
    assert result["big_five"]["conscientiousness"] > 60
    assert result["big_five"]["agreeableness"] > 50
    assert result["big_five"]["neuroticism"] < 50
    assert result["decision_style"]["rational"] > result["decision_style"]["avoidant"]
    assert result["decision_style"]["assertive"] > 20
    assert result["source_counts"]["report_evidence"] == 2
    assert result["source_counts"]["user_inputs"] == 2
    assert any("数据和成本风险" in item["text"] for item in result["behavior_evidence"])
    assert "行为证据" in result["summary"]


def test_profile_response_contains_api_ready_schema_for_single_session() -> None:
    session_result = _session("s1", openness=76, conscientiousness=82)
    session_result["behavior_evidence"] = [
        {
            "source": "user_input",
            "dimension": "openness",
            "label": "开放性",
            "text": "提出新方案并主动验证。",
            "signals": ["新方案", "验证"],
        }
    ]
    profile = update_user_profile("user-1", None, session_result)

    response = get_profile_response("user-1", profile)

    assert response["user_id"] == "user-1"
    assert response["session_count"] == 1
    assert response["big_five"]["openness"] == 76
    assert response["decision_style"]["rational"] == 76
    assert response["latest_scores"]["openness"] == 76
    assert len(response["session_history"]) == 1
    assert response["session_history"][0]["evidence_count"] == 1
    assert response["evidence_summary"]["count"] == 1
    assert response["evidence_summary"]["by_dimension"]["openness"] == 1
    assert response["updated_at"].endswith("Z")
    assert response["generated_at"].endswith("Z")


def test_trend_response_contains_full_big_five_series_for_multiple_sessions() -> None:
    profile = update_user_profile("user-1", None, _session("s1", openness=40, conscientiousness=70))
    profile = update_user_profile("user-1", profile, _session("s2", openness=55, conscientiousness=60))
    profile = update_user_profile("user-1", profile, _session("s3", openness=70, conscientiousness=50))

    profile_response = get_profile_response("user-1", profile)
    trend_response = get_trend_response("user-1", profile["trend"])

    assert profile_response["session_count"] == 3
    assert profile_response["latest_scores"]["openness"] == 70
    assert len(profile_response["session_history"]) == 3
    assert trend_response["session_count"] == 3
    assert trend_response["latest_scores"]["openness"] == 70
    assert trend_response["delta"]["openness"] == 30
    assert trend_response["direction"]["openness"] == "up"
    assert trend_response["generated_at"].endswith("Z")
    for trait in (
        "openness",
        "conscientiousness",
        "extraversion",
        "agreeableness",
        "neuroticism",
    ):
        assert trait in trend_response["big_five_trend"]
        assert len(trend_response["big_five_trend"][trait]) == 3
