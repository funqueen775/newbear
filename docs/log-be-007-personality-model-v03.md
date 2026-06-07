# BE-007 personality_model v0.3 人格评分模块 — 开发日志

## 当前状态：Phase 3 进行中

当前已基于最新 `main` 新建分支 `chen/personality-model-v03-integration`，并将 `personality-model v0.3` 核心评分模块放入 newbear 后端目录。旧分支 `chen/personality-analyzer-be007` 暂不合并，只作为历史参考。

## 变更记录

| 时间 | 阶段 | 变更 | 原因 |
|------|------|------|------|
| 2026-06-08 | Phase 1 | 确认 BE-007 仍对应陈鸿淼的人格分析/评分模块 | 对齐 `phase1-task-assignment-react-ts-only.md` 分工 |
| 2026-06-08 | Phase 1 | 确认最新主线为 `486bba5`，已完成 React 前端与后端 event flow 整合 | 后续集成必须基于最新 `main`，避免旧分支冲突 |
| 2026-06-08 | Phase 2 | 创建 `plan-be-007-personality-model-v03.md` | 按现有 BE-005 / BE-006 文档风格补齐规划 |
| 2026-06-08 | Phase 3 | 新增 `backend/src/core/world/personality_model/` | 将独立评分模块纳入 newbear 后端世界模块目录 |
| 2026-06-08 | Phase 3 | 引入 `schemas.py`、`rule_scorer.py`、`llm_scorer.py`、`hybrid_scorer.py` 等核心文件 | 支持 rule baseline、LLM zero-shot、hybrid 和 `final_result` 输出 |
| 2026-06-08 | Phase 3 | 暂不修改 `server.py`、前端组件和现有 report 流程 | 降低对已打通前后端主线的影响 |

## 决策记录

| # | 问题 | 决策 | 理由 |
|---|------|------|------|
| 1 | 是否直接合入旧 `chen/personality-analyzer-be007` | 不合入 | 旧分支落后最新主线，且接口口径与 v0.3 不完全一致 |
| 2 | 模块放置位置 | `backend/src/core/world/personality_model/` | 模块包含多个文件，目录方式比单文件更清晰，也贴近 world 领域 |
| 3 | 是否本阶段改前端 | 不改 | 前端已打通主流程，BE-007 先作为后端内部模块落地 |
| 4 | 是否强依赖 LLM | 不强依赖 | LLM 默认关闭，缺 key 或失败时 fallback 到规则评分 |
| 5 | 后端写回读取哪个字段 | `final_result.feedback` | 避免将 0-100 中间人格分直接写入 M9 |

## 待办

| 优先级 | 任务 | 说明 |
|------|------|------|
| P0 | 新增 newbear adapter | 把 `/api/step`、`/api/meeting/say`、`/api/pantry/say` 的输入映射为 `ScoreInput` |
| P0 | 增加 BE-007 测试 | 验证 rule fallback、event_id 校验、`final_result.feedback` 输出 |
| P1 | 设计持久化位置 | 明确 `final_result` 存到 `reports`、`user_profiles` 还是新增表 |
| P1 | 与报告页对齐展示字段 | 报告页优先使用 `final_result.evidence`、`decision_style`，不展示调试字段 |
| P2 | 封装 `/score/event` 和 `/score/session` | 如后端需要独立调试接口，再加 HTTP 路由 |

## 验收标准

- `backend/src/core/world/personality_model/` 可被 Python 正常 import。
- 给定 `metadata + dialogue_event + response_meta`，可返回包含 `final_result` 的评分结果。
- LLM 未启用时接口不中断，`final_result == rule_result`。
- `final_result.feedback` 包含 `game_id`、`round_id`、`actor_id=玩家` 和五维变化量。
- 不提交 `.env`、API key、`data/outputs/`、`__pycache__/` 等本地文件。
