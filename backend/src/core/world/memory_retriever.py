from __future__ import annotations

from src.core.world.runtime_state import ActorRuntimeState, MemoryRecord

IMPORTANT_TERMS = [
    # 原有
    "现金", "客户", "竞对", "挖走", "离职", "预算", "延期",
    "Demo", "传播", "技术", "会议", "成本", "需求",
    # 角色关系
    "信任", "怀疑", "支持", "反对", "冲突", "合作", "背刺",
    # 情绪/压力
    "焦虑", "崩溃", "疲惫", "满意", "不满", "抱怨",
    # 决策/行动
    "拍板", "妥协", "让步", "坚持", "拒绝", "同意", "投票",
    # 风险/机会
    "风险", "机会", "危机", "转机", "救命", "完蛋",
]

KIND_WEIGHT = {
    "reflection": 1.3,
    "meeting": 1.2,
    "user_input": 1.15,
    "incident": 1.25,
    "pantry": 1.1,
    "observation": 1.0,
}


def retrieve_relevant_memories(
    actor: ActorRuntimeState,
    *,
    query: str,
    limit: int = 6,
) -> list[str]:
    query_terms = _extract_terms(query)
    scored: list[tuple[float, MemoryRecord]] = []

    total = len(actor.memory_stream)

    for index, memory in enumerate(actor.memory_stream):
        recency_score = index / max(1, total)
        importance_score = memory.importance / 10
        relevance_score = _keyword_score(memory.text, query_terms)
        kind_weight = KIND_WEIGHT.get(memory.kind, 1.0)
        archived_factor = 0.3 if memory.archived else 1.0

        score = (
            (recency_score * 0.2 + importance_score * 0.3 + relevance_score * 0.35)
            * kind_weight
            * archived_factor
        )
        scored.append((score, memory))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [memory.text for _, memory in scored[:limit]]


def _extract_terms(query: str) -> list[str]:
    source = str(query or "").strip()
    if not source:
        return []

    return [term for term in IMPORTANT_TERMS if term in source]


def _keyword_score(text: str, terms: list[str]) -> float:
    if not terms:
        return 0.0

    hit_count = sum(1 for term in terms if term in text)
    return min(1.0, hit_count / max(1, len(terms)))


def retrieve_causal_chain(
    actor: ActorRuntimeState,
    target_memory_id: int,
    max_depth: int = 3,
) -> list[str]:
    chain = []
    current_id = target_memory_id
    id_to_memory = {m.memory_id: m for m in actor.memory_stream}

    for _ in range(max_depth):
        memory = id_to_memory.get(current_id)
        if memory is None:
            break
        chain.append(memory.text)
        if memory.caused_by_id is None:
            break
        current_id = memory.caused_by_id

    return list(reversed(chain))
