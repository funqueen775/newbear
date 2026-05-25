from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any


BIG_FIVE_TRAITS = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)

DECISION_STYLES = (
    "rational",
    "emotional",
    "assertive",
    "avoidant",
)

TRAIT_LABELS = {
    "openness": "开放性",
    "conscientiousness": "尽责性",
    "extraversion": "外向性",
    "agreeableness": "宜人性",
    "neuroticism": "神经质",
}

STYLE_LABELS = {
    "rational": "理性分析",
    "emotional": "情绪/价值驱动",
    "assertive": "主动决断",
    "avoidant": "回避/延后",
}

TEXT_FIELDS = (
    "raw_text",
    "text",
    "input",
    "message",
    "choice",
    "action",
    "decision",
    "summary",
    "content",
    "description",
)

REPORT_TEXT_FIELDS = (
    "trait_summary",
    "letter_title",
    "letter_body",
    "summary",
    "title",
    "content",
    "description",
)

KEYWORDS = {
    "openness": {
        "positive": (
            "创意",
            "创新",
            "变化",
            "尝试",
            "探索",
            "新方案",
            "新功能",
            "实验",
            "假设",
            "原型",
            "灵感",
            "alternative",
            "creative",
            "experiment",
            "explore",
            "prototype",
        ),
        "negative": ("照旧", "不变", "保守", "老办法"),
    },
    "conscientiousness": {
        "positive": (
            "计划",
            "细节",
            "标准",
            "清单",
            "截止",
            "成本",
            "风险",
            "确认",
            "数据",
            "复盘",
            "排期",
            "优先级",
            "责任",
            "验证",
            "指标",
            "plan",
            "check",
            "risk",
            "metric",
        ),
        "negative": ("随便", "差不多", "不用管", "懒得", "拖延"),
    },
    "extraversion": {
        "positive": (
            "推进",
            "拍板",
            "争取",
            "说服",
            "沟通",
            "会议",
            "主动",
            "表达",
            "协调",
            "客户",
            "分享",
            "发起",
            "present",
            "promote",
            "coordinate",
        ),
        "negative": ("沉默", "不说", "躲开", "退出"),
    },
    "agreeableness": {
        "positive": (
            "团队",
            "感受",
            "帮",
            "一起",
            "对齐",
            "信任",
            "倾听",
            "支持",
            "合作",
            "共识",
            "体谅",
            "理解",
            "安抚",
            "协作",
            "support",
            "trust",
            "listen",
        ),
        "negative": ("指责", "甩锅", "争吵", "无所谓", "不管别人"),
    },
    "neuroticism": {
        "positive": (
            "焦虑",
            "紧张",
            "担心",
            "害怕",
            "压力",
            "慌",
            "崩",
            "不安",
            "失控",
            "纠结",
            "生气",
            "急躁",
            "worry",
            "anxious",
            "stress",
        ),
        "negative": (
            "冷静",
            "稳",
            "稳定",
            "先别急",
            "缓冲",
            "判断",
            "控制",
            "平衡",
            "观察",
            "calm",
            "steady",
        ),
    },
}

STYLE_KEYWORDS = {
    "rational": (
        "数据",
        "风险",
        "成本",
        "优先级",
        "验证",
        "证据",
        "计划",
        "指标",
        "分析",
        "先看",
        "复盘",
        "因果",
        "data",
        "evidence",
        "risk",
        "metric",
    ),
    "emotional": (
        "感受",
        "直觉",
        "担心",
        "喜欢",
        "讨厌",
        "害怕",
        "兴奋",
        "情绪",
        "难受",
        "信任",
        "intuition",
        "feel",
    ),
    "assertive": (
        "拍板",
        "决定",
        "立即",
        "推进",
        "承担",
        "我来",
        "必须",
        "争取",
        "直接",
        "落地",
        "发起",
        "decide",
        "commit",
    ),
    "avoidant": (
        "再等等",
        "先不",
        "暂缓",
        "回避",
        "不确定",
        "没办法",
        "以后",
        "算了",
        "拖",
        "推迟",
        "观望",
        "avoid",
        "delay",
    ),
}


def analyze_session(session_id: str, report: Any, user_inputs: Any) -> dict[str, Any]:
    """Extract one-session personality signals from report and player behavior."""
    report_scores = _extract_report_scores(report)
    text_records = _collect_text_records(report, user_inputs)
    text_values = [record["text"] for record in text_records]

    big_five: dict[str, int] = {}
    for trait in BIG_FIVE_TRAITS:
        keyword_score = _keyword_score(
            text_values,
            KEYWORDS[trait]["positive"],
            KEYWORDS[trait]["negative"],
        )
        report_score = report_scores.get(trait)
        if report_score is None:
            big_five[trait] = keyword_score
        else:
            big_five[trait] = _clamp_score(report_score * 0.65 + keyword_score * 0.35)

    decision_style = {
        style: _decision_style_score(text_values, STYLE_KEYWORDS[style])
        for style in DECISION_STYLES
    }

    behavior_evidence = _build_behavior_evidence(text_records)

    return {
        "session_id": str(session_id),
        "big_five": big_five,
        "decision_style": decision_style,
        "behavior_evidence": behavior_evidence,
        "summary": _build_session_summary(big_five, decision_style, behavior_evidence),
        "source_counts": {
            "report_evidence": _count_report_evidence(report),
            "user_inputs": _count_user_inputs(user_inputs),
        },
    }


def update_user_profile(
    user_id: str,
    existing_profile: dict[str, Any] | None,
    session_result: dict[str, Any],
) -> dict[str, Any]:
    """Create or update a user-level profile with weighted session aggregation."""
    profile = deepcopy(existing_profile) if isinstance(existing_profile, dict) else {}
    history = _extract_sessions(profile)

    old_weight = _positive_float(profile.get("total_weight"), default=0.0)
    if old_weight <= 0 and history:
        old_weight = float(len(history))
    new_weight = _positive_float(
        session_result.get("session_weight", session_result.get("weight")),
        default=1.0,
    )

    session_big_five = _normalize_score_mapping(
        _read_mapping(session_result, "big_five", "scores"),
        BIG_FIVE_TRAITS,
        default=50,
    )
    session_decision_style = _normalize_score_mapping(
        _read_mapping(session_result, "decision_style"),
        DECISION_STYLES,
        default=0,
    )

    if old_weight > 0 and isinstance(profile.get("big_five"), dict):
        current_big_five = _normalize_score_mapping(profile["big_five"], BIG_FIVE_TRAITS, default=50)
        big_five = _weighted_scores(current_big_five, session_big_five, old_weight, new_weight)
    else:
        big_five = session_big_five

    if old_weight > 0 and isinstance(profile.get("decision_style"), dict):
        current_decision_style = _normalize_score_mapping(
            profile["decision_style"],
            DECISION_STYLES,
            default=0,
        )
        decision_style = _weighted_scores(
            current_decision_style,
            session_decision_style,
            old_weight,
            new_weight,
        )
    else:
        decision_style = session_decision_style

    session_entry = _make_session_entry(
        session_result,
        index=len(history) + 1,
        weight=new_weight,
        big_five=session_big_five,
        decision_style=session_decision_style,
    )
    session_history = history + [session_entry]
    trend = get_trend(session_history)

    return {
        "user_id": str(user_id),
        "big_five": big_five,
        "decision_style": decision_style,
        "summary": _build_profile_summary(big_five, decision_style, len(session_history)),
        "session_count": len(session_history),
        "latest_session_id": session_entry["session_id"],
        "session_history": session_history,
        "total_weight": old_weight + new_weight,
        "trend": trend,
    }


def get_trend(profile_or_sessions: Any) -> dict[str, Any]:
    """Return cross-session score movement for profile history or session lists."""
    sessions = _extract_sessions(profile_or_sessions)
    if not sessions and isinstance(profile_or_sessions, dict) and isinstance(
        profile_or_sessions.get("big_five"), dict
    ):
        sessions = [profile_or_sessions]

    normalized_sessions = [
        _normalize_session_for_trend(session, index)
        for index, session in enumerate(sessions, start=1)
        if isinstance(session, dict)
    ]
    normalized_sessions = [session for session in normalized_sessions if session is not None]

    if not normalized_sessions:
        return _empty_trend()

    big_five_trend = {trait: [] for trait in BIG_FIVE_TRAITS}
    decision_style_trend = {style: [] for style in DECISION_STYLES}

    for session in normalized_sessions:
        for trait in BIG_FIVE_TRAITS:
            big_five_trend[trait].append(
                {
                    "session_id": session["session_id"],
                    "index": session["index"],
                    "score": session["big_five"][trait],
                }
            )
        for style in DECISION_STYLES:
            decision_style_trend[style].append(
                {
                    "session_id": session["session_id"],
                    "index": session["index"],
                    "score": session["decision_style"][style],
                }
            )

    first = normalized_sessions[0]["big_five"]
    latest = normalized_sessions[-1]["big_five"]
    delta = {trait: latest[trait] - first[trait] for trait in BIG_FIVE_TRAITS}

    first_style = normalized_sessions[0]["decision_style"]
    latest_style = normalized_sessions[-1]["decision_style"]
    decision_delta = {style: latest_style[style] - first_style[style] for style in DECISION_STYLES}

    return {
        "session_count": len(normalized_sessions),
        "big_five_trend": big_five_trend,
        "latest_scores": latest,
        "delta": delta,
        "direction": {trait: _direction(value) for trait, value in delta.items()},
        "decision_style_trend": decision_style_trend,
        "latest_decision_style": latest_style,
        "decision_delta": decision_delta,
    }


def get_profile_response(user_id: str, profile: dict[str, Any] | None) -> dict[str, Any]:
    """Shape a profile object for a future profile API response."""
    if not isinstance(profile, dict) or not profile:
        return _empty_profile_response(user_id)

    history = _extract_sessions(profile)
    has_profile_scores = isinstance(profile.get("big_five"), dict)
    session_count = int(profile.get("session_count") or len(history) or (1 if has_profile_scores else 0))
    if session_count <= 0 and not has_profile_scores:
        return _empty_profile_response(user_id)

    generated_at = _utc_now_iso()
    big_five = _normalize_score_mapping(profile.get("big_five"), BIG_FIVE_TRAITS, default=50)
    decision_style = _normalize_score_mapping(
        profile.get("decision_style"),
        DECISION_STYLES,
        default=0,
    )
    latest_session = history[-1] if history else {}
    latest_scores = _latest_big_five_scores(latest_session, big_five)
    latest_decision_style = _latest_decision_style_scores(latest_session, decision_style)
    public_history = [
        _public_session(session, index)
        for index, session in enumerate(history, start=1)
    ]

    return {
        "user_id": str(user_id),
        "has_data": True,
        "session_count": session_count,
        "big_five": big_five,
        "decision_style": decision_style,
        "latest_scores": latest_scores,
        "latest_decision_style": latest_decision_style,
        "summary": str(profile.get("summary") or ""),
        "latest_session_id": profile.get("latest_session_id") or latest_session.get("session_id"),
        "behavior_evidence": _safe_list(
            latest_session.get("behavior_evidence") or profile.get("behavior_evidence")
        ),
        "session_history": public_history,
        "sessions": public_history,
        "evidence_summary": _build_evidence_summary(profile, history),
        "trend": get_trend(profile),
        "updated_at": str(profile.get("updated_at") or generated_at),
        "generated_at": generated_at,
    }


def get_trend_response(user_id: str, trend: dict[str, Any] | None) -> dict[str, Any]:
    """Shape trend data for a future trend API response."""
    trend_data = trend if _looks_like_trend(trend) else get_trend(trend)
    normalized = _normalize_trend_data(trend_data)

    return {
        "user_id": str(user_id),
        "has_data": bool(normalized["session_count"]),
        "session_count": normalized["session_count"],
        "big_five_trend": normalized["big_five_trend"],
        "latest_scores": normalized["latest_scores"],
        "delta": normalized["delta"],
        "direction": normalized["direction"],
        "decision_style_trend": normalized["decision_style_trend"],
        "latest_decision_style": normalized["latest_decision_style"],
        "decision_delta": normalized["decision_delta"],
        "generated_at": _utc_now_iso(),
    }


def _extract_report_scores(report: Any) -> dict[str, int]:
    data = _as_mapping(report)
    score_sources: list[Any] = [
        data.get("scores"),
        data.get("big_five"),
        data.get("personality_scores"),
        data,
    ]

    normalized: dict[str, int] = {}
    emotional_stability: int | None = None

    for source in score_sources:
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            mapped = _map_score_key(key)
            if mapped is None:
                continue
            score = _clamp_score(value)
            if mapped == "emotional_stability":
                emotional_stability = score
            else:
                normalized[mapped] = score

    for item in _safe_list(data.get("radar_items")):
        if not isinstance(item, dict):
            continue
        mapped = _map_score_key(item.get("code") or item.get("label") or item.get("name"))
        if mapped is None:
            continue
        score = _clamp_score(item.get("value") or item.get("score"))
        if mapped == "emotional_stability":
            emotional_stability = score
        else:
            normalized[mapped] = score

    if emotional_stability is not None and "neuroticism" not in normalized:
        normalized["neuroticism"] = 100 - emotional_stability

    return normalized


def _collect_text_records(report: Any, user_inputs: Any) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    report_data = _as_mapping(report)

    for field in REPORT_TEXT_FIELDS:
        text = _clean_text(report_data.get(field))
        if text:
            records.append({"source": "report", "field": field, "text": text})

    for item in _safe_list(report_data.get("evidence")):
        text = _clean_text(item)
        if text:
            records.append({"source": "report", "field": "evidence", "text": text})

    for item in _iter_items(user_inputs):
        data = _as_mapping(item)
        fragments: list[str] = []

        if isinstance(item, str):
            fragments.append(item)

        for field in TEXT_FIELDS:
            value = data.get(field)
            if isinstance(value, (list, tuple)):
                fragments.extend(str(part) for part in value)
            else:
                text = _clean_text(value)
                if text:
                    fragments.append(text)

        for behavior in _safe_list(data.get("behavior") or data.get("behaviors")):
            text = _clean_text(behavior)
            if text:
                fragments.append(text)

        for reaction in _safe_list(data.get("actor_reactions")):
            reaction_data = _as_mapping(reaction)
            for field in ("reaction", "response", "text", "message", "summary"):
                text = _clean_text(reaction_data.get(field))
                if text:
                    fragments.append(text)

        text = "；".join(_dedupe_keep_order(_clean_text(fragment) for fragment in fragments))
        if text:
            records.append(
                {
                    "source": "user_input",
                    "field": str(data.get("clock") or data.get("step") or ""),
                    "text": text,
                }
            )

    return _dedupe_records(records)


def _keyword_score(text_values: list[str], positive: tuple[str, ...], negative: tuple[str, ...]) -> int:
    joined = "\n".join(text_values).lower()
    positive_hits = _count_keywords(joined, positive)
    negative_hits = _count_keywords(joined, negative)
    return _clamp_score(50 + positive_hits * 7 - negative_hits * 7)


def _decision_style_score(text_values: list[str], keywords: tuple[str, ...]) -> int:
    joined = "\n".join(text_values).lower()
    hits = _count_keywords(joined, keywords)
    if not joined.strip():
        return 0
    return _clamp_score(20 + hits * 10)


def _build_behavior_evidence(records: list[dict[str, str]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for record in records:
        text = record["text"]
        lowered = text.lower()

        for trait in BIG_FIVE_TRAITS:
            signals = _matched_keywords(
                lowered,
                KEYWORDS[trait]["positive"] + KEYWORDS[trait]["negative"],
            )
            if signals:
                key = (trait, text)
                if key not in seen:
                    seen.add(key)
                    evidence.append(
                        {
                            "source": record["source"],
                            "dimension": trait,
                            "label": TRAIT_LABELS[trait],
                            "text": _clip_text(text),
                            "signals": signals[:4],
                        }
                    )

        for style in DECISION_STYLES:
            signals = _matched_keywords(lowered, STYLE_KEYWORDS[style])
            if signals:
                key = (style, text)
                if key not in seen:
                    seen.add(key)
                    evidence.append(
                        {
                            "source": record["source"],
                            "dimension": style,
                            "label": STYLE_LABELS[style],
                            "text": _clip_text(text),
                            "signals": signals[:4],
                        }
                    )

    return evidence[:12]


def _build_session_summary(
    big_five: dict[str, int],
    decision_style: dict[str, int],
    evidence: list[dict[str, Any]],
) -> str:
    if not evidence:
        return "本局可用行为信息较少，暂以中性画像作为起点。"

    strongest_trait = max(big_five, key=big_five.get)
    strongest_style = max(decision_style, key=decision_style.get)
    return (
        f"本局最突出的画像信号是{TRAIT_LABELS[strongest_trait]}，"
        f"决策上更偏{STYLE_LABELS[strongest_style]}；"
        f"共提取 {len(evidence)} 条行为证据。"
    )


def _build_profile_summary(
    big_five: dict[str, int],
    decision_style: dict[str, int],
    session_count: int,
) -> str:
    strongest_trait = max(big_five, key=big_five.get)
    strongest_style = max(decision_style, key=decision_style.get)
    return (
        f"已累计 {session_count} 局画像数据。"
        f"当前最稳定的高分维度是{TRAIT_LABELS[strongest_trait]}，"
        f"常见决策风格偏向{STYLE_LABELS[strongest_style]}。"
    )


def _make_session_entry(
    session_result: dict[str, Any],
    *,
    index: int,
    weight: float,
    big_five: dict[str, int],
    decision_style: dict[str, int],
) -> dict[str, Any]:
    return {
        "session_id": str(session_result.get("session_id") or f"session-{index}"),
        "index": index,
        "weight": weight,
        "big_five": big_five,
        "decision_style": decision_style,
        "behavior_evidence": _safe_list(session_result.get("behavior_evidence"))[:12],
        "summary": str(session_result.get("summary") or ""),
    }


def _normalize_session_for_trend(session: dict[str, Any], index: int) -> dict[str, Any] | None:
    big_five_source = _read_mapping(session, "big_five", "scores")
    if not isinstance(big_five_source, dict):
        return None

    return {
        "session_id": str(session.get("session_id") or f"session-{index}"),
        "index": int(session.get("index") or index),
        "big_five": _normalize_score_mapping(big_five_source, BIG_FIVE_TRAITS, default=50),
        "decision_style": _normalize_score_mapping(
            _read_mapping(session, "decision_style"),
            DECISION_STYLES,
            default=0,
        ),
    }


def _weighted_scores(
    current: dict[str, int],
    incoming: dict[str, int],
    current_weight: float,
    incoming_weight: float,
) -> dict[str, int]:
    total_weight = current_weight + incoming_weight
    if total_weight <= 0:
        return {key: _clamp_score(incoming[key]) for key in incoming}

    return {
        key: _clamp_score(
            (current[key] * current_weight + incoming[key] * incoming_weight) / total_weight
        )
        for key in incoming
    }


def _extract_sessions(profile_or_sessions: Any) -> list[dict[str, Any]]:
    if isinstance(profile_or_sessions, list):
        return [deepcopy(item) for item in profile_or_sessions if isinstance(item, dict)]

    if not isinstance(profile_or_sessions, dict):
        return []

    for key in ("session_history", "sessions", "history"):
        value = profile_or_sessions.get(key)
        if isinstance(value, list):
            return [deepcopy(item) for item in value if isinstance(item, dict)]

    return []


def _public_session(session: dict[str, Any], index: int) -> dict[str, Any]:
    evidence = _safe_list(session.get("behavior_evidence"))
    return {
        "session_id": str(session.get("session_id") or f"session-{index}"),
        "index": int(session.get("index") or index),
        "weight": _positive_float(session.get("weight"), default=1.0),
        "big_five": _normalize_score_mapping(
            _read_mapping(session, "big_five", "scores"),
            BIG_FIVE_TRAITS,
            default=50,
        ),
        "decision_style": _normalize_score_mapping(
            _read_mapping(session, "decision_style"),
            DECISION_STYLES,
            default=0,
        ),
        "behavior_evidence": evidence[:12],
        "evidence_count": len(evidence),
        "summary": str(session.get("summary") or ""),
    }


def _latest_big_five_scores(
    latest_session: dict[str, Any],
    fallback: dict[str, int],
) -> dict[str, int]:
    source = _read_mapping(latest_session, "big_five", "scores")
    if isinstance(source, dict):
        return _normalize_score_mapping(source, BIG_FIVE_TRAITS, default=50)
    return {trait: _clamp_score(fallback.get(trait, 50)) for trait in BIG_FIVE_TRAITS}


def _latest_decision_style_scores(
    latest_session: dict[str, Any],
    fallback: dict[str, int],
) -> dict[str, int]:
    source = _read_mapping(latest_session, "decision_style")
    if isinstance(source, dict):
        return _normalize_score_mapping(source, DECISION_STYLES, default=0)
    return {style: _clamp_score(fallback.get(style, 0), default=0) for style in DECISION_STYLES}


def _build_evidence_summary(
    profile: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for evidence in _safe_list(profile.get("behavior_evidence")):
        item = _public_evidence_item(evidence)
        if item is not None:
            items.append(item)

    for session in history:
        session_id = str(session.get("session_id") or "")
        for evidence in _safe_list(session.get("behavior_evidence")):
            item = _public_evidence_item(evidence, session_id=session_id)
            if item is not None:
                items.append(item)

    if not items:
        return _empty_evidence_summary()

    by_dimension = _empty_dimension_counts()
    for item in items:
        dimension = str(item.get("dimension") or "")
        if not dimension:
            continue
        by_dimension[dimension] = by_dimension.get(dimension, 0) + 1

    return {
        "count": len(items),
        "by_dimension": by_dimension,
        "latest": items[-5:],
        "items": items[:20],
    }


def _public_evidence_item(evidence: Any, *, session_id: str = "") -> dict[str, Any] | None:
    if isinstance(evidence, dict):
        text = _clean_text(evidence.get("text") or evidence.get("summary") or evidence.get("content"))
        if not text:
            return None

        return {
            "session_id": str(evidence.get("session_id") or session_id),
            "source": str(evidence.get("source") or ""),
            "dimension": str(evidence.get("dimension") or ""),
            "label": str(evidence.get("label") or ""),
            "text": _clip_text(text),
            "signals": [str(item) for item in _safe_list(evidence.get("signals"))][:4],
        }

    text = _clean_text(evidence)
    if not text:
        return None

    return {
        "session_id": session_id,
        "source": "",
        "dimension": "",
        "label": "",
        "text": _clip_text(text),
        "signals": [],
    }


def _empty_evidence_summary() -> dict[str, Any]:
    return {
        "count": 0,
        "by_dimension": _empty_dimension_counts(),
        "latest": [],
        "items": [],
    }


def _empty_dimension_counts() -> dict[str, int]:
    return {dimension: 0 for dimension in BIG_FIVE_TRAITS + DECISION_STYLES}


def _empty_profile_response(user_id: str) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    return {
        "user_id": str(user_id),
        "has_data": False,
        "session_count": 0,
        "big_five": {},
        "decision_style": {},
        "latest_scores": {},
        "latest_decision_style": {},
        "summary": "",
        "latest_session_id": None,
        "behavior_evidence": [],
        "session_history": [],
        "sessions": [],
        "evidence_summary": _empty_evidence_summary(),
        "trend": _empty_trend(),
        "updated_at": generated_at,
        "generated_at": generated_at,
    }


def _empty_trend() -> dict[str, Any]:
    return {
        "session_count": 0,
        "big_five_trend": {trait: [] for trait in BIG_FIVE_TRAITS},
        "latest_scores": {},
        "delta": {},
        "direction": {},
        "decision_style_trend": {style: [] for style in DECISION_STYLES},
        "latest_decision_style": {},
        "decision_delta": {},
    }


def _normalize_trend_data(trend_data: Any) -> dict[str, Any]:
    if not isinstance(trend_data, dict):
        return _empty_trend()

    big_five_trend = _normalize_trend_series_map(
        trend_data.get("big_five_trend"),
        BIG_FIVE_TRAITS,
    )
    decision_style_trend = _normalize_trend_series_map(
        trend_data.get("decision_style_trend"),
        DECISION_STYLES,
    )
    session_count = _trend_session_count(trend_data, big_five_trend)

    if session_count <= 0:
        return _empty_trend()

    latest_scores = _normalize_latest_scores(
        trend_data.get("latest_scores"),
        big_five_trend,
        BIG_FIVE_TRAITS,
        default=50,
    )
    latest_decision_style = _normalize_latest_scores(
        trend_data.get("latest_decision_style"),
        decision_style_trend,
        DECISION_STYLES,
        default=0,
    )
    delta = _normalize_delta_mapping(
        trend_data.get("delta"),
        big_five_trend,
        BIG_FIVE_TRAITS,
    )
    decision_delta = _normalize_delta_mapping(
        trend_data.get("decision_delta"),
        decision_style_trend,
        DECISION_STYLES,
    )
    direction_source = trend_data.get("direction") if isinstance(trend_data.get("direction"), dict) else {}

    return {
        "session_count": session_count,
        "big_five_trend": big_five_trend,
        "latest_scores": latest_scores,
        "delta": delta,
        "direction": {
            trait: str(direction_source.get(trait) or _direction(delta[trait]))
            for trait in BIG_FIVE_TRAITS
        },
        "decision_style_trend": decision_style_trend,
        "latest_decision_style": latest_decision_style,
        "decision_delta": decision_delta,
    }


def _normalize_trend_series_map(
    source: Any,
    dimensions: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    source_map = source if isinstance(source, dict) else {}
    return {
        dimension: _normalize_trend_series(source_map.get(dimension), dimension)
        for dimension in dimensions
    }


def _normalize_trend_series(source: Any, dimension: str) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for index, point in enumerate(_safe_list(source), start=1):
        if isinstance(point, dict):
            point_index = _safe_int(point.get("index"), default=index)
            session_id = str(point.get("session_id") or f"session-{point_index}")
            score = _clamp_score(point.get("score"))
        else:
            point_index = index
            session_id = f"session-{index}"
            score = _clamp_score(point)

        series.append(
            {
                "session_id": session_id,
                "index": point_index,
                "score": score,
            }
        )

    return series


def _trend_session_count(
    trend_data: dict[str, Any],
    big_five_trend: dict[str, list[dict[str, Any]]],
) -> int:
    explicit_count = _safe_int(trend_data.get("session_count"), default=0)
    series_count = max((len(series) for series in big_five_trend.values()), default=0)
    return max(explicit_count, series_count)


def _normalize_latest_scores(
    source: Any,
    trend_map: dict[str, list[dict[str, Any]]],
    dimensions: tuple[str, ...],
    *,
    default: int,
) -> dict[str, int]:
    if isinstance(source, dict):
        return _normalize_score_mapping(source, dimensions, default=default)

    latest: dict[str, int] = {}
    for dimension in dimensions:
        series = trend_map.get(dimension) or []
        latest[dimension] = _clamp_score(series[-1]["score"], default=default) if series else default
    return latest


def _normalize_delta_mapping(
    source: Any,
    trend_map: dict[str, list[dict[str, Any]]],
    dimensions: tuple[str, ...],
) -> dict[str, int]:
    source_map = source if isinstance(source, dict) else {}
    delta: dict[str, int] = {}

    for dimension in dimensions:
        if dimension in source_map:
            delta[dimension] = _safe_int(source_map.get(dimension), default=0)
            continue

        series = trend_map.get(dimension) or []
        if len(series) >= 2:
            delta[dimension] = _safe_int(series[-1]["score"], default=0) - _safe_int(
                series[0]["score"],
                default=0,
            )
        else:
            delta[dimension] = 0

    return delta


def _looks_like_trend(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "session_count" in value
        and "big_five_trend" in value
        and "latest_scores" in value
    )


def _map_score_key(key: Any) -> str | None:
    text = str(key or "").strip()
    lowered = text.lower()

    direct = {
        "o": "openness",
        "openness": "openness",
        "open": "openness",
        "c": "conscientiousness",
        "conscientiousness": "conscientiousness",
        "e": "extraversion",
        "extraversion": "extraversion",
        "a": "agreeableness",
        "agreeableness": "agreeableness",
        "n": "neuroticism",
        "neuroticism": "neuroticism",
        "s": "emotional_stability",
        "stability": "emotional_stability",
        "emotional_stability": "emotional_stability",
    }
    if lowered in direct:
        return direct[lowered]

    contains = (
        ("开放", "openness"),
        ("尽责", "conscientiousness"),
        ("责任", "conscientiousness"),
        ("外向", "extraversion"),
        ("宜人", "agreeableness"),
        ("合作", "agreeableness"),
        ("神经", "neuroticism"),
        ("焦虑", "neuroticism"),
        ("情绪稳定", "emotional_stability"),
        ("稳定性", "emotional_stability"),
    )
    for token, trait in contains:
        if token in text:
            return trait

    return None


def _normalize_score_mapping(
    mapping: Any,
    keys: tuple[str, ...],
    *,
    default: int,
) -> dict[str, int]:
    source = mapping if isinstance(mapping, dict) else {}
    return {key: _clamp_score(source.get(key, default), default=default) for key in keys}


def _read_mapping(source: Any, *keys: str) -> Any:
    if not isinstance(source, dict):
        return None

    for key in keys:
        value = source.get(key)
        if isinstance(value, dict):
            return value
    return None


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _iter_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _safe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _clip_text(value: str, limit: int = 160) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _dedupe_keep_order(items: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _dedupe_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for record in records:
        key = (record["source"], record["text"])
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def _count_keywords(source: str, keywords: tuple[str, ...]) -> int:
    return sum(source.count(keyword.lower()) for keyword in keywords if keyword)


def _matched_keywords(source: str, keywords: tuple[str, ...]) -> list[str]:
    return [keyword for keyword in keywords if keyword and keyword.lower() in source]


def _count_report_evidence(report: Any) -> int:
    data = _as_mapping(report)
    return len(_safe_list(data.get("evidence")))


def _count_user_inputs(user_inputs: Any) -> int:
    return len(_iter_items(user_inputs))


def _clamp_score(value: Any, *, default: int = 50) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)

    if not math.isfinite(number):
        number = float(default)

    return int(round(min(100, max(0, number))))


def _positive_float(value: Any, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number) or number <= 0:
        return default
    return number


def _safe_int(value: Any, *, default: int) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default
    return int(round(number))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _direction(delta: int) -> str:
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "flat"
