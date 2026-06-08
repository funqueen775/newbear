from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import re
import threading
from typing import Any, Callable

from src.core.llm.ark_client import ArkClientError, ark_chat
from src.core.world.memory_engine import append_actor_memory
from src.core.world.runtime_state import MemoryRecord, WorldRuntimeState


REFLECTION_THRESHOLD = 35
REFLECTION_MEMORY_LIMIT = 18

_REFLECTION_EXECUTOR = ThreadPoolExecutor(max_workers=2)
_RUNNING_ACTOR_IDS: set[str] = set()
_RUNNING_LOCK = threading.Lock()


def schedule_memory_reflections(
    world: WorldRuntimeState,
    *,
    world_lock: threading.Lock,
) -> None:
    from src.core.world.seed_loader import load_world_seed

    seed = load_world_seed()
    character_by_id = {item["actor_id"]: item for item in seed["characters"]}

    for actor in world.actors.values():
        if actor.reflection_importance_buffer < REFLECTION_THRESHOLD:
            continue

        actor_id = actor.actor_id

        with _RUNNING_LOCK:
            if actor_id in _RUNNING_ACTOR_IDS:
                continue
            _RUNNING_ACTOR_IDS.add(actor_id)

        memory_snapshot = list(actor.memory_stream[-REFLECTION_MEMORY_LIMIT:])
        display_name = actor.display_name
        character = character_by_id.get(actor_id)

        _REFLECTION_EXECUTOR.submit(
            _run_actor_reflection_task,
            world,
            world_lock,
            actor_id,
            display_name,
            memory_snapshot,
            character,
        )


def _run_actor_reflection_task(
    world: WorldRuntimeState,
    world_lock: threading.Lock,
    actor_id: str,
    display_name: str,
    memory_snapshot: list[MemoryRecord],
    character: dict[str, Any] | None,
) -> None:
    try:
        reflections = _build_reflections(
            display_name=display_name,
            memories=memory_snapshot,
            character=character,
        )

        if not reflections:
            return

        with world_lock:
            actor = world.actors.get(actor_id)
            if actor is None:
                return

            for reflection_text in reflections:
                append_actor_memory(
                    world,
                    actor_id=actor_id,
                    kind="reflection",
                    text=reflection_text,
                    clock=world.company.clock,
                    tags=["reflection"],
                )

            for memory in memory_snapshot:
                memory.archived = True

            actor.reflection_importance_buffer = 0

    finally:
        with _RUNNING_LOCK:
            _RUNNING_ACTOR_IDS.discard(actor_id)


def _build_reflections(
    *,
    display_name: str,
    memories: list[MemoryRecord],
    character: dict[str, Any] | None = None,
) -> list[str]:
    if not memories:
        return []

    personality_hint = ""
    if character:
        profile = character.get("character_profile", {}) or {}
        personality = profile.get("personality", {}) or {}
        style = personality.get("speaking_style", "")
        shadow = personality.get("shadow_pattern", "")
        job = character.get("job_profile", {}).get("role_name", "")
        personality_hint = (
            f"你是{job}，说话风格：{style}，"
            f"内心阴影：{shadow}。\n"
        )

    memory_text = "\n".join(
        f"- {memory.clock} [{memory.kind}] {memory.text}"
        for memory in memories
    )

    messages = [
        {
            "role": "system",
            "content": (
                f"你是职场模拟中的{display_name}。{personality_hint}"
                "请根据最近的记忆，用你自己的语气提炼你形成的稳定判断。"
                "只输出 JSON，不要 Markdown，不要解释。"
                '{"reflections":["反思1","反思2","反思3"]}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"最近记忆：\n{memory_text}\n\n"
                "请生成 2 到 3 条短反思。"
                "反思要像你自己的内心独白，不要像工作总结。"
                "优先关注：用户说的话、突发事件、同事态度、公司风险、自己的压力。"
            ),
        },
    ]

    try:
        raw_reply = ark_chat(messages=messages, temperature=0.4, max_tokens=500)
        parsed = _parse_json_object(raw_reply)
    except (ArkClientError, ValueError):
        return _fallback_reflections(memories)

    raw_reflections = parsed.get("reflections", [])
    if not isinstance(raw_reflections, list):
        return _fallback_reflections(memories)

    reflections = [
        str(item).strip()
        for item in raw_reflections
        if str(item).strip()
    ]

    return reflections[:3] or _fallback_reflections(memories)


def _fallback_reflections(memories: list[MemoryRecord]) -> list[str]:
    if not memories:
        return []

    return [
        f"我需要把最近这些事情串起来看，不能只处理眼前任务：{memories[-1].text[:80]}"
    ]


def _parse_json_object(text: str) -> dict[str, Any]:
    source = str(text or "").strip()
    if not source:
        raise ValueError("empty response")

    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", source, re.S)
        if not match:
            raise ValueError("no json object")
        data = json.loads(match.group(0))

    if not isinstance(data, dict):
        raise ValueError("response is not an object")

    return data
