# BE-007 personality_model v0.4 迁移日志

## 迁移摘要

已将独立 `personality-model` v0.4 的核心评分、聚合、画像更新和 newbear adapter 迁入 newbear 后端既有目录：

```text
backend/src/core/world/personality_model/
```

本次迁移只提供可调用的后端 Python 子模块，不改变现有前端、HTTP 路由或主游戏流程。

## 新增文件

- `backend/src/core/world/personality_model/adapters/`
- `backend/src/core/world/personality_model/aggregation.py`
- `backend/src/core/world/personality_model/profile_updater.py`
- `backend/src/core/world/personality_model/service.py`
- `backend/src/core/world/personality_analyzer.py`
- `backend/test_personality_model_v04.py`
- `docs/log-be-007-personality-model-v04.md`

## 更新或确认的核心文件

- `backend/src/core/world/personality_model/feature_extractor.py`
- `backend/src/core/world/personality_model/rule_scorer.py`
- `backend/src/core/world/personality_model/__init__.py`
- `backend/src/core/world/personality_model/adapters/__init__.py`

以下 v0.4 核心文件在当前分支中已与迁移目标兼容，保留在原位置供新服务入口调用：

- `backend/src/core/world/personality_model/schemas.py`
- `backend/src/core/world/personality_model/llm_prompt.py`
- `backend/src/core/world/personality_model/llm_scorer.py`
- `backend/src/core/world/personality_model/hybrid_scorer.py`
- `backend/src/core/world/personality_model/report_builder.py`

## 未动关键文件

- `backend/server.py`
- `frontend/`
- `backend/src/core/db/`
- `backend/src/core/world/report_engine.py`
- `backend/src/core/world/step_engine.py`
- `backend/src/core/llm/ark_client.py`

## 调用示例

```python
from src.core.world.personality_model.service import analyze_personality_session

result = analyze_personality_session(
    {
        "events": [
            {
                "metadata": {"session_id": "S-1", "user_id": "U-1", "scene_name": "meeting"},
                "dialogue_event": {
                    "event_id": "EV-1",
                    "game_id": "S-1",
                    "round_id": 1,
                    "npc_role": "熊老板",
                    "trigger_condition": {"scene": "meeting"},
                    "npc_dialogue_script": "今天必须上线，你怎么处理？",
                    "user_response_type": "FreeText",
                },
                "response_meta": {
                    "event_id": "EV-1",
                    "user_free_text_input": "我会先确认风险，再推动团队合作。",
                },
            }
        ]
    }
)
```

返回结果包含：

- `events`
- `scene_scores`
- `session_score`
- `profile_update`
- `profile_response`
- `llm_status`

## 测试命令

```bash
PYTHONPATH=backend python3 -m pytest backend/test_personality_model_v04.py
python3 backend/test_database.py
python3 backend/test_seed_loader.py
python3 backend/test_be006.py
python3 - <<'PY'
import sys
sys.path.insert(0, "backend")
import server
print("server import ok")
PY
```

## LLM 状态

当前默认 `use_llm=False`，不会连接 DeepSeek、OpenAI-compatible API 或 Ark，也不需要任何 API key。`hybrid` 在未启用 LLM 时会使用 rule scoring 作为 fallback，并在 `scoring_trace` / `llm_status` 中标记未使用真实 LLM。

后续如果需要真实 LLM，需要由后端同学单独显式传入 `use_llm=True` 并配置运行环境。代码不会写死或输出 API key；若缺少 key、缺少 OpenAI-compatible SDK、请求失败或 LLM 返回无法解析，`hybrid` 会自动回退到 rule baseline，并记录 fallback reason。
