from __future__ import annotations

from typing import Any

from .personality_model.service import (
    analyze_personality_session,
    get_personality_profile_response,
    score_personality_events,
    update_personality_profile,
)


def analyze_session(
    session_id: str | None = None,
    report: dict[str, Any] | None = None,
    user_inputs: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    events = kwargs.pop("events", None)
    if events is None and user_inputs:
        events = [
            {
                "metadata": {
                    "session_id": session_id or item.get("session_id"),
                    "user_id": item.get("user_id"),
                    "scene_name": item.get("scene") or item.get("scene_name") or "world",
                },
                "dialogue_event": {
                    "event_id": item.get("event_id") or f"{session_id or 'session'}:{index}",
                    "game_id": session_id or item.get("game_id") or "unknown_game",
                    "round_id": index,
                    "npc_role": item.get("npc_role") or "系统",
                    "trigger_condition": item.get("trigger_condition") or report or {},
                    "npc_dialogue_script": item.get("prompt") or item.get("npc_dialogue_script") or "",
                    "user_response_type": item.get("user_response_type") or "FreeText",
                },
                "response_meta": {
                    "event_id": item.get("event_id") or f"{session_id or 'session'}:{index}",
                    "user_free_text_input": item.get("message") or item.get("text") or item.get("user_text") or "",
                    "user_selected_option": item.get("selected_option"),
                    "response_time_ms": item.get("response_time_ms"),
                },
            }
            for index, item in enumerate(user_inputs, start=1)
        ]

    payload = dict(kwargs)
    if events is not None:
        payload["events"] = events
    elif session_id is not None:
        payload["events"] = []

    return analyze_personality_session(payload)


def get_profile_response(
    profile: dict[str, Any] | None = None,
    session_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return get_personality_profile_response(profile, session_result)


def get_trend_response(sessions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sessions = sessions or []
    return {
        "sessions": sessions,
        "trend": [
            {
                "session_id": item.get("session_id"),
                "session_score": item.get("session_score") or item.get("scores") or {},
            }
            for item in sessions
        ],
    }


__all__ = [
    "analyze_personality_session",
    "score_personality_events",
    "update_personality_profile",
    "get_personality_profile_response",
    "analyze_session",
    "get_profile_response",
    "get_trend_response",
]
