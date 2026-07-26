# AgentRank Agent Context

## 插件用途

AgentRank 是 MoviePilot V2 本地插件。它按稳定 Emby identity 读取 Playback Reporting 播放快照，冻结 MoviePilot 发现候选，调用受限内置 Agent 生成用户画像与前 5 名榜单，再由确定性安全门保存榜单、通知或执行受控订阅。

## 运行边界

- 插件入口：`__init__.py`，只声明元数据、生命周期和扩展点。
- 推荐编排：`service/recommendation.py`，负责用户锁、播放快照、画像复用、候选冻结、一次补选、失败保留旧数据和分阶段保存。
- MP Provider：`adapter/discovery.py` 复用 DoubanChain、TmdbChain、BangumiChain；公共探索默认全局原始上限 150，并把 source、mode、method、params、limit 写入 request recipe。
- 依赖探测：`adapter/playback_reporting.py` 只返回 `ready`、`not_installed`、`permission_error`、`transient_error` 或 `emby_unavailable`，且不暴露 Emby 地址与凭据。
- Agent 适配：`adapter/agent.py` 中的 `RestrictedAgentRankAgent`，为画像与排序使用独立角色、独立 session 和 `ReplyMode.CAPTURE_ONLY`。
- 提示协议：`service/prompt.py`；画像提示只允许播放事实，排序提示只允许使用冻结候选、归档反馈、权重和当前画像；候选标题、简介、标签和归档文本始终是不可信数据。
- 检索计划模型：`model/retrieval.py`，固定媒体类型、TMDB 题材 ID、ISO 639-1 语言与合法排序集合。
- 受控解析：`service/keyword_resolution.py` 只把固定题材/语言别名或唯一可信 TMDB 关键词写入 filters；`adapter/tmdb_keyword.py` 通过宿主 `TmdbApi.search.keywords` 查询，不在 service 层直接发 HTTP。
- 输出解析与安全校验：`service/validation.py`；画像与排序分别使用独立 schema，只接受有界 JSON 对象，并保持排序 Agent 最终顺序。
- 订阅副作用：仅允许 `service/subscription.py` 在 Agent 已结束后执行，Agent 适配器不得持有该服务。
- Telegram 自选订阅：`service/telegram_interaction.py` 使用海报轮播和一次性会话令牌处理 `MessageAction`；按钮点击只维护待订阅清单，最终确认才调用 `service/subscription.py`。

## Agent 角色与工具边界

AgentRank 全局只允许以下四个只读工具，工具参数不能选择 username 或 run_id：

1. `read_agentrank_playback`
2. `read_agentrank_candidates`
3. `read_agentrank_archive_feedback`
4. `read_agentrank_weights`

受信上下文锁定本轮 username、run_id 与 agent role。画像 Agent 只能加载 `read_agentrank_playback`，看不到候选、归档和权重；排序 Agent 才能加载四个工具。禁止订阅、禁止写插件数据、禁止修改配置、禁止访问文件、禁止发送消息，也禁止加载通用 ToolFactory 工具。

画像 Agent 的播放工具返回当前播放快照、可选的上一版画像、人工画像标签偏好和当前只读画像。画像缓存开启、画像 schema 为当前版本且播放指纹未变化时直接复用画像，不调用画像 Agent；候选变化不能重写画像。旧 schema 画像必须先重建检索计划。播放指纹只由稳定播放事实构成，不包含 `synced_at` 等易变字段。

人工偏好必须参与画像与排序；人工避雷与未被屏蔽的 Agent 负向标签作为插件硬过滤关键词，用户删除的 Agent 标签不得重新写回。禁止用标签集合并集替代画像更新。

播放画像工具只返回当前 identity 的 Playback Reporting 受信快照，不再读取 Emby 原生 UserData。不得把其他媒体列表冒充已观看记录，也不得持久化密钥、Cookie、客户端、设备或地址信息。

## 输出协议

- 画像 Agent 只返回一个 JSON 对象，根键固定为 `profile`、`filters` 与 `ranking_tags`；不得包含候选或推荐字段。
- `filters` 的键固定为 `media_types`、`genre_ids`、`keyword_ids`、`original_languages`、`year_min`、`year_max`、`rating_min`、`vote_count_min` 和 `sort_by`，任何额外字段都拒绝。
- `media_types`、题材 ID、ISO 639-1 语言、年份 1870 至 2100、评分 0 至 10、非负票数与排序值都由确定性边界校验；未知枚举、越界值和编造 ID 不能进入检索计划。
- `keyword_ids` 只接受宿主注入的可信 ID 集合，当前默认集合为空；无法确认或尚未解析的自由语义只能进入 `ranking_tags`，由后续受控解析阶段处理。
- 画像保存前会执行一次受控解析：精确/别名匹配写入 `genre_ids`、`original_languages` 或 `keyword_ids`；歧义、无结果、查询上限和 TMDB 临时故障均保留原 `ranking_tags`，并记录解析计数，不阻断画像保存。
- Provider 请求只允许固定 chain 方法与白名单参数；来源失败按 request_id 隔离，不会丢弃其他来源结果。`fetch_recommendations()` 只接受播放快照中的正整数电影/剧集 TMDB 种子。
- 默认冻结目标 100 条，按精确探索 25、放宽探索 10、相邻题材 5、公共推荐 10 的基准比例缩放后分层召回；层级不足时只从其余有效层补足，并保持来源轮询。低于 20 条不会调用排序 Agent。
- 最终候选身份固定为 `tmdb:movie:<id>` 或 `tmdb:tv:<id>`；电影与剧集的相同数字 ID 不冲突，跨来源只按类型化身份合并，不按标题兜底。
- 插件在冻结前排除已看完、已入库、全部用户名下已有订阅、当前画像归档项和命中负向关键词的候选；任一硬过滤依赖读取失败时闭锁本轮，不调用排序 Agent。
- schema 3 候选快照记录画像版本、检索计划、候选、来源统计、排除统计、生成时间和内容 hash；同一 profile_id/run_id 只允许首次写入，保存后必须回读校验，排序 Agent 只读取回读快照。
- 排序 Agent 只返回一个 JSON 对象，根键固定为 `recommendations`；不得生成、修改或回写画像。
- `recommendations[].candidate_id` 必须来自冻结候选快照。
- 推荐不得重复，不得包含已归档或已订阅候选。
- Telegram 回调必须校验目标用户 ID、会话有效期和当前榜单 `run_id`；旧榜单、越权用户和重复确认不得创建订阅。
- `confidence` 必须为 0 到 100 的整数。
- 每条作品 `reason` 与 `summary` 必须各自恰好十五个中文字符，不含英文、数字、标点或空白。
- 不输出 Markdown、自然语言前后缀、工具过程、推理过程或思维链。

## 状态与恢复

- 启用门禁：只有所有已选 Emby identity 的 Playback Reporting 探测为 `ready` 才允许运行；阻断状态保留配置意图、旧画像与旧榜单，并通过状态 API 返回原因。
- `playback_unavailable`：运行中播放依赖瞬时故障时停止本轮，不调用 Agent，不覆盖旧画像或旧榜单。
- `sample_insufficient`：播放样本不足，不调用 Agent。
- `candidate_insufficient`：发现候选不足，不调用 Agent。
- `candidate_filter_failed`：媒体库或全局订阅硬过滤无法可靠完成，不调用 Agent，也不保存风险候选快照。
- `candidate_snapshot_failed`：最终候选快照无法安全保存或回读，不调用排序 Agent，且不覆盖已有运行快照。
- `profile_agent_failed` / `profile_validation_failed` / `profile_save_failed`：画像阶段失败，保留旧画像与旧榜单。
- `ranking_agent_failed` / `ranking_validation_failed` / `ranking_save_failed`：排序阶段失败；新画像可以保留，但旧榜单不被覆盖。
- `validation_failed`：仅作为历史兼容状态，不作为生产组合输出链路。
- `recommendation_incomplete`：补选后仍不足五条，保存实际安全条数，不填充伪推荐。
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
