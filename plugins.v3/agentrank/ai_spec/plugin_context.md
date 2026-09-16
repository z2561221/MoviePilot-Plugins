# Agent榜单中心稳定上下文

## 插件定位

`AgentRank` 是 MoviePilot V3 Vue 联邦插件。它以 Emby 播放事实、用户确认偏好和候选媒体事实为输入，调用受限 Agent 生成个性化 Top 5 榜单，并提供反馈学习、对话、待确认中心、订阅归因和历史追踪。

插件 ID 为 `AgentRank`，源码位于 `plugins.v3/agentrank`，生产导入命名空间为 `app.plugins.agentrank`，入口类为 `AgentRank`，配置前缀为 `agentrank_`。当前运行模式为 `("vue", "dist/assets")`。

本周期开发版本为 `3.0.6`。Telegram 重试会话持久化原消息来源、消息 ID、聊天 ID 与重试代次。同一轮及其重试仅发送一条通知，受理后移除按钮，后台每 5 秒合并真实阶段并调用宿主 `edit_message` 原地更新；成功显示结果，失败恢复下一代重试按钮，编辑失败不降级为新消息。重试仍使用有界后台线程，停止时取消任务与进度发布器。媒体库状态仍使用 `true`、`false`、`null` 区分存在、不存在与查询失败，排除已入库时拦截未知状态。

## 入口与生命周期

- `init_plugin()` 委托 `service/lifecycle.py::initialize_plugin()`：规范化配置、执行存储迁移、探测 Playback Reporting 硬依赖并创建 `AgentRankRuntime`。
- `get_service()` 委托运行时返回周期榜单服务；计划由 `schedule_enabled` 和 `cron` 控制。
- `EventType.MessageAction` 只处理当前实例 ID 的 Telegram 回调；运行重试交给 `service/telegram_retry.py`，榜单与待办按钮继续使用原交互服务。
- `get_sidebar_nav()` 在插件启用且 `discovery_page_enabled=true` 时提供发现区入口。
- Vue 联邦暴露 `./Page`、`./Config`、`./Dashboard` 和 `./AppPage`，构建产物必须完整保留在 `dist/assets`。
- 前端 API 由 `controller/routes.py::build_api_routes()` 统一注册，端点绑定位于 `controller/endpoints.py`，并全部声明为 `auth: "bear"`。浏览器端只能使用宿主注入的 `api` 客户端，且必须以宿主传入的 `pluginId` 组装当前实例路由。

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

通用只读工具为：

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
& 'D:\AIGC\MoviePilot\.venv-test\Scripts\python.exe' -m compileall -q plugins.v3\agentrank
& 'D:\AIGC\MoviePilot\.venv-test\Scripts\python.exe' -m pytest -q tests\v3\agentrank
pnpm --dir plugins.v3\agentrank\frontend build
git diff --check
```

完整本地闭环为：聚焦测试 -> 开发技能 `accept_local.py` 同步与必要本地安装 -> `POST /api/v1/plugin/reload/AgentRank` -> `/api/v1/plugin/history/AgentRank`、installed、状态/overview 和静态资产回读。页面桌面与移动端验收由用户完成。

常见坑：

- 插件仓没有 MoviePilot 后端 `app/` 时，直接运行完整 pytest 会在收集阶段失败；应使用准备好的隔离环境或测试镜像，不能把环境失败报告成产品失败。
- 当前 V3 宿主的 reload endpoint 使用 POST；宿主发生变化时先回读目标 OpenAPI。
- MP 本地源仍存在时，history 显示 `local://` 属于预期，不能为了改变来源显示而删除本地插件。
- 文件同步和哈希一致只证明文件状态；reload、history、API 与 installed 回读共同验证运行态，页面交互另列验收结果。
