from __future__ import annotations

import sys
from types import SimpleNamespace


sys.path.insert(0, "backend")

from src.core.world.personality_analyzer import analyze_session, get_profile_response
from src.core.world.personality_model.adapters.newbear_adapter import build_score_input_from_world
from src.core.world.personality_model.aggregation import TRAIT_FIELDS
from src.core.world.personality_model.hybrid_scorer import score
from src.core.world.personality_model.service import (
    analyze_personality_session,
    score_personality_events,
    update_personality_profile,
)


def fake_llm_payload():
    return {
        "estimated_persona": {
            "personality_openness": 70,
            "personality_conscientiousness": 72,
            "personality_extraversion": 68,
            "personality_agreeableness": 74,
            "personality_neuroticism": 35,
        },
        "decision_style": "balanced",
        "evidence": [{"trait": "personality_conscientiousness", "quote": "确认风险", "reason": "关注风险"}],
        "confidence": 0.7,
        "model_version": "fake-llm",
    }


def make_event(event_id: str = "EV-1", text: str = "我会先确认风险，再推动团队合作。") -> dict:
    return {
        "metadata": {
            "session_id": "S-1",
            "user_id": "U-1",
            "scene_name": "meeting",
            "scene_id": "SCENE-1",
            "task_id": "TASK-1",
        },
        "dialogue_event": {
            "event_id": event_id,
            "game_id": "S-1",
            "round_id": 1,
            "npc_role": "熊老板",
            "trigger_condition": {"scene": "meeting"},
            "npc_dialogue_script": "今天必须上线，你怎么处理？",
            "user_response_type": "FreeText",
        },
        "response_meta": {
            "event_id": event_id,
            "user_free_text_input": text,
        },
    }


def make_world() -> tuple[SimpleNamespace, SimpleNamespace]:
    user = SimpleNamespace(user_id=7, session_id="auth-session-7")
    company = SimpleNamespace(
        name="熊心壮职",
        phase="early",
        cash=5000,
        day=2,
        step=3,
        clock="09:30",
    )
    meeting = SimpleNamespace(
        meeting_id="m-1",
        title="上线评审",
        content="今天必须上线。",
        phase="discussion",
        participants=["xionglaoban"],
        transcript=[
            {"actor_id": "xionglaoban", "speaker": "熊老板", "content": "今天必须上线。"}
        ],
    )
    world = SimpleNamespace(
        session_record_id="game-session-7",
        company=company,
        active_meeting=meeting,
        active_pantry=None,
        pending_incident=None,
        user_inputs=[],
    )
    return user, world


def assert_big_five_scores(scores: dict) -> None:
    for field in TRAIT_FIELDS:
        assert field in scores
        assert scores[field] is None or 0 <= scores[field] <= 100


def test_personality_model_and_server_imports():
    import server  # noqa: F401
    import src.core.world.personality_model.service  # noqa: F401
    import src.core.world.personality_analyzer  # noqa: F401


def test_newbear_adapter_builds_score_input_from_runtime_objects():
    user, world = make_world()
    score_input = build_score_input_from_world(
        user=user,
        world=world,
        scene="meeting",
        user_text="我会先确认影响范围，然后安排修复计划。",
        response_time_ms=12000,
    )

    assert score_input.metadata.session_id == "game-session-7"
    assert score_input.metadata.user_id == "7"
    assert score_input.dialogue_event.npc_role == "熊老板"
    assert score_input.response_meta.user_free_text_input == "我会先确认影响范围，然后安排修复计划。"


def test_hybrid_scoring_without_llm_outputs_big_five(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    result = score(
        build_score_input_from_world(
            user=make_world()[0],
            world=make_world()[1],
            scene="meeting",
            user_text="我会制定计划，确认风险，并协调团队合作。",
        ),
        method="hybrid",
        use_llm=False,
    )

    data = result.to_dict()
    assert_big_five_scores(data["final_result"]["estimated_persona"])
    assert data["scoring_trace"]["llm_used"] is False


def test_service_does_not_use_llm_by_default_even_when_available(monkeypatch):
    monkeypatch.setattr("src.core.world.personality_model.hybrid_scorer.llm_fallback_reason", lambda: None)
    monkeypatch.setattr(
        "src.core.world.personality_model.hybrid_scorer.score_with_llm",
        lambda score_input: fake_llm_payload(),
    )

    result = score_personality_events([make_event()])

    assert result["llm_status"]["llm_used"] is False
    assert result["events"][0]["result"]["scoring_trace"]["llm_used"] is False
    assert result["events"][0]["result"]["scoring_trace"]["fallback_reason"] == "LLM_NOT_REQUESTED"
    assert_big_five_scores(result["events"][0]["final_result"]["estimated_persona"])


def test_service_can_use_mock_llm_when_explicitly_requested(monkeypatch):
    monkeypatch.setattr("src.core.world.personality_model.hybrid_scorer.llm_fallback_reason", lambda: None)
    monkeypatch.setattr(
        "src.core.world.personality_model.hybrid_scorer.score_with_llm",
        lambda score_input: fake_llm_payload(),
    )

    result = score_personality_events([make_event()], use_llm=True)

    assert result["llm_status"]["llm_used"] is True
    assert result["events"][0]["result"]["scoring_trace"]["llm_used"] is True
    assert_big_five_scores(result["events"][0]["final_result"]["estimated_persona"])


def test_service_falls_back_to_baseline_when_llm_unavailable(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    result = score_personality_events([make_event()])

    assert result["llm_status"]["llm_used"] is False
    assert "LLM_DISABLED" in result["llm_status"]["fallback_reasons"]
    assert result["events"][0]["scored"] is True
    assert_big_five_scores(result["events"][0]["final_result"]["estimated_persona"])


def test_service_scores_events_and_aggregates_session_profile(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    payload = {
        "events": [
            make_event("EV-1", "我会制定计划，确认风险，保证交付质量。"),
            make_event("EV-2", "我会安抚同事，协调大家一起合作。"),
        ],
        "old_profile": {field: 50 for field in TRAIT_FIELDS},
    }

    result = analyze_personality_session(payload)

    assert result["status"] == "ok"
    assert len(result["events"]) == 2
    assert result["scene_scores"]
    assert result["session_score"]["aggregation_status"] == "ok"
    assert_big_five_scores(result["session_score"]["session_score"])
    assert_big_five_scores(result["profile_update"])
    assert result["llm_status"]["llm_used"] is False


def test_score_personality_events_handles_generic_payloads(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    result = score_personality_events([make_event()])

    assert len(result["events"]) == 1
    assert result["events"][0]["scored"] is True
    assert_big_five_scores(result["events"][0]["final_result"]["estimated_persona"])


def test_profile_updater_smooths_session_score():
    old_profile = {field: 50 for field in TRAIT_FIELDS}
    session_score = {"session_score": {field: 100 for field in TRAIT_FIELDS}}

    updated = update_personality_profile(old_profile, session_score, alpha=0.2)

    assert updated["personality_openness"] == 60
    assert_big_five_scores(updated)


def test_personality_analyzer_compatibility_entrypoints(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    analyzed = analyze_session(session_id="S-compat", user_inputs=[{"message": "我会先复盘再行动。"}])
    profile = get_profile_response()

    assert analyzed["status"] == "ok"
    assert analyzed["events"][0]["scored"] is True
    assert_big_five_scores(profile["profile"])
