from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import ScoreInput


def _get_game_id(user: Any, world: Any) -> str:
    """Prefer business session_record_id, then fall back to auth session_id."""

    return str(world.session_record_id or user.session_id)


def _clean_clock(clock: str) -> str:
    return str(clock or "").replace(":", "")


def _last_non_user_line(transcript: list[dict[str, Any]]) -> dict[str, Any] | None:
    for line in reversed(transcript or []):
        actor_id = str(line.get("actor_id") or "")
        kind = str(line.get("kind") or "")
        role = str(line.get("role") or "")

        if actor_id != "user" and kind != "user" and role != "user":
            return line

    return None


def _line_text(line: dict[str, Any] | None) -> str:
    if not line:
        return ""

    return str(
        line.get("content")
        or line.get("speech")
        or line.get("text")
        or ""
    )


def _line_speaker(line: dict[str, Any] | None) -> str:
    if not line:
        return ""

    return str(
        line.get("speaker")
        or line.get("display_name")
        or line.get("actor_id")
        or ""
    )


def _build_meeting_context(world: Any) -> tuple[str, str, dict[str, Any], str]:
    meeting = world.active_meeting
    company = world.company

    if meeting is None:
        return (
            "会议 NPC",
            "玩家在会议场景中发言。",
            {
                "scene": "meeting",
                "day": company.day,
                "step": company.step,
                "clock": company.clock,
            },
            "meeting",
        )

    last_npc_line = _last_non_user_line(meeting.transcript)

    npc_role = _line_speaker(last_npc_line) or "会议 NPC"
    npc_script = (
        _line_text(last_npc_line)
        or meeting.content
        or meeting.title
        or "玩家在会议场景中发言。"
    )

    trigger_condition = {
        "scene": "meeting",
        "meeting_id": meeting.meeting_id,
        "title": meeting.title,
        "content": meeting.content,
        "phase": meeting.phase,
        "participants": meeting.participants,
        "day": company.day,
        "step": company.step,
        "clock": company.clock,
    }

    return npc_role, npc_script, trigger_condition, meeting.meeting_id


def _build_pantry_context(world: Any) -> tuple[str, str, dict[str, Any], str]:
    pantry = world.active_pantry
    company = world.company

    if pantry is None:
        return (
            "茶水间 NPC",
            "玩家在茶水间场景中发言。",
            {
                "scene": "pantry",
                "day": company.day,
                "step": company.step,
                "clock": company.clock,
            },
            "pantry",
        )

    last_npc_line = _last_non_user_line(pantry.transcript)

    npc_role = _line_speaker(last_npc_line) or "茶水间 NPC"
    npc_script = (
        _line_text(last_npc_line)
        or pantry.content
        or pantry.title
        or "玩家在茶水间场景中发言。"
    )

    trigger_condition = {
        "scene": "pantry",
        "pantry_id": pantry.pantry_id,
        "title": pantry.title,
        "content": pantry.content,
        "phase": pantry.phase,
        "participants": pantry.participants,
        "day": company.day,
        "step": company.step,
        "clock": company.clock,
    }

    return npc_role, npc_script, trigger_condition, pantry.pantry_id


def _build_world_context(world: Any) -> tuple[str, str, dict[str, Any], str]:
    company = world.company
    pending_incident = world.pending_incident

    if pending_incident is not None:
        npc_script = f"{pending_incident.title}：{pending_incident.content}"
        subject_id = pending_incident.incident_id
    else:
        npc_script = "玩家在世界主流程中输入事务处理方案。"
        subject_id = "world"

    trigger_condition = {
        "scene": "world",
        "company_name": company.name,
        "company_phase": company.phase,
        "cash": company.cash,
        "day": company.day,
        "step": company.step,
        "clock": company.clock,
        "pending_incident_id": pending_incident.incident_id if pending_incident else None,
        "pending_incident_title": pending_incident.title if pending_incident else None,
    }

    return "系统", npc_script, trigger_condition, subject_id


def _build_scene_context(world: Any, scene: str) -> tuple[str, str, dict[str, Any], str]:
    if scene == "meeting":
        return _build_meeting_context(world)

    if scene == "pantry":
        return _build_pantry_context(world)

    return _build_world_context(world)


def _build_event_id(
    *,
    game_id: str,
    scene: str,
    world: Any,
    subject_id: str,
    counter: int,
) -> str:
    company = world.company

    return (
        f"{game_id}:{scene}:day{company.day}:"
        f"step{company.step}:clock{_clean_clock(company.clock)}:"
        f"{subject_id}:{counter}"
    )


def _counter_for_scene(world: Any, scene: str) -> int:
    if scene == "meeting" and world.active_meeting is not None:
        return len(world.active_meeting.transcript) + 1

    if scene == "pantry" and world.active_pantry is not None:
        return len(world.active_pantry.transcript) + 1

    return len(world.user_inputs) + 1


def build_score_input_from_world(
    *,
    user: Any,
    world: Any,
    scene: str,
    user_text: str,
    selected_option: int | None = None,
    response_time_ms: int | None = None,
) -> ScoreInput:
    """Convert newbear user/world input into personality-model ScoreInput."""

    clean_scene = str(scene or "world").strip() or "world"
    clean_user_text = str(user_text or "").strip()

    game_id = _get_game_id(user, world)
    company = world.company

    npc_role, npc_script, trigger_condition, subject_id = _build_scene_context(
        world,
        clean_scene,
    )

    counter = _counter_for_scene(world, clean_scene)

    event_id = _build_event_id(
        game_id=game_id,
        scene=clean_scene,
        world=world,
        subject_id=subject_id,
        counter=counter,
    )

    payload = {
        "metadata": {
            "session_id": game_id,
            "user_id": str(user.user_id),
            "scene_name": clean_scene,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "clock": company.clock,
            "day": company.day,
            "step": company.step,
            "auth_session_id": str(user.session_id),
            "world_session_record_id": str(world.session_record_id or ""),
        },
        "dialogue_event": {
            "event_id": event_id,
            "game_id": game_id,
            "round_id": int(company.step),
            "npc_role": npc_role,
            "trigger_condition": trigger_condition,
            "npc_dialogue_script": npc_script,
            "user_response_type": "Option" if selected_option is not None else "FreeText",
        },
        "response_meta": {
            "event_id": event_id,
            "user_free_text_input": clean_user_text,
            "user_selected_option": selected_option,
            "response_time_ms": response_time_ms,
        },
    }

    return ScoreInput.from_dict(payload)
