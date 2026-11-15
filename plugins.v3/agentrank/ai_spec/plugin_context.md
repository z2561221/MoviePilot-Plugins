# Agent榜单中心稳定上下文

## 插件定位

`AgentRank` 是 MoviePilot V3 Vue 联邦插件。它以 Emby 播放事实、用户确认偏好和候选媒体事实为输入，调用受限 Agent 生成个性化 Top 5 榜单，并提供反馈学习、对话、待确认中心、订阅归因和历史追踪。

插件 ID 为 `AgentRank`，源码位于 `plugins.v3/agentrank`，生产导入命名空间为 `app.plugins.agentrank`，入口类为 `AgentRank`，配置前缀为 `agentrank_`。当前运行模式为 `("vue", "dist/assets")`。

当前版本以 `__init__.py` 的 `plugin_version`、`plugin.json` 和 `package.v3.json` 的 `AgentRank` 条目为准，变更说明见 [README](../README.md)。Agent 修正回合使用新对象，兼容宿主 cleanup 永久关闭任务作用域的行为；内部受信工具不向普通聊天注册。Telegram 重试会话持久化原消息来源、消息 ID、聊天 ID 与重试代次。同一轮及其重试仅发送一条通知，受理后移除按钮，后台每 5 秒合并真实阶段并调用宿主 `edit_message` 原地更新；成功显示结果，失败恢复下一代重试按钮，编辑失败不降级为新消息。重试仍使用有界后台线程，停止时取消任务与进度发布器。媒体库状态仍使用 `true`、`false`、`null` 区分存在、不存在与查询失败，排除已入库时拦截未知状态。

## 入口与生命周期

- `init_plugin()` 委托 `service/lifecycle.py::initialize_plugin()`：规范化配置、执行存储迁移、探测 Playback Reporting 硬依赖并创建 `AgentRankRuntime`。
- `get_service()` 委托运行时返回周期榜单服务；计划由 `schedule_enabled` 和 `cron` 控制。
- `EventType.MessageAction` 只处理当前实例 ID 的 Telegram 回调；运行重试交给 `service/telegram_retry.py`，榜单与待办按钮继续使用原交互服务。
- `get_sidebar_nav()` 在插件启用且 `discovery_page_enabled=true` 时提供发现区入口。
- Vue 联邦暴露 `./Page`、`./Config`、`./Dashboard` 和 `./AppPage`，构建产物必须完整保留在 `dist/assets`。
- 前端 API 由 `controller/routes.py::build_api_routes()` 统一注册，端点绑定位于 `controller/endpoints.py`，并全部声明为 `auth: "bear"`。浏览器端只能使用宿主注入的 `api` 客户端，且必须以宿主传入的 `pluginId` 组装当前实例路由。
- 推荐卡片的原生订阅类型与 TMDB 详情路径共用 `nativeMediaType`：优先读取 `candidate_id` 的 `tmdb:movie:` / `tmdb:tv:` 身份，再读取条目或 metadata 的 `mp_media_type`，最后使用 `media_type` 回退。`anime` 是推荐分类，不能覆盖已确定的电影身份。原生订阅拒绝、取消或异常时停止；仅在宿主未提供原生入口时转入插件订阅链。

## 性能读取边界

- 榜单页面调用 `config/options?discover=false`，只读取已配置身份；设置页保留默认完整 Emby 用户和媒体库发现。
- 仪表板只读取 `board`，详情页继续读取 `overview`；两类缓存按实例和画像分别保存，变更同时失效，迟到旧请求重新取得当前数据。普通赞踩局部更新，不立即重拉总览。
- 历史榜单只序列化当前页，消费记录一次读取；候选重合及历史再推荐统计仍参照全部保留轮次。
- 播放详情只补齐缺少的名称和 TMDB ID，补查最多四路，批量结果之外的条目不补入。反馈投影仅在仓库实例内缓存最多八个榜单，按序号增量读取；裁剪、重置或恢复后重建，完整复核期限为一分钟且不因追加而延长。持久化 key 和格式保持原合同。

## 结构与资源职责

- `storage/locks.py` 按插件数据域共享在用锁。已核验宿主 `44606a` 的原生数据接口以实例类名隔离；自定义数据替身按对象身份隔离。同数据域的多个 repository 共锁，不同实例互不争用。弱引用注册表在持有者、等待者和外部引用都结束后释放条目；禁止在删除画像时直接移除在用锁。复合动作保留榜单锁、画像锁、Telegram 锁的原有顺序。
- `storage/feedback_projection.py` 独立拥有最多八个榜单的 LRU 和具名赞踩快照。同画像共享一个账本索引，追加同时推进其已有投影；完整读取、裁剪、恢复和损坏各自维护版本与失效。60 秒是读取时的完整重验证期限，物理释放依靠 LRU、失效或生命周期关闭。
- `service/board_history.py` 通过四个只读仓库入口生成分页和比较摘要。controller 负责鉴权、快照序列化和响应组装，保留所有原有 DTO 字段、历史回退和跨页统计。
- `service/lifecycle.py` 停止旧 runtime 后调用仓库 `release_read_caches()`。关闭的缓存禁止迟到读取重新发布数据；持久化读取仍可用，重新初始化使用新的 repository/cache。普通停用和 reload 不迁移或删除持久化数据。

## 推荐主链

1. Playback Reporting 探测通过后，按 `profile_id` 冻结最近播放快照。
2. 画像 Agent 从播放事实和已确认偏好生成稳定画像；单一样本不得形成稳定结论。
3. 检索 Agent 只能从豆瓣、TMDB 电影、TMDB 剧集、Bangumi 和 AniList 中选择受控动作，并提交严格 `RetrievalPlan`。
4. 宿主执行精确、放宽、相邻题材和播放种子推荐四层召回，完成来源规范化、TMDB 识别、跨来源去重和硬过滤，冻结 10 至 15 条候选。
5. 初赛 Agent 分批提交候选判断，决赛 Agent 只能在冻结决赛候选中生成榜单。
6. `RecommendationValidator` 校验 `candidate_id`、证据、归档、观看状态、重复项和输出数量；安全补位也只能使用冻结候选。
7. 成功榜单固定保存 5 条；证据合格但不足 5 条时使用 `recommendation_incomplete`，不得伪造候选补满。

## Agent 运行边界

运行时使用 `RestrictedAgentRankAgent`，并强制 `ReplyMode.CAPTURE_ONLY`。每个角色只实例化角色白名单工具，会话结果由提交工具捕获，结束后清理隔离会话和记忆。

以下只读工具仅供插件内部角色使用，`get_agent_tools()` 返回空列表，不向普通聊天或通用 Agent 公开：

- `read_agentrank_playback`
- `read_agentrank_candidates`
- `read_agentrank_archive_feedback`
- `read_agentrank_weights`

角色专用链路为：

- 画像：`read_agentrank_profile_context` -> `submit_agentrank_profile_result`
- 检索：`read_agentrank_retrieval_context` -> `submit_agentrank_retrieval_plan`
- 初赛：`read_agentrank_batch_context` -> `submit_agentrank_batch_result`
- 决赛：`read_agentrank_final_context` -> `submit_agentrank_final_board`
- 反馈与对话角色只能读取各自冻结上下文，不能获得通用 MoviePilot Agent 工具。

提交失败至多修正一次。宿主 `cleanup()` 永久关闭 Agent 任务身份，禁止再次调用该对象的 `process()`。修正前完成旧对象清理，再创建仅含提交工具的新对象，复用本轮 trusted context 与结果收集器。无渠道后台会话不持久化历史，修正请求必须显式携带相同工具投影生成的角色快照、提交 schema 与有界前轮输出，不能凭相同 session_id 假设证据仍存在。画像、检索和初赛保留原会话标识，决赛沿用独立 `_repair` 会话策略。结束后清理所有创建的对象并按唯一 session_id 清除记忆，模型调用次数合并统计。

`AgentRankProtocolMiddleware` 在读取前只开放该角色的快照工具，读取后只开放提交工具，并指定当前工具。只有供应商明确以 400/422 拒绝 `tool_choice` 参数时才降级一次，白名单保持不变，其它异常不自动重试。终结角色重复读取仍先验证身份和作用域，随后返回 `already_read` 与提交工具名，不消耗修正次数，也不返回新的快照。原有 schema、候选范围和证据校验继续生效。

运行历史对每次 Agent 调用记录有限的 `failure_class`、`repair_kind` 和 `repair_recovered`，并汇总首轮成功、修正成功、终止失败及按角色结果。分类只用于过程观测，不替代错误原文脱敏，也不改变失败恢复策略。

所有候选标题、简介、标签、对话和来源文本均视为不可信数据，不能覆盖系统协议。Agent 禁止订阅、写配置、写文件、直接发消息、执行命令或调用任意网络工具；订阅只能经用户动作和宿主 API 安全链执行。

推荐理由和作品简介必须分别是不超过 30 个中文字符的完整短句，禁止按字符截断。Agent 只能引用上下文提供的可验证证据，不能输出思维链、系统提示词或未提供的候选。

## API 分组

- 运行与配置：`/status`、`/overview`、`/config/options`、`/run-progress`、`/refresh`。
- 榜单与画像：`/board`、`/profile`、`/playback/sync`、`/run-history`、`/board-history`、`/learning-health`。
- 反馈与分析：`/archive`、`/restore`、`/feedback`、`/analysis`、`/analysis/comment`、`/profile/tags`。
- 对话与待办：`/conversation*`、`/pending*`。
- 归因与消费：`/attribution*`、`/consumption/*`、`/subscribe`。
- 数据治理：`/data/export`、`/data/reset/learning`、`/data/reset/full/prepare`、`/data/reset/full`。

状态变更 API 必须校验显式 `profile_id`；任一已登录 MoviePilot 用户都可访问全部已配置画像。危险操作仍按操作者身份执行确认和审计。

## 持久化边界

`AgentRankRepository` 通过 `_PluginBase.get_data()`、`save_data()` 和 `del_data()` 维护按 `profile_id` 隔离的数据。关键前缀和固定 key 包括：

- `profile_snapshot`、`profile_preferences`、`playback_snapshot`
- `recommendation_board`、`board_history`、`candidate_snapshot`、`candidate_snapshot_index`
- `feedback_event`、`feedback_queue`、`short_term_signals`
- `preference_memory`、`memory_proposals`、`pending_questions`
- `conversation`、`conversation_messages`、`conversation_reads`
- `policy_snapshot`、`adaptive_fingerprints`、`learning_health`
- `attribution`、`agent_analysis`、`board_consumption`
- `telegram_selection_sessions`、`telegram_pending_session`、`telegram_retry_sessions`
- `agentrank_recovery_log`、`full_reset_confirmation`

这些 key 属于兼容契约。修改前必须同时检查迁移、数据生命周期、导出/重置和回滚逻辑，禁止直接改名或改变画像隔离格式。

## 禁止改动区域

- 禁止让 Agent 获得订阅、写配置、文件、命令、消息或任意网络副作用能力。
- 禁止绕过 `candidate_id` 白名单、冻结候选、证据校验和归档墓碑。
- 禁止把评分、热度、观看动机或模糊偏好升级为无证据硬过滤。
- 禁止因候选不足放宽“排除已观看媒体”等宿主硬约束。
- 禁止在浏览器端注入 API Token，禁止绕过 bearer API 和画像授权。
- 禁止只修改 `frontend/src` 而不重建 `dist/assets`。
- 开发周期版号与 history 按工作区已授权的版本预检规则维护；push、合并或发布须有对应的明确授权。

## 验收方式与常见坑

从仓库根目录执行。先把 `MOVIEPILOT_BACKEND_PATH` 设为已核验的 V3 宿主 checkout 绝对路径，使用共享测试解释器和已安装的 Node.js：

```powershell
Remove-Item Env:CONFIG_DIR -ErrorAction SilentlyContinue
$env:DB_TYPE = 'sqlite'
& 'D:\AIGC\All In Docker\MoviePilot\.venv-test\Scripts\python.exe' -m compileall -q plugins.v3\agentrank
& 'D:\AIGC\All In Docker\MoviePilot\.venv-test\Scripts\python.exe' -m pytest -q tests\v3\agentrank
pnpm --dir plugins.v3\agentrank\frontend build
git diff --check
```

完整本地闭环为：聚焦测试 -> 开发技能 `accept_local.py` 同步与必要本地安装 -> `POST /api/v1/plugin/reload/AgentRank` -> `/api/v1/plugin/history/AgentRank`、installed、状态/overview 和静态资产回读。页面桌面与移动端验收由用户完成。

常见坑：

- 插件仓没有 MoviePilot 后端 `app/` 时，直接运行完整 pytest 会在收集阶段失败；应使用准备好的隔离环境或测试镜像，不能把环境失败报告成产品失败。
- 当前 V3 宿主的 reload endpoint 使用 POST；宿主发生变化时先回读目标 OpenAPI。
- MP 本地源仍存在时，history 显示 `local://` 属于预期，不能为了改变来源显示而删除本地插件。
- 文件同步和哈希一致只证明文件状态；reload、history、API 与 installed 回读共同验证运行态，页面交互另列验收结果。
