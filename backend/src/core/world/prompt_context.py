from __future__ import annotations
from src.core.map.map_semantics import build_map_context_text
from typing import Any
import json


def build_company_context(company: dict[str, Any]) -> str:
    goals = "；".join(str(item) for item in company.get("short_term_goals", []) or [])
    return "\n".join(
        [
            f"公司名称：{company.get('name', '')}",
            f"公司类型：{company.get('company_type', '')}",
            f"业务方向：{company.get('business', '')}",
            f"阶段：{company.get('stage', '')}",
            f"资金状态：{company.get('funding_status', '')}",
            f"短期目标：{goals}",
            f"团队状态：{company.get('team_state', '')}",
        ]
    )


def build_character_context(character: dict[str, Any]) -> str:
    profile = character.get("character_profile", {}) or {}
    job = character.get("job_profile", {}) or {}
    personality = profile.get("personality", {}) or {}
    work = profile.get("work", {}) or {}
    habits = "、".join(str(item) for item in personality.get("habits", []) or [])
    drives = "、".join(str(item) for item in personality.get("core_drives", []) or [])
    return "\n".join(
        [
            f"人物：{character.get('display_name', '')}",
            f"岗位：{job.get('role_name', '')}",
            f"身份：{profile.get('work_title', '')}",
            f"年龄：{profile.get('age', '')}",
            f"婚育与经济：{profile.get('marital_status', '')}；{profile.get('economic_status', '')}",
            f"教育与通勤：{profile.get('education', '')}；{profile.get('commute', '')}",
            f"核心驱动力：{drives}",
            f"习惯：{habits}",
            f"说话方式：{personality.get('speaking_style', '')}",
            f"阴影模式：{personality.get('shadow_pattern', '')}",
            f"公司压力视角：{work.get('company_lens', '')}",
            f"职责：{job.get('responsibility', '')}",
            f"权限：{job.get('power', '')}",
            f"KPI：{job.get('kpi', '')}",
        ]
    )


def build_actor_reaction_messages(
    *,
    company: dict[str, Any],
    character: dict[str, Any],
    clock: str,
    affair: str,
    memories: list[str] | None = None,
    incident: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    memory_text = "\n".join(f"- {item}" for item in (memories or [])[-8:])
    if not memory_text:
        memory_text = "暂无"

    system_prompt = "\n\n".join(
        [
            "你是一个该公司职场中的角色，你不是在演戏，不要刻意的讨好别人，你也是人，你也可以偷懒，也可以撒谎，也可以发牢骚，当然是基于你的人物性格。但是你也有自己的工作职责所在，最重要的任务是配合产品经理一起推动公司发展",
            "对了，产品经理是你们公司的团宠，他说的话你得格外注意，也就是affair，你也可以经常向他主动搭话",
            build_company_context(company),
            build_map_context_text(),
            build_character_context(character),
            f"你的最近记忆：\n{memory_text}",
            "在输出下面内容时，先构思一段自己内心的想法，然后从这一想法出发去回答"
            "输出要求：只输出 JSON，不要 Markdown，不要解释。",
            (
                'JSON 格式：{"task":"当前要做的具体任务",'
                '"speech":"一句符合人物性格的自然发言",'
                '"intent":"当前意图，如 work/communicate/decide/rest/observe",'
                '"move_to":"想去的公司地点，要只能从 开放办公区/会议室/会客区/休闲区/活动区 中选择"}'
            ),
        ]
    )
    incident_text = "无"
    if incident:
        incident_text = f"{incident.get('title', '')}：{incident.get('content', '')}"

    user_prompt = "\n".join(
        
        [
            
            f"当前时间：{clock}",
            f"当前固定事件：{incident_text}",
            f"用户作为产品经理说的话：{affair or '无额外事务'}",
            "请生成这个角色此刻的任务、意图、想去的地点和一句发言。发言要短、具体、有岗位视角。",
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
def build_dialogue_decision_messages(
    *,
    clock: str,
    affair: str,
    encounter_groups: list[dict[str, Any]],
) -> list[dict[str, str]]:
    system_prompt = "\n".join(
        [
            "你是职场模拟器的系统层社交调度器，不扮演任何具体角色。",
            "你的任务是判断同一地点相遇的人是否真的需要对话。",
            "默认不要聊天。只有存在明确协作、分歧、决策、信息传递或突发响应需求时，才安排对话。",
            "只输出 JSON，不要 Markdown，不要解释。",
            'JSON 格式：{"conversations":[{"location":"地点","actor_ids":["角色ID1","角色ID2"],"topic":"为什么要聊"}]}',
            "如果没有需要发生的对话，输出：{\"conversations\":[]}",
        ]
    )

    user_prompt = "\n".join(
        [
            f"当前时间：{clock}",
            f"本时间步事务：{affair or '无额外事务'}",
            "候选相遇场景：",
            json.dumps(encounter_groups, ensure_ascii=False),
        ]
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
def build_dialogue_generation_messages(
    *,
    clock: str,
    affair: str,
    conversations: list[dict[str, Any]],
    actors: list[dict[str, Any]],
) -> list[dict[str, str]]:
    system_prompt = "\n".join(
        [
            "你是职场模拟器的对话生成器。",
            "你要为已经决定发生的对话生成完整台词。",
            "对话要短、自然、符合角色岗位和性格。",
            "每个参与者至少说一句。",
            "不要写旁白，不要写动作描写，只写说出口的话。",
            "只输出 JSON，不要 Markdown，不要解释。",
            'JSON 格式：{"conversations":[{"location":"地点","actor_ids":["角色ID1","角色ID2"],"lines":[{"actor_id":"角色ID","to_actor_id":"对谁说","speech":"一句话"}]}]}',
        ]
    )

    user_prompt = "\n".join(
        [
            f"当前时间：{clock}",
            f"本时间步事务：{affair or '无额外事务'}",
            "已经决定发生的对话：",
            json.dumps(conversations, ensure_ascii=False),
            "参与者资料：",
            json.dumps(actors, ensure_ascii=False),
        ]
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


