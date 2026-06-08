from __future__ import annotations

from typing import Any

from src.core.world.runtime_state import EncounterRecord, MemoryRecord, RelationshipRecord, WorldRuntimeState



def write_step_memories(
    world: WorldRuntimeState,
    *,
    clock: str,
    affair: str,
    actor_reactions: list[dict[str, Any]],
    encounter_records: list[EncounterRecord],
    incident: object | None = None,
) -> None:
    actor_by_id = world.actors
    action_by_actor_id = {
        str(item.get("actor_id", "")): item
        for item in actor_reactions
        if str(item.get("actor_id", "")).strip()
    }

    for actor in world.actors.values():
        memory_lines: list[str] = []
        clean_affair = str(affair or "").strip()
        if clean_affair:
            append_actor_memory(
                world,
                actor_id=actor.actor_id,
                kind="user_input",
                text=f"{clock} 产品经理说：{clean_affair}",
                clock=clock,
                tags=["user_input"],
            )

        if incident is not None:
            append_actor_memory(
                world,
                actor_id=actor.actor_id,
                kind="incident",
                text=f"{clock} 公司突发事件：{incident.title}。{incident.content}",
                clock=clock,
                tags=["incident"],
            )


        own_action = action_by_actor_id.get(actor.actor_id)
        if own_action:
            own_task = str(own_action.get("task", "") or "").strip()
            own_speech = str(own_action.get("speech", "") or "").strip()
            own_location = str(own_action.get("to_location") or own_action.get("location") or actor.location)

            if own_task or own_speech:
                memory_lines.append(
                    f"{clock} 我在{own_location}处理：{own_task or '日常工作'}；我说：{own_speech or '我没有明确发言'}"
                )

        for other_action in actor_reactions:
            other_actor_id = str(other_action.get("actor_id", "") or "").strip()
            if not other_actor_id or other_actor_id == actor.actor_id:
                continue

            other_actor = actor_by_id.get(other_actor_id)
            if other_actor is None:
                continue

            other_location = str(
                other_action.get("to_location")
                or other_action.get("location")
                or other_actor.location
            )
            if other_location != actor.location:
                continue

            other_name = str(other_action.get("display_name") or other_actor.display_name)
            other_speech = str(other_action.get("speech", "") or "").strip()
            other_task = str(other_action.get("task", "") or "").strip()

            if other_speech:
                memory_lines.append(
                    f"{clock} 我在{actor.location}听见{other_name}说：{other_speech}"
                )
                _update_relationship(
                    actor, other_actor_id, other_speech,
                    world.company.step, clock,
                )
            elif other_task:
                memory_lines.append(
                    f"{clock} 我在{actor.location}看到{other_name}在处理：{other_task}"
                )

        for encounter in encounter_records:
            if encounter.location != actor.location:
                continue

            for line in encounter.dialogue:
                speaker_id = str(line.get("actor_id", "") or "").strip()
                if not speaker_id:
                    continue

                speech = str(line.get("speech", "") or "").strip()
                if not speech:
                    continue

                speaker = actor_by_id.get(speaker_id)
                speaker_name = speaker.display_name if speaker else speaker_id

                if speaker_id == actor.actor_id:
                    memory_lines.append(f"{clock} 我在相遇对话中说：{speech}")
                else:
                    memory_lines.append(f"{clock} 我在{actor.location}听见{speaker_name}说：{speech}")
                    _update_relationship(
                        actor, speaker_id, speech,
                        world.company.step, clock,
                    )

        if not memory_lines:
            continue

        for memory_line in _dedupe_keep_order(memory_lines):
            append_actor_memory(
                world,
                actor_id=actor.actor_id,
                kind="observation",
                text=memory_line,
                clock=clock,
            )



def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        result.append(normalized)

    return result


def _update_relationship(
    observer: Any,
    target_actor_id: str,
    speech: str,
    step: int,
    clock: str,
    is_positive: bool = True,
) -> None:
    if target_actor_id not in observer.relationships:
        observer.relationships[target_actor_id] = RelationshipRecord(
            target_actor_id=target_actor_id
        )
    rel = observer.relationships[target_actor_id]
    rel.interaction_count += 1
    rel.last_interaction_step = step
    rel.last_interaction_clock = clock

    if is_positive:
        rel.trust = min(100, rel.trust + 3)
    else:
        rel.trust = max(0, rel.trust - 5)

    if speech:
        rel.impression = speech[:30]


def estimate_importance(text: str, kind: str = "observation") -> int:
    score = 1

    if kind == "self":
        score += 1
    elif kind == "dialogue":
        score += 2
    elif kind == "meeting":
        score += 4
    elif kind == "reflection":
        score += 5
    elif kind == "user_input":
        score += 4
    elif kind == "incident":
        score += 6
    elif kind == "pantry":
        score += 3


    high_impact_words = [
        "离职",
        "挖走",
        "竞对",
        "崩",
        "现金",
        "客户",
        "延期",
        "失败",
        "冲突",
        "预算",
        "涨薪",
        "裁员",
    ]

    for word in high_impact_words:
        if word in text:
            score += 2

    return min(10, max(1, score))


MAX_MEMORY_STREAM = 120
PROTECTED_RECENT = 10


def _evict_lowest_importance(memory_stream: list[MemoryRecord]) -> list[MemoryRecord]:
    if len(memory_stream) <= MAX_MEMORY_STREAM:
        return memory_stream
    protected = memory_stream[-PROTECTED_RECENT:]
    candidates = memory_stream[:-PROTECTED_RECENT]
    to_remove = len(memory_stream) - MAX_MEMORY_STREAM
    candidates.sort(key=lambda m: m.importance)
    survivors = candidates[to_remove:]
    return sorted(protected + survivors, key=lambda m: m.memory_id)


DEDUP_WINDOW = 20
DEDUP_THRESHOLD = 0.65


def _is_duplicate(new_text: str, existing: list[MemoryRecord]) -> bool:
    new_chars = set(new_text)
    for old in existing[-DEDUP_WINDOW:]:
        old_chars = set(old.text)
        overlap = len(new_chars & old_chars) / max(len(new_chars | old_chars), 1)
        if overlap > DEDUP_THRESHOLD:
            return True
    return False


def append_actor_memory(
    world: WorldRuntimeState,
    *,
    actor_id: str,
    kind: str,
    text: str,
    clock: str,
    related_actor_ids: list[str] | None = None,
    tags: list[str] | None = None,
) -> None:
    actor = world.actors.get(actor_id)
    if actor is None:
        return

    clean_text = text.strip()
    if not clean_text:
        return

    if kind not in ("reflection", "meeting") and _is_duplicate(clean_text, actor.memory_stream):
        return

    importance = estimate_importance(clean_text, kind)

    record = MemoryRecord(
        memory_id=actor.memory_next_id,
        kind=kind,
        text=clean_text,
        day=world.company.day,
        step=world.company.step,
        clock=clock,
        importance=importance,
        tags=tags or [],
        related_actor_ids=related_actor_ids or [],
    )

    actor.memory_next_id += 1
    actor.memory_stream.append(record)
    actor.memory_stream = _evict_lowest_importance(actor.memory_stream)

    actor.reflection_importance_buffer += importance
