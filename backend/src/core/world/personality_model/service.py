from __future__ import annotations

from typing import Any

from .adapters.common import build_score_input_from_payload
from .adapters.newbear_adapter import build_score_input_from_world
from .aggregation import TRAIT_FIELDS, aggregate_scene_scores, aggregate_session_scores
from .hybrid_scorer import score
from .profile_updater import initial_profile, update_profile
from .schemas import ScoreInput, ScoreResult


API_VERSION = "personality_model_v04_newbear"


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def _short_traits(scores: dict[str, Any] | None) -> dict[str, float | None]:
    scores = scores or {}
    return {
        "openness": _round_or_none(scores.get("personality_openness")),
        "conscientiousness": _round_or_none(scores.get("personality_conscientiousness")),
        "extraversion": _round_or_none(scores.get("personality_extraversion")),
        "agreeableness": _round_or_none(scores.get("personality_agreeableness")),
        "neuroticism": _round_or_none(scores.get("personality_neuroticism")),
    }


def _round_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _score_input_from_event(event: Any) -> ScoreInput:
    if isinstance(event, ScoreInput):
        return event
    if not isinstance(event, dict):
        raise TypeError("event must be a ScoreInput or dict")

    return build_score_input_from_payload(
        metadata=dict(event.get("metadata") or {}),
        dialogue_event=dict(event.get("dialogue_event") or {}),
        response_meta=dict(event.get("response_meta") or {}),
    )


def _event_record(result: ScoreResult, source_event: Any) -> dict[str, Any]:
    result_dict = result.to_dict()
    metadata = result.metadata.to_dict()
    dialogue_event = result.dialogue_event.to_dict()
    source = source_event if isinstance(source_event, dict) else {}
    final_result = result_dict.get("final_result") or {
        "estimated_persona": result_dict.get("estimated_persona"),
        "feedback": result_dict.get("feedback"),
        "decision_style": result_dict.get("decision_style"),
        "evidence": result_dict.get("evidence"),
        "confidence": result_dict.get("confidence"),
        "scoring_method": result_dict.get("scoring_method"),
    }

    return {
        "session_id": metadata.get("session_id") or dialogue_event.get("game_id"),
        "user_id": metadata.get("user_id"),
        "game_id": dialogue_event.get("game_id"),
        "round_id": dialogue_event.get("round_id"),
        "event_id": dialogue_event.get("event_id"),
        "scene_id": metadata.get("scene_id") or metadata.get("scene_name") or "default_scene",
        "scene_name": metadata.get("scene_name"),
        "task_id": metadata.get("task_id") or dialogue_event.get("round_id"),
        "target_traits": metadata.get("target_traits"),
        "user_response_type": dialogue_event.get("user_response_type"),
        "is_demo": _truthy(metadata.get("is_demo") or source.get("is_demo"), False),
        "is_valid_event": _truthy(metadata.get("is_valid_event"), True),
        "quality_flags": metadata.get("quality_flags") or [],
        "scored": True,
        "confidence": result.confidence,
        "evidence": result_dict.get("evidence") or [],
        "final_result": final_result,
        "result": result_dict,
    }


def _failed_event_record(event: Any, error: Exception) -> dict[str, Any]:
    source = event if isinstance(event, dict) else {}
    metadata = source.get("metadata") or {}
    dialogue_event = source.get("dialogue_event") or {}
    return {
        "session_id": metadata.get("session_id") or dialogue_event.get("game_id"),
        "user_id": metadata.get("user_id"),
        "event_id": dialogue_event.get("event_id"),
        "scene_id": metadata.get("scene_id") or metadata.get("scene_name") or "default_scene",
        "scene_name": metadata.get("scene_name"),
        "task_id": metadata.get("task_id") or dialogue_event.get("round_id"),
        "is_demo": _truthy(metadata.get("is_demo"), False),
        "is_valid_event": False,
        "quality_flags": ["scoring_error"],
        "scored": False,
        "confidence": 0,
        "evidence": [],
        "final_result": None,
        "error": str(error),
    }


def _llm_status(records: list[dict[str, Any]]) -> dict[str, Any]:
    traces = []
    for record in records:
        result = record.get("result") or {}
        trace = result.get("scoring_trace")
        if isinstance(trace, dict):
            traces.append(trace)

    return {
        "llm_used": any(trace.get("llm_used") is True for trace in traces),
        "llm_enabled": any(trace.get("llm_enabled") is True for trace in traces),
        "fallback_reasons": sorted(
            {
                str(trace.get("fallback_reason"))
                for trace in traces
                if trace.get("fallback_reason")
            }
        ),
    }


def score_personality_events(
    events: list[Any],
    method: str = "hybrid",
    use_llm: bool = False,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    for event in events:
        try:
            score_input = _score_input_from_event(event)
            result = score(score_input, method=method, use_llm=use_llm)
            records.append(_event_record(result, event))
        except Exception as exc:  # keep the game backend from failing on one bad event
            records.append(_failed_event_record(event, exc))

    return {
        "api_version": API_VERSION,
        "events": records,
        "llm_status": _llm_status(records),
    }


def _events_from_runtime_payload(payload: dict[str, Any]) -> list[ScoreInput]:
    score_input = build_score_input_from_world(
        user=payload.get("user"),
        world=payload.get("world"),
        scene=str(payload.get("scene") or "world"),
        user_text=str(payload.get("user_text") or payload.get("message") or ""),
        selected_option=payload.get("selected_option"),
        response_time_ms=payload.get("response_time_ms"),
    )
    return [score_input]


def analyze_personality_session(
    payload: dict[str, Any],
    method: str = "hybrid",
    use_llm: bool = False,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}

    if payload.get("events") is not None:
        events = list(payload.get("events") or [])
    elif payload.get("user") is not None and payload.get("world") is not None:
        events = _events_from_runtime_payload(payload)
    else:
        return {
            "api_version": API_VERSION,
            "events": [],
            "scene_scores": [],
            "session_score": None,
            "profile_update": None,
            "llm_status": {"llm_used": False, "llm_enabled": False, "fallback_reasons": ["NO_INPUT"]},
            "status": "no_input",
        }

    scored = score_personality_events(events, method=method, use_llm=use_llm)
    records = scored["events"]
    scene_scores = aggregate_scene_scores(records)
    session_scores = aggregate_session_scores(records)
    session_score = session_scores[0] if session_scores else None

    old_profile = payload.get("old_profile")
    if old_profile is None:
        old_profile = payload.get("profile")
    profile_update = None
    if session_score is not None:
        profile_update = update_personality_profile(
            old_profile,
            session_score,
            alpha=float(payload.get("alpha", 0.2)),
        )

    return {
        "api_version": API_VERSION,
        "events": records,
        "scene_scores": scene_scores,
        "session_score": session_score,
        "profile_update": profile_update,
        "profile_response": get_personality_profile_response(profile_update, session_score),
        "llm_status": scored["llm_status"],
        "status": "ok" if records else "no_events",
    }


def update_personality_profile(
    old_profile: dict[str, Any] | None,
    session_score: dict[str, Any] | None,
    alpha: float = 0.2,
) -> dict[str, float]:
    if session_score is None:
        return update_profile(old_profile or initial_profile(), {}, alpha=alpha)
    return update_profile(old_profile, session_score, alpha=alpha)


def get_personality_profile_response(
    profile: dict[str, Any] | None,
    session_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = profile or initial_profile()
    session_score = None
    if isinstance(session_result, dict):
        session_score = session_result.get("session_score") or session_result

    return {
        "api_version": API_VERSION,
        "profile": {field: _round_or_none(profile.get(field)) for field in TRAIT_FIELDS},
        "profile_short": _short_traits(profile),
        "latest_session_score": {
            field: _round_or_none((session_score or {}).get(field))
            for field in TRAIT_FIELDS
        },
        "latest_session_short": _short_traits(session_score),
        "llm_note": "LLM scoring is enabled by default; rule scoring remains the baseline fallback when LLM is unavailable.",
    }
