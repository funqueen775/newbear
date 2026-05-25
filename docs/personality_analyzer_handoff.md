# 人格画像分析模块交接说明

## 1. 本次完成范围

本次完成 BE-007 和 BE-008 的第一阶段本地模块能力，不涉及 API 路由、数据库写入或真实 LLM 调用。

- BE-007：人格画像分析引擎
  - 从单局 `report` 和玩家输入/行为中提取人格画像数据。
  - 输出大五人格、决策风格、行为证据和摘要。
  - 支持用户画像首次创建、多 session 加权更新、趋势计算。

- BE-008：profile/trend response 数据结构补强
  - 补强 `get_profile_response` 和 `get_trend_response`。
  - 返回结构更适合未来 profile/trend API 直接使用。
  - 空数据、单 session、多 session 均有稳定返回结构。

## 2. 修改文件

- `backend/src/core/world/personality_analyzer.py`
- `backend/test_personality_analyzer.py`

## 3. 核心函数说明

### `analyze_session(session_id, report, user_inputs)`

从单局 session 的 `report` 和玩家输入/行为中提取人格信号。

输出内容包括：

- `session_id`
- `big_five`
  - `openness`
  - `conscientiousness`
  - `extraversion`
  - `agreeableness`
  - `neuroticism`
- `decision_style`
  - `rational`
  - `emotional`
  - `assertive`
  - `avoidant`
- `behavior_evidence`
- `summary`
- `source_counts`

说明：

- 当前是本地关键词/规则聚合，不调用真实 LLM。
- 可兼容日报模块中的 `O/C/E/A/S` 分数。
- `S` 表示情绪稳定性，会转换为 `neuroticism = 100 - S`。

### `update_user_profile(user_id, existing_profile, session_result)`

基于单局分析结果创建或更新用户画像。

支持：

- 首次创建用户画像。
- 多 session 加权更新。
- 人格分数限制在 `0-100`。
- 保留 `session_history` 用于后续趋势计算。

返回内容包括：

- `user_id`
- `big_five`
- `decision_style`
- `summary`
- `session_count`
- `latest_session_id`
- `session_history`
- `total_weight`
- `trend`

### `get_trend(profile_or_sessions)`

根据 profile 或 session 列表计算跨 session 趋势。

返回内容包括：

- `session_count`
- `big_five_trend`
- `latest_scores`
- `delta`
- `direction`
- `decision_style_trend`
- `latest_decision_style`
- `decision_delta`

多 session 时，每个大五人格维度都会返回趋势序列。

### `get_profile_response(user_id, profile)`

生成未来 profile API 可直接返回的数据结构。

返回内容包括：

- `user_id`
- `has_data`
- `session_count`
- `big_five`
- `decision_style`
- `latest_scores`
- `latest_decision_style`
- `summary`
- `latest_session_id`
- `behavior_evidence`
- `session_history`
- `sessions`
- `evidence_summary`
- `trend`
- `updated_at`
- `generated_at`

空数据时会返回稳定空结构，不抛异常。

### `get_trend_response(user_id, trend)`

生成未来 trend API 可直接返回的数据结构。

返回内容包括：

- `user_id`
- `has_data`
- `session_count`
- `big_five_trend`
- `latest_scores`
- `delta`
- `direction`
- `decision_style_trend`
- `latest_decision_style`
- `decision_delta`
- `generated_at`

空数据时会返回稳定空结构，不抛异常。

## 4. 当前模块输入输出说明

### `report` 支持字段

`analyze_session` 可从以下字段中读取分数和文本证据：

- `scores`
  - 支持 `O/C/E/A/S`
  - 支持 `openness/conscientiousness/extraversion/agreeableness/neuroticism`
- `big_five`
- `personality_scores`
- `radar_items`
- `trait_summary`
- `letter_title`
- `letter_body`
- `summary`
- `title`
- `content`
- `description`
- `evidence`

### `user_inputs` 支持行为字段

`user_inputs` 可传入列表、元组、单个对象或字符串。单条输入支持字段：

- `raw_text`
- `text`
- `input`
- `message`
- `choice`
- `action`
- `decision`
- `summary`
- `content`
- `description`
- `behavior`
- `behaviors`
- `actor_reactions`

`actor_reactions` 内部会尝试读取：

- `reaction`
- `response`
- `text`
- `message`
- `summary`

### profile response 返回结构

`get_profile_response` 返回适合未来 profile API 的结构，重点字段为：

- 用户维度：`user_id`、`has_data`
- 总体画像：`big_five`、`decision_style`
- 最新画像：`latest_scores`、`latest_decision_style`
- 历史数据：`session_count`、`session_history`
- 行为证据：`behavior_evidence`、`evidence_summary`
- 趋势数据：`trend`
- 时间戳：`updated_at`、`generated_at`

### trend response 返回结构

`get_trend_response` 返回适合未来 trend API 的结构，重点字段为：

- `user_id`
- `has_data`
- `session_count`
- `big_five_trend`
- `latest_scores`
- `delta`
- `direction`
- `decision_style_trend`
- `latest_decision_style`
- `decision_delta`
- `generated_at`

其中 `big_five_trend` 包含五个大五人格维度的趋势序列。

## 5. 测试说明

测试命令：

```bash
pytest backend/test_personality_analyzer.py -q
```

当前结果：

```text
8 passed
```

覆盖范围：

- 首次画像创建
- 多 session 加权更新
- 分数边界 `0-100`
- 趋势计算
- 空数据兜底
- `analyze_session` 从 `report` 和 `user_inputs` 提取人格/行为信息
- profile response 单 session API-ready 结构
- trend response 多 session 完整趋势序列

## 6. 后续接入建议

- 等 `user_profiles` / `session_records` 数据库 CRUD 稳定后再接入持久化。
- 等 `server.py` / API 路由负责人接入 profile/trend API。
- 当前模块不调用真实 LLM，只负责结构化聚合和趋势计算。
- 接 API 时建议保持当前函数边界：
  - session 完成后调用 `analyze_session`
  - 持久化前调用 `update_user_profile`
  - profile API 返回前调用 `get_profile_response`
  - trend API 返回前调用 `get_trend_response`

## 7. 注意事项

- 不读取 API Key。
- 不打印 API Key。
- 不保存 API Key。
- 不直接调用 DeepSeek。
- 不调用任何真实 LLM API。
- 不修改数据库文件。
- 不影响前端。
- 当前模块不接 API 路由，不修改 `backend/server.py`。
