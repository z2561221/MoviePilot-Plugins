# AgentRank Agent Context

## 文档状态

本文是 Agent榜单中心 `v1.0.0` 专属影评师改造的目标契约，不代表所有条目已经落地。实际完成状态、验收证据和下一允许动作以 `ai_spec/v1.0.0_progress.json` 为准；实现不得通过缩减本契约来迁就当前代码。

## 插件用途

AgentRank 是 MoviePilot V2 本地插件。它按稳定 Emby identity 读取 Playback Reporting 播放快照，冻结 MoviePilot 发现候选，调用受限内置 Agent 生成用户画像与前 5 名榜单，再由确定性安全门保存榜单、通知或执行受控订阅。`v1.0.0` 在此基础上增加可审计的反馈事件、确认式长期记忆、确定性学习增量、结构化 Agent分析和专属影评师对话，使插件能持续贴近用户口味而不静默改写画像。

“符合用户心理”只表示依据可验证观看动机辅助软排序：情绪体验、认知满足、叙事投入、熟悉与新奇平衡、节奏与完成感。稳定动机必须有至少两条相互独立的播放证据，或一项用户明确添加/确认的偏好；单一样本不能形成稳定结论，弃看只能作为弱负向信号。禁止推断人格、焦虑、孤独、疾病、创伤等敏感心理状态。

## 运行边界

- 插件入口：`__init__.py`，只声明元数据、生命周期和扩展点。
- 推荐编排：`service/recommendation.py`，负责用户锁、播放快照、画像复用、候选冻结、一次补选、失败保留旧数据和分阶段保存。
- MP Provider：`adapter/discovery.py` 复用 DoubanChain、TmdbChain、BangumiChain；公共探索默认全局原始上限 150，并把 source、mode、method、params、limit 写入 request recipe。
- 依赖探测：`adapter/playback_reporting.py` 只返回 `ready`、`not_installed`、`permission_error`、`transient_error` 或 `emby_unavailable`，且不暴露 Emby 地址与凭据。
- Agent 适配：`adapter/agent.py` 中的 `RestrictedAgentRankAgent`，为画像、排序、反馈理解和影评师对话使用独立角色、独立 session 和 `ReplyMode.CAPTURE_ONLY`。
- 提示协议：`service/prompt.py`；画像提示只允许播放事实，排序提示只允许使用冻结候选、归档反馈、权重和当前画像；候选标题、简介、标签和归档文本始终是不可信数据。
- 检索计划模型：`model/retrieval.py`，固定媒体类型、TMDB 题材 ID、ISO 639-1 语言与合法排序集合。
- 受控解析：`service/keyword_resolution.py` 只把固定题材/语言别名或唯一可信 TMDB 关键词写入 filters；`adapter/tmdb_keyword.py` 通过宿主 `TmdbApi.search.keywords` 查询，不在 service 层直接发 HTTP。
- 输出解析与安全校验：`service/validation.py`；画像与排序分别使用独立 schema，只接受有界 JSON 对象，并保持排序 Agent 最终顺序。
- 订阅副作用：仅允许 `service/subscription.py` 在 Agent 已结束后执行，Agent 适配器不得持有该服务。
- Telegram 自选订阅：`service/telegram_interaction.py` 使用海报轮播和一次性会话令牌处理 `MessageAction`；按钮点击只维护待订阅清单，最终确认才调用 `service/subscription.py`。
- 用户动作：喜欢、不喜欢和忽略先写入幂等事件账本，再异步触发反馈理解；API 和页面不得等待 LLM。
- 记忆投影：Agent 只能输出复述、证据和变化提案；长期画像必须经过用户确认后由 `service/memory_projection.py` 投影。
- 确定性评分：十项配置权重继续作为基准，已确认学习只形成有界增量；最终顺序和推荐支持度由版本化评分器计算，不采用 LLM 自报置信度。

## Agent 角色与工具边界

现有画像和排序角色只允许以下四个只读工具，工具参数不能选择 username 或 run_id：

1. `read_agentrank_playback`
2. `read_agentrank_candidates`
3. `read_agentrank_archive_feedback`
4. `read_agentrank_weights`

受信上下文锁定本轮 profile_id、username、run_id 与 agent role。画像 Agent 只能加载 `read_agentrank_playback`，看不到候选、归档和权重；排序 Agent 才能加载四个工具。反馈理解和影评师对话角色只可增加显式注册的最小只读工具，用于读取当前事件、结构化分析、已确认记忆和待确认提案；不得把未确认提案或会话摘要冒充长期记忆。所有角色均禁止订阅、写插件数据、修改配置、访问文件、发送消息、加载外部 MCP、委派子代理或加载通用 ToolFactory 工具。

插件内置人设固定为谨慎、具体、尊重用户纠正的专属影评师。内置 skills 是插件内部版本化的无副作用分析程序：`summarize_evidence`、`understand_feedback`、`compare_conflicts`、`propose_memory_change`、`explain_recommendation`、`ask_clarification`；它们不等于 MoviePilot 通用动态技能，不自行调用外部工具。

画像 Agent 的播放工具返回当前播放快照、可选的上一版画像、人工画像标签偏好和当前只读画像。画像缓存开启、画像 schema 为当前版本且播放指纹未变化时直接复用画像，不调用画像 Agent；候选变化不能重写画像。旧 schema 画像必须先重建检索计划。播放指纹只由稳定播放事实构成，不包含 `synced_at` 等易变字段。

人工偏好必须参与画像与排序；人工避雷与未被归档的 Agent 负向标签作为插件硬过滤关键词。删除标签写入保留原类别的归档，标签偏好指纹变化必须使画像缓存失效；画像保存、检索计划和排序上下文都不得重新使用归档标签。禁止用标签集合并集替代画像更新。

已删除、已纠正或被新判断替代的标签和记忆必须保留墓碑、`supersedes` 与单调递增 `memory_revision`。事件按 profile_id 的单调 sequence 重放；旧 LLM 回调、重复确认和乱序结果不得覆盖新 revision，也不得让归档标签复活。

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
- Agent 排序或唯一补选失败、校验失败、数量不足时，对冻结安全候选使用同一确定性评分器补齐至五条；补位不得新增 Agent 调用、不得编造观看经历，并继续排除已观看、已入库、已订阅、已忽略和已不喜欢候选。只有完成全部硬过滤后确实不足五条才允许少于五条，并明确返回 `safe_candidate_insufficient`。
- Telegram 回调必须校验目标用户 ID、会话有效期和当前榜单 `run_id`；旧榜单、越权用户和重复确认不得创建订阅。
- 旧 `confidence` 字段只作 schema 迁移兼容；对外百分比是 0 到 100 的整数推荐支持度，可由受信证据贡献和 `policy_version` 确定性重算，不能来自 LLM 自报信心。
- 每条作品 `reason` 与 `summary` 必须分别是不超过 30 个中文字符的完整语义总结。校验失败时最多定向重写一次，再失败使用确定性模板重述；禁止用字符串截断制造残句或丢字。
- 每条作品可保存结构化 `AgentAnalysis`，只包含具体匹配证据、反证、不确定点、确定性贡献、memory revision 和 policy version。不得输出或保存 Markdown 前后缀、隐藏提示、工具过程、token、原始推理过程或思维链。

## 反馈、记忆与对话协议

- 喜欢是强正向事件；条目保留在当前榜单。它可以生成长期偏好提案，但必须经用户确认才投影。
- 不喜欢是强负向事件；作品立即移出当前榜单和补位池，并用冻结安全候选补齐。题材、主创或观看动机层面的长期负向仍须确认。
- 忽略只排除当前作品，不代表讨厌，不生成权重或口味增量；无评论的纯忽略理解结果固定为 `exclusion_only`。
- 每个动作都异步触发受限反馈理解。理解明确时生成“复述 -> 变化预览 -> 用户确认”的 `MemoryProposal`；不明确时生成 `PendingQuestion`，提供 2 至 3 个选项和自定义回答。
- 用户可立即回复、选择 1/3/7 天后提醒或不提醒。未回复、拒绝、超时和不提醒均不改变长期画像；待确认项仍可稍后从详情页继续回答。
- 每条 Agent 判断都可评论。评论绑定 `analysis_id` 并生成新事件；旧分析保留审计记录并由新分析 `supersedes`，不得原地篡改历史。
- 专属影评师对话只读播放事实、冻结候选、结构化分析和已确认记忆。任何标签、权重、忽略、订阅、重置等写请求都只能形成待确认命令，确认后由对应 service 执行。

## 鉴权、订阅与模型溯源

- 所有 bear API 必须取得 `TokenPayload = Depends(verify_token)` 并执行 profile 访问校验。超级用户可访问全部已配置 profile；普通用户只可访问 `profile_access_map[str(token.sub)]` 显式授权的 profile，默认空集合，不使用用户名模糊匹配或默认 profile 回退。
- `nativeSubscribe()` 成功返回只表示 MoviePilot 原生订阅交互已接管或抽屉已打开，不代表订阅实际创建。归因必须复查订阅状态；取消抽屉不得记录成功。
- 订阅、入库和播放采用单调状态归因：`native_drawer_opened -> subscription_observed -> library_observed -> playback_observed`。读取失败保持 `verification_pending`，不得猜测成功。
- Agent Tokens 管理插件是可选接管层。安装并接管时记录其实际供应商/模型；未安装、未接管或不可用时沿 MoviePilot 内置 Agent 选择链回退系统 LLM，并标记来源 `moviepilot_system`。
- 运行历史主列表显示实际供应商和模型名；调用次数、token 和每阶段耗时放在展开详情。来源无法解析时显示“模型来源未返回”，不能用调用次数代替模型名。

## 数据生命周期与界面契约

- 反馈事件按 profile_id 分段保存，具有幂等键、单调 sequence 和保留策略；候选快照、队列、事件、对话和归因数据不得无限增长。
- 提供脱敏导出、仅重置学习和彻底重置。彻底重置需要二次确认，且不能删除 MoviePilot 订阅或媒体库数据；任何导出不得包含 token、Cookie、Authorization、Emby 地址、LLM key 或原始思维链。
- 仪表盘、详情页和发现页在安全候选充足时都展示完整五条。每条仅保留订阅、TMDB、忽略及图标化喜欢/不喜欢；百分比靠右且不显示“置信度”文字。
- 推荐和简介自然换行完整展示，不使用展开/收起或 CSS 截断。详情页功能区移除“运行就绪”，移动端自适应换行。
- 喜欢/不喜欢图标必须靠形状、填充和 `aria-pressed` 区分，不能只依赖绿色点赞/红色点踩；按钮无可见名称但必须有 tooltip 和 aria-label。
- 结构化 Agent分析、逐条评论、专属影评师对话和待确认均提供独立窗口；移动端对话使用全屏布局。

## 状态与恢复

- 启用门禁：只有所有已选 Emby identity 的 Playback Reporting 探测为 `ready` 才允许运行；阻断状态保留配置意图、旧画像与旧榜单，并通过状态 API 返回原因。
- `playback_unavailable`：运行中播放依赖瞬时故障时停止本轮，不调用 Agent，不覆盖旧画像或旧榜单。
- `sample_insufficient`：播放样本不足，不调用 Agent。
- `candidate_insufficient`：发现候选不足，不调用 Agent。
- `candidate_filter_failed`：媒体库或全局订阅硬过滤无法可靠完成，不调用 Agent，也不保存风险候选快照。
- `candidate_snapshot_failed`：最终候选快照无法安全保存或回读，不调用排序 Agent，且不覆盖已有运行快照。
- `profile_agent_failed` / `profile_validation_failed` / `profile_save_failed`：画像阶段失败，保留旧画像与旧榜单。
- `ranking_agent_failed` / `ranking_validation_failed`：仅在冻结候选不足以完成本地保底时返回；候选充足时保存五条新榜单并在 metrics 记录保底原因。
- `ranking_save_failed`：榜单保存失败；新画像可以保留，但旧榜单不被覆盖。
- `validation_failed`：仅作为历史兼容状态，不作为生产组合输出链路。
- `recommendation_incomplete`：上游有效冻结候选本身不足五条时保存实际安全条数，不编造候选。
- `subscription_partial_failed`：自动订阅逐条继续，成功项保留，失败项进入运行历史。
- `feedback_queued`：动作已落账并等待异步理解，不表示记忆已改变。
- `feedback_needs_attention`：LLM 有界重试耗尽，作品级即时动作保留，长期记忆不变并通知用户。
- `memory_revision_conflict`：旧提案或乱序确认不能投影，保留新 revision 并记录 superseded。
- `attribution_verification_pending`：订阅、入库或播放状态暂不可读，保持上次可信状态。

## 验收

- `python -m compileall -q plugins.v2/agentrank`
- `pytest --confcutdir=plugins.v2/agentrank/tests --import-mode=append plugins.v2/agentrank/tests -q`
- `pytest --confcutdir=tests/static tests/static/test_agentrank_contracts.py tests/static/test_agentrank_frontend_contracts.py -q`
- `plugins.v2/agentrank/tests/test_agent_evals.py` 与新增专属影评师 eval 聚合正常排序、权重变化、喜欢/不喜欢/忽略、单样本、独立证据、弃看弱负向、敏感心理推断、提示注入、越池候选、非法 JSON、乱序记忆和补选不足场景。
- Vue 联邦 build 必须产生 `dist/assets/remoteEntry.js`；390x844、768x1024、1440x900 三个视口均须验证五条显示、自然换行、评论/对话和操作按钮无重叠。

## 禁止范围

- 不修改 MoviePilot core 或 MoviePilot-Frontend。
- 不把真实用户画像、token、Cookie、Authorization header 或本地秘密写入源码、测试和运行历史。
- 不展示、保存或提供原始思维链；只展示可纠正的结构化 Agent分析。
- 不让 Agent 直接写存储、订阅、通知、配置、文件或外部系统。
- 不在未获用户确认时 push、PR、merge、release 或发布。
