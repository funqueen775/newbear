from __future__ import annotations

from src.core.config.pantry_events import SCRIPTED_PANTRY_EVENTS
from src.core.world.memory_engine import append_actor_memory
from src.core.world.runtime_state import ActivePantryState, WorldRuntimeState


def trigger_pantry_for_clock(world: WorldRuntimeState, clock: str) -> ActivePantryState | None:
    normalized_clock = str(clock or "").strip()

    if world.active_pantry is not None:
        return world.active_pantry

    for index, item in enumerate(SCRIPTED_PANTRY_EVENTS, start=1):
        pantry_id = f"pantry-{index}"
        pantry_time = str(item.get("time", "")).strip()

        if pantry_id in world.triggered_pantry_ids:
            continue

        if pantry_time != normalized_clock:
            continue

        participants = list(world.actors.keys())

        pantry = ActivePantryState(
            pantry_id=pantry_id,
            time=pantry_time,
            title=str(item.get("title", "")),
            content=str(item.get("content", "")),
            participants=participants,
            day=world.company.day,
            step=world.company.step,
            clock=world.company.clock,
        )

        world.active_pantry = pantry
        world.triggered_pantry_ids.add(pantry_id)

        for actor_id in participants:
            actor = world.actors.get(actor_id)
            if actor:
                actor.location = "休闲区"
                actor.current_task = f"茶水间闲谈：{pantry.title}"
                actor.intent = "communicate"
                actor.move_to = "休闲区"

        world.company.logs.append(
            {
                "type": "pantry_triggered",
                "clock": normalized_clock,
                "pantry_id": pantry_id,
                "title": pantry.title,
                "participants": participants,
            }
        )

        return pantry

    return None


def add_user_pantry_message(world: WorldRuntimeState, message: str) -> ActivePantryState | None:
    pantry = world.active_pantry
    clean_message = str(message or "").strip()

    if pantry is None or not clean_message:
        return pantry

    pantry.transcript.append(
        {
            "speaker": "产品经理",
            "actor_id": "user",
            "kind": "user",
            "content": clean_message,
        }
    )

    pantry.transcript = pantry.transcript[-80:]
    return pantry


def close_active_pantry(world: WorldRuntimeState) -> None:
    pantry = world.active_pantry
    if pantry is None:
        return

    summary = str(pantry.result.get("thought") or pantry.result.get("summary") or "").strip()
    if summary:
        memory_text = f"{world.company.clock} 茶水间闲谈：{pantry.title}。{summary}"
    else:
        memory_text = f"{world.company.clock} 茶水间闲谈：{pantry.title}。大家在轻松场景里交换了一些真实想法。"

    for actor_id in pantry.participants:
        append_actor_memory(
            world,
            actor_id=actor_id,
            kind="pantry",
            text=memory_text,
            clock=world.company.clock,
            related_actor_ids=[item for item in pantry.participants if item != actor_id],
            tags=["pantry", "informal_chat"],
        )

    world.company.logs.append(
        {
            "type": "pantry_closed",
            "clock": world.company.clock,
            "pantry_id": pantry.pantry_id,
            "title": pantry.title,
        }
    )

    world.active_pantry = None
