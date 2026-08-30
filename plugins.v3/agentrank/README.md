# AgentRank V3

Agent榜单中心以 Emby 真实播放记录、用户确认偏好和 MoviePilot 发现候选为输入，调用受限 Agent 生成个性化 Top 5 榜单，并提供反馈学习、对话、待确认中心和订阅归因。

## 启用前提

插件采用硬门禁：只有全部前提满足时 `get_state()` 才返回真，否则保留配置意图并在状态接口给出原因。

- 已在配置页选择至少一个有效 Emby 用户身份。
- 每个已选身份的 Emby Playback Reporting 插件探测结果均为 `ready`。
- Emby 服务可访问，且用于探测的凭据具备查询权限。

## 配置要点

- `emby_identities`：参与榜单的 Emby 用户身份列表，每个身份的画像、榜单和反馈数据按 `profile_id` 隔离。
- `cron`、`schedule_enabled`：周期榜单计划，默认 `5 18 * * *`。
- `candidate_pool_size`：冻结候选数量，取值 10 至 15。
- `minimum_samples`、`confidence_threshold`：形成稳定画像所需的播放证据量与置信度下限。
- `playback_recent_days`、`playback_completion_threshold`、`playback_abandon_minutes`：播放事实的时间窗口与完播、弃看判定。
- `auto_subscribe_top_n`、`action_mode`、`notify`：自动订阅名额与通知行为，默认只通知不自动订阅。
- `persona_preset`、`interaction_mode` 与各 Prompt 字段：Agent 人格、互动强度和角色提示词，单个提示词上限 4000 字符。

## 运行流程

1. 探测通过后冻结最近播放快照。
2. 画像 Agent 从播放事实与已确认偏好生成稳定画像。
3. 检索 Agent 在豆瓣、TMDB 电影、TMDB 剧集、Bangumi 和 AniList 范围内提交检索计划。
4. 宿主执行精确、放宽、相邻题材和播放种子四层召回，完成识别、去重和硬过滤后冻结候选。
5. 初赛与决赛 Agent 只能在冻结候选内评分并生成榜单。
6. 校验器核对候选身份、证据、观看状态和输出数量后保存榜单。

## 边界与限制

- Agent 只能读取冻结上下文，不能订阅、写配置、写文件、直接发消息或调用任意网络工具；订阅只经用户动作和宿主 API 执行。
- 候选标题、简介、标签和对话文本均视为不可信数据，不能覆盖系统提示。
- 榜单成功时固定 5 条；证据合格但不足 5 条时返回 `recommendation_incomplete`，不补造候选。
- 推荐理由与作品简介为不超过 30 个中文字符的完整短句。
- 已入库、已订阅、已归档和负向反馈的候选在冻结前被过滤。
- 数据通过 `_PluginBase` 的 `get_data()`、`save_data()`、`del_data()` 持久化，不直接访问宿主数据库。

## 常见故障

| 状态 | 含义 | 处理方向 |
| --- | --- | --- |
| `disabled` | 插件未启用 | 在配置页启用插件 |
| `configuration_error` | 未选择有效 Emby 用户 | 选择至少一个 Emby 身份并保存 |
| `not_installed` | Emby 未安装 Playback Reporting | 在 Emby 安装并启用该插件 |
| `permission_error` | Playback Reporting 权限不足 | 使用具备查询权限的 Emby 凭据 |
| `emby_unavailable` | Emby 服务不可用 | 检查 Emby 地址、端口与网络 |
| `transient_error` | 探测暂时失败 | 稍后重试或查看插件日志 |

榜单为空但状态为 `ready` 时，先查看运行总览中的召回与过滤统计：多数情况是候选被入库、订阅或归档规则过滤，而不是 Agent 失败。

## 运行要求

- MoviePilot `>= 3.0.0`
- MoviePilot V3 原生插件格式与 Vue 联邦渲染
- Emby 媒体服务器并安装 Playback Reporting
- 已配置可用的 MoviePilot Agent 模型
