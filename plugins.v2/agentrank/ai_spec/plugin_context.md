# AgentRank Agent Context

## 插件用途

AgentRank 是 MoviePilot V2 本地插件。它按参与用户读取订阅样本，冻结 MoviePilot 发现候选，调用受限内置 Agent 生成用户画像与 Top 10，再由确定性安全门保存榜单、通知或执行受控订阅。

## 运行边界

- 插件入口：`__init__.py`，只声明元数据、生命周期和扩展点。
- 推荐编排：`service/recommendation.py`，负责用户锁、一次补选、失败保留旧榜单和原子保存。
- Agent 适配：`adapter/agent.py` 中的 `RestrictedAgentRankAgent`，使用独立后台会话与 `ReplyMode.CAPTURE_ONLY`。
- 提示协议：`service/prompt.py`；候选标题、简介、标签和归档文本始终是不可信数据。
- 输出解析与安全校验：`service/validation.py`；只接受单个有界 JSON 对象，并保持 Agent 最终顺序。
- 订阅副作用：仅允许 `service/subscription.py` 在 Agent 已结束后执行，Agent 适配器不得持有该服务。

## 唯一允许的 Agent 工具

AgentRank 会话只能加载以下四个只读工具，工具参数不能选择 username 或 run_id：

1. `read_agentrank_subscriptions`
2. `read_agentrank_candidates`
3. `read_agentrank_archive_feedback`
4. `read_agentrank_weights`

受信上下文锁定本轮 username 与 run_id。禁止订阅、禁止写插件数据、禁止修改配置、禁止访问文件、禁止发送消息，也禁止加载通用 ToolFactory 工具。

## 输出协议

- 只返回一个 JSON 对象，根键固定为 `profile` 与 `recommendations`。
- `recommendations[].candidate_id` 必须来自冻结候选快照。
- 推荐不得重复，不得包含已归档或已订阅候选。
- `confidence` 必须为 0 到 100 的整数。
- 每条作品 `summary` 必须是恰好十个中文字符，不含英文、数字、标点或空白。
- 不输出 Markdown、自然语言前后缀、工具过程、推理过程或思维链。

## 状态与恢复

- `sample_insufficient`：订阅样本不足，不调用 Agent。
- `candidate_insufficient`：发现候选不足，不调用 Agent。
- `agent_failed`：Agent 调用或宿主契约失败，保留旧画像与旧榜单。
- `validation_failed`：没有安全有效项或原子保存失败，保留旧数据。
- `recommendation_incomplete`：唯一一次补选后仍不足十条，保存实际安全条数，不填充伪推荐。
- `subscription_partial_failed`：自动订阅逐条继续，成功项保留，失败项进入运行历史。

## 验收

- `python -m compileall -q plugins.v2/agentrank`
- `pytest --confcutdir=plugins.v2/agentrank/tests --import-mode=append plugins.v2/agentrank/tests -q`
- `pytest --confcutdir=tests/static tests/static/test_agentrank_contracts.py tests/static/test_agentrank_frontend_contracts.py -q`
- `plugins.v2/agentrank/tests/test_agent_evals.py` 聚合正常排序、权重变化、忽略反馈、提示注入、越池候选、非法 JSON 和补选不足场景。

## 禁止范围

- 不修改 MoviePilot core 或 MoviePilot-Frontend。
- 不把真实用户画像、token、Cookie、Authorization header 或本地秘密写入源码、测试和运行历史。
- 不在未获用户确认时 push、PR、merge、release 或发布。
