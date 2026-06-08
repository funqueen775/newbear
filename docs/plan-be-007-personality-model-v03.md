# BE-007 personality_model v0.3 人格评分模块 — 规划文档

## 模块概述

接入陈鸿淼的 `personality-model v0.3`，把玩家在一轮游戏中的回应和当前事件上下文转成结构化人格评分结果。模块先作为后端内部评分引擎落地，不直接改现有前端流程，也不直接替换 `report_engine`。

本阶段目标是完成可复用的后端评分模块，为后续 BE-008 profile/trend API 和报告页增强提供稳定输入。

## 文件清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/src/core/world/personality_model/` | 新增 | BE-007 人格评分核心模块目录 |
| `backend/src/core/world/personality_model/schemas.py` | 新增 | 输入、输出、M9 feedback、evidence 数据结构 |
| `backend/src/core/world/personality_model/feature_extractor.py` | 新增 | 从玩家回应中补齐文本长度、情绪、词汇特征等 M7 衍生字段 |
| `backend/src/core/world/personality_model/rule_scorer.py` | 新增 | 规则 baseline 评分，保证无 LLM 时可稳定输出 |
| `backend/src/core/world/personality_model/llm_prompt.py` | 新增 | LLM zero-shot 评分 prompt |
| `backend/src/core/world/personality_model/llm_scorer.py` | 新增 | DeepSeek/OpenAI-compatible LLM 调用与 JSON 归一化 |
| `backend/src/core/world/personality_model/hybrid_scorer.py` | 新增 | rule / LLM / hybrid 融合逻辑和 `final_result` 输出 |
| `backend/src/core/world/personality_model/report_builder.py` | 新增 | 多事件 session 汇总 |
| `docs/plan-be-007-personality-model-v03.md` | 新增 | 本规划文档 |
| `docs/log-be-007-personality-model-v03.md` | 新增 | 开发日志 |

## 数据流

```text
newbear 用户输入 + 当前场景上下文
  │
  ├─ metadata：session_id / user_id / scene_name / timestamp
  ├─ dialogue_event：event_id / game_id / round_id / npc_role / npc_dialogue_script / user_response_type
  └─ response_meta：event_id / user_free_text_input / user_selected_option / response_time_ms
       │
       ▼
ScoreInput.from_dict(payload)
       │
       ├─ rule_result：规则 baseline
       ├─ llm_result：LLM zero-shot，可选
       └─ hybrid_result：rule + LLM 融合，可选
       │
       ▼
final_result
       │
       ├─ final_result.feedback → 后端写回 M9 / 用户画像聚合
       ├─ final_result.evidence → 报告页引用玩家原话和解释
       └─ final_result.decision_style → 报告页/画像展示
```

## 接口定义

本阶段不新增 HTTP 路由，先提供后端内部 Python 接口：

```python
from src.core.world.personality_model.hybrid_scorer import score
from src.core.world.personality_model.schemas import ScoreInput

score_input = ScoreInput.from_dict(payload)
result = score(score_input, method="hybrid", use_llm=False)
data = result.to_dict()
```

后续后端可在 `server.py` 中封装：

| 建议路由 | 用途 |
|------|------|
| `POST /score/event` | 单事件评分，返回 `final_result` |
| `POST /score/session` | 多事件评分，返回 events + session_report |

## 输入契约

最小输入由三组字段组成：

| 字段组 | 对应来源 | 说明 |
|------|------|------|
| `metadata` | newbear session / user / scene | 辅助信息，不属于正式 M1-M9 字段 |
| `dialogue_event` | M6 互动事件 / 当前场景上下文 | 提供 NPC、事件、台词、轮次等上下文 |
| `response_meta` | M7 用户回应 | 提供玩家文本、选项、响应时间和衍生特征 |

关键校验：

- `dialogue_event.event_id` 必须等于 `response_meta.event_id`。
- `dialogue_event.user_response_type` 只能是 `FreeText` / `Option` / `Action`。
- `response_meta.user_free_text_input` 和 `response_meta.user_selected_option` 至少应根据交互类型提供一个。

## 输出契约

后端、报告页和后续画像系统优先读取：

```text
final_result
```

`final_result` 内部核心字段：

| 字段 | 说明 |
|------|------|
| `estimated_persona` | 本轮临时五维人格评分，范围 0-100，不是 M9 原字段 |
| `feedback` | 可写回 M9 的变化量，当前每维范围 -2 到 2 |
| `decision_style` | `rational` / `empathetic` / `assertive` / `avoidant` / `balanced` / `unclear` |
| `evidence` | 结构化证据，包含 `trait`、`quote`、`reason` |
| `confidence` | 本轮评分置信度 |
| `scoring_method` | `rule_baseline` / `llm_zero_shot` / `hybrid` |

调试字段：

| 字段 | 说明 |
|------|------|
| `rule_result` | 规则 baseline 结果 |
| `llm_result` | LLM 结果，未启用或失败时为 `null` |
| `hybrid_result` | 混合结果，未融合时为 `null` |
| `scoring_trace` | 记录 LLM 是否启用、是否使用和 fallback 原因 |

## M9 写回约定

后端写回或聚合时只使用：

```text
final_result.feedback
```

不要把 `estimated_persona` 的 0-100 中间分直接写入 M9。`estimated_persona` 用于调试、分析和后续报告解释。

当前变化量换算：

| 临时分数区间 | change |
|------|------|
| `score >= 75` | `+2` |
| `60 <= score < 75` | `+1` |
| `40 < score < 60` | `0` |
| `25 < score <= 40` | `-1` |
| `score <= 25` | `-2` |

## LLM 配置

默认不依赖外部 LLM，`LLM_ENABLED=false` 或缺少 API key 时自动 fallback 到 `rule_baseline`。

可选环境变量：

```bash
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_ENABLED=true
LLM_TIMEOUT_SECONDS=30
```

`.env`、真实 API key、运行输出不得提交仓库。

## 与现有 newbear 的接入点

当前主线已有玩家输入入口：

| 路由 | 可映射字段 |
|------|------|
| `/api/step` | `response_meta.user_free_text_input = affair`，`scene_name = world` |
| `/api/meeting/say` | `response_meta.user_free_text_input = message`，`scene_name = meeting` |
| `/api/pantry/say` | `response_meta.user_free_text_input = message`，`scene_name = pantry` |

已新增 adapter：

```text
backend/src/core/world/personality_model/adapter.py
```

adapter 负责把主项目里的 `user + world + scene + 玩家输入` 转换成 personality-model 需要的 `ScoreInput`。当前还没有改 `server.py`，不会影响现有接口运行；下一步是在后端输入入口接入调用。

推荐后端内部调用 adapter，而不是让前端直接调用评分模块：

```text
server.py / world flow
  -> build_score_input_from_world(...)
  -> personality_model.score(...)
  -> persist final_result.feedback / evidence
```

调用示例：

```python
from src.core.world.personality_model.adapter import build_score_input_from_world
from src.core.world.personality_model.hybrid_scorer import score

score_input = build_score_input_from_world(
    user=user,
    world=world,
    scene="world",  # 或 "meeting" / "pantry"
    user_text=affair,  # meeting / pantry 场景传 message
)

result = score(score_input, method="hybrid", use_llm=False)
final_result = result.final_result
```

接入注意事项：

- `/api/step` 建议在 `run_one_step(world, affair=affair)` 之前生成 `score_input`，这样 adapter 能拿到当前 `pending_incident`。
- `/api/meeting/say` 和 `/api/pantry/say` 可以在 `add_user_meeting_message` / `add_user_pantry_message` 附近接。
- 第一版建议 `use_llm=False`，只跑规则 fallback。
- 评分失败时建议只记录日志，不要阻断主流程。
- 后端还需要决定 `final_result.feedback` 写回哪里，以及 `final_result.evidence` / `decision_style` 是否存给报告页。

## 假设

1. newbear 当前用户输入入口继续由后端统一保存，不要求前端感知评分逻辑。
2. `user_messages`、`reports`、`user_profiles` 表继续由后端管理。
3. 首阶段先跑 `rule_baseline`，LLM 作为可选增强，不阻塞联调。
4. `npc_role` 表示发起对话的 NPC，不是评分对象；当前评分对象固定为玩家。
5. `personality_neuroticism` 越高表示越焦虑、越压力敏感、越情绪不稳定；如展示情绪稳定性需使用 `100 - neuroticism`。

## 风险

| 风险 | 等级 | 预案 |
|------|------|------|
| newbear 现有输入缺少完整 M6/M7 字段 | 中 | 先用 adapter 补齐 `event_id`、`game_id`、`round_id`、`npc_role` 等上下文 |
| 直接暴露中间分导致用户迎合测评逻辑 | 中 | 前端只使用产品化后的报告字段，不展示 `scoring_trace` 和公式 |
| LLM key 或网络不可用 | 低 | 默认 fallback 到 `rule_baseline` |
| 旧 BE-007 分支与 v0.3 模块口径不同 | 中 | 新分支基于最新 `main`，旧分支只作为参考，不 merge |
| 过早改前端造成联调风险 | 中 | 本阶段只放后端模块和文档，不改前端 UI |
