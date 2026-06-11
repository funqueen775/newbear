# BE-007 personality_model v0.4 人格评分模块 — 开发日志

## 当前状态：v0.4 后端引擎迁移完成，主流程自动触发待后端接入

当前分支 `chen/personality-model-v03-integration` 已在既有 `backend/src/core/world/personality_model/` 目录上升级到 `personality-model v0.4`。本次完成的是后端内部评分引擎 MVP：主项目可 import、可从 event/session payload 得到 Big Five 五维结果、可做 scene/session 聚合和 profile smoothing。

还没有把评分自动接入 `server.py` 的玩家输入路由，也没有把 session_report 接到日终、老板信、人格报告页。需要后端同学继续做主流程集成，并确认现有游戏流程是否仍在使用旧人格/报告逻辑。

## 变更记录

| 时间 | 阶段 | 变更 | 原因 |
|------|------|------|------|
| 2026-06-08 | Phase 1 | 确认 BE-007 仍对应陈鸿淼的人格分析/评分模块 | 对齐 `phase1-task-assignment-react-ts-only.md` 分工 |
| 2026-06-08 | Phase 1 | 确认最新主线为 `486bba5`，已完成 React 前端与后端 event flow 整合 | 后续集成必须基于最新 `main`，避免旧分支冲突 |
| 2026-06-08 | Phase 2 | 创建 `plan-be-007-personality-model-v03.md` | 按现有 BE-005 / BE-006 文档风格补齐规划 |
| 2026-06-08 | Phase 3 | 新增 `backend/src/core/world/personality_model/` | 将独立评分模块纳入 newbear 后端世界模块目录 |
| 2026-06-08 | Phase 3 | 引入 `schemas.py`、`rule_scorer.py`、`llm_scorer.py`、`hybrid_scorer.py` 等核心文件 | 支持 rule baseline、LLM zero-shot、hybrid 和 `final_result` 输出 |
| 2026-06-08 | Phase 3 | 暂不修改 `server.py`、前端组件和现有 report 流程 | 降低对已打通前后端主线的影响 |
| 2026-06-08 | Phase 3 | 新增 `backend/src/core/world/personality_model/adapter.py` | 先放入主项目字段转换层，将 `user + world + scene + 玩家输入` 映射为 `ScoreInput`，暂不接 `server.py` |
| 2026-06-11 | Phase 4 | 迁入 v0.4 `adapters/`、`aggregation.py`、`profile_updater.py` | 支持 newbear 数据转换、scene/session 聚合、长期画像 smoothing |
| 2026-06-11 | Phase 4 | 新增 `backend/src/core/world/personality_model/service.py` | 提供 `analyze_personality_session`、`score_personality_events`、`update_personality_profile`、`get_personality_profile_response` |
| 2026-06-11 | Phase 4 | 新增 `backend/src/core/world/personality_analyzer.py` | 保留旧文档预期入口名，底层调用 v0.4 service |
| 2026-06-11 | Phase 4 | 新增 `backend/test_personality_model_v04.py` | 覆盖 import、adapter、scoring、aggregation、profile 和兼容入口 |
| 2026-06-11 | Phase 4 | 保持 `server.py`、前端、DB 层、report flow 不变 | 本次只完成引擎迁移，不改变现有游戏业务 |

## 决策记录

| # | 问题 | 决策 | 理由 |
|---|------|------|------|
| 1 | 是否直接合入旧 `chen/personality-analyzer-be007` | 不合入 | 旧分支落后最新主线，且接口口径与 v0.3 不完全一致 |
| 2 | 模块放置位置 | `backend/src/core/world/personality_model/` | 模块包含多个文件，目录方式比单文件更清晰，也贴近 world 领域 |
| 3 | 是否本阶段改前端 | 不改 | 前端已打通主流程，BE-007 先作为后端内部模块落地 |
| 4 | 是否强依赖 LLM | 不强依赖 | LLM 默认关闭，缺 key 或失败时 fallback 到规则评分 |
| 5 | 后端写回读取哪个字段 | `final_result.feedback` | 避免将 0-100 中间人格分直接写入 M9 |
| 6 | v0.4 默认是否启用 LLM | 不启用，`use_llm=False` | 满足当前“不接真实 DeepSeek / LLM API、不需要 key”的验收要求 |
| 7 | 是否现在接 `/score/event` / `/score/session` HTTP 路由 | 暂不接 | 先提供 Python service；HTTP 和主流程自动触发交给后端集成阶段 |

## 待办

| 优先级 | 任务 | 说明 |
|------|------|------|
| P0 | 接入玩家输入路由 | 在 `/api/step`、`/api/meeting/say`、`/api/pantry/say` 调用 v0.4 service |
| P0 | 设计 scored events 持久化 | 明确 scored event 保存到 JSONL、DB 字段还是新表 |
| P0 | session 汇总接日终/报告 | 第 11-14 页读取 `session_score`、`decision_style`、`evidence` |
| P1 | M9/profile 写回 | 明确 `final_result.feedback` 与 `profile_update` 写回位置 |
| P1 | 封装 `/score/event` 和 `/score/session` | 如后端需要独立调试接口，再加 HTTP 路由 |
| P2 | 后续启用真实 LLM | 单独配置 DeepSeek / OpenAI-compatible API，默认仍需 fallback |

## 后端接入说明

v0.4 service 已在当前分支新增：

```text
backend/src/core/world/personality_model/service.py
backend/src/core/world/personality_model/adapters/newbear_adapter.py
```

后续在 `server.py` 三个玩家输入入口接入：

| 路由 | adapter 参数 |
|------|------|
| `/api/step` | `scene="world"`，`user_text=affair` |
| `/api/meeting/say` | `scene="meeting"`，`user_text=message` |
| `/api/pantry/say` | `scene="pantry"`，`user_text=message` |

推荐调用方式：

```python
from src.core.world.personality_model.service import analyze_personality_session

result = analyze_personality_session(
    {
        "user": user,
        "world": world,
        "scene": "world",  # 或 "meeting" / "pantry"
        "user_text": affair,
        "old_profile": existing_profile,
    }
)
```

接入建议：

- `/api/step` 建议在 `run_one_step(world, affair=affair)` 之前生成 `score_input`，以保留当前 `pending_incident` 上下文。
- `/api/meeting/say` 和 `/api/pantry/say` 可以在 `add_user_meeting_message` / `add_user_pantry_message` 附近接。
- 第一版默认 `use_llm=False`，只跑规则 fallback。
- 评分失败时只记录日志，不阻断主流程。
- 后端还需要决定 scored events 持久化位置、`final_result.feedback` 写回位置，以及 `evidence` / `decision_style` 如何进入报告页数据。

## 需要和后端同学确认的问题

1. 现在游戏流程里是否还在用旧的人格/报告逻辑，而没有调用 `backend/src/core/world/personality_model/service.py`？
2. 玩家输入路由 `/api/step`、`/api/meeting/say`、`/api/pantry/say` 里，准备在哪里插入 `analyze_personality_session(...)`？
3. `scored_events` 是保存到 JSONL、现有 SQLite 表，还是新增表？
4. 日终、老板信、人格报告页当前读取哪个 report 数据源？是否可以接入 `session_score`、`evidence`、`decision_style`？
5. M9 写回现在有没有明确字段？如果没有，第一版是否先把 `profile_update` merge 到 `user_profiles.personality_data`？

## 本次验证

```bash
PYTHONPATH=backend python3 -m pytest -q backend/test_personality_model_v04.py
python3 backend/test_database.py
python3 backend/test_seed_loader.py
python3 backend/test_be006.py
```

结果：

- `backend/test_personality_model_v04.py`：10 passed
- `backend/test_database.py`：26/26 通过
- `backend/test_seed_loader.py`：通过
- `backend/test_be006.py`：ALL TESTS PASSED
- 后端 `server.py` 可启动，基础注册 / state / step / sessions API smoke flow 通过

## 验收标准

- `backend/src/core/world/personality_model/` 可被 Python 正常 import。
- 给定 `metadata + dialogue_event + response_meta`，可返回包含 `final_result` 的评分结果。
- LLM 未启用时接口不中断，`final_result == rule_result`。
- `final_result.feedback` 包含 `game_id`、`round_id`、`actor_id=玩家` 和五维变化量。
- 不提交 `.env`、API key、`data/outputs/`、`__pycache__/` 等本地文件。
