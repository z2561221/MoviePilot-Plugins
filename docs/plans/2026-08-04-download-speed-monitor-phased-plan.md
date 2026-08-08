# DownloadManagerLocal 下载速度异常监控分阶段计划

## 目标

为 `DownloadManagerLocal` 增加可选的下载速度异常监控闭环，覆盖 qBittorrent、Transmission 和多个下载器选择场景，不依赖转种流程。插件在任务被观察到开始下载时建立监控会话，在完成、删除或明确终止时结束会话并统计有效平均速度；当任务在基准或手动阈值规定的时间内仍未完成时，按 MoviePilot 通知分类发送异常通知，并在 Telegram 通知中提供“关闭”和“删除”交互。

“运行总览”的运行链路只展示本插件内部处理，不把订阅助手画成内部节点。订阅助手只在配置页的删除行为说明中作为可选外部联动出现：本插件经 Telegram 明确确认后删除种子及该种子的全部数据，订阅助手增强版自行监听删除事件并按自身规则清理、重试或换种。本计划不修改订阅助手。

## 规格审查

状态：Ready，可以进入分阶段实现。

已锁定的产品决策：

- 监控下载器由用户自由选择，至少支持 qBittorrent、Transmission，并按下载器实例分别统计。
- 监控不依赖转种，也不要求任务经过本插件的转移流程。
- 任务首次被监控到有效下载时创建会话；暂停、排队、校验和无效状态不计入有效下载时长。
- 自动模式使用每个下载器自己的健康完成样本；至少积累 5 个有效完成任务后才允许自动告警。
- 手动模式使用用户为下载器设置的最低期望速度，不等待历史样本；仍遵守启动宽限和连续异常采样次数。
- 容忍倍数可配置，默认 `1.5`。参考速度对应的预期完成时长乘以该倍数得到允许时限。
- 基准使用稳健统计，不使用简单平均；超时、手动删除、错误、无有效速度的任务不得污染健康基准。
- 自动模式支持按下载器实例设置可选的速度保护下限，默认不填写；填写后实际参考速度取“自动稳健基准”和该下载器保护下限的较大值，不设置时只判断相对历史异常。
- 默认采样间隔 `5` 分钟、启动宽限 `10` 分钟、连续异常 `2` 次、自动模式最小样本数 `5`。
- 通知类型使用 MP 主程序的 `NotificationType` 分类，默认 `NotificationType.Plugin`，配置页允许选择其他合法分类。
- Telegram 异常通知提供“关闭”和“删除种子及全部数据”；删除必须二次确认，并且固定删除种子及该种子的全部数据。
- “关闭”只确认并收束当前告警，不删除任务、不停止下载；同一 hash 在同一异常周期内不重复通知，任务恢复到正常/完成后重新进入异常周期时允许再次通知。
- 插件不自动静默删除任务、不直接搜索换种；换种由订阅助手增强版是否监听删除事件决定。

非阻塞的实现核验项：

- Phase 1 通过 MoviePilot 当前 `EventType.MessageAction` 和 `post_message` 约定确认 Telegram 回调字段、原消息收束方式和 Telegram 用户身份字段。
- Phase 1 通过 qBittorrent、Transmission 适配器及测试替身确认状态、字节计数、加入时间和 `delete_file=True` 的具体字段。核验结果只能细化实现，不改变上述产品决策。

## 来源文档

- `D:/AIGC/MoviePilot/AGENTS.md`
- `D:/AIGC/MoviePilot/.agents/skills/create-moviepilot-plugin/SKILL.md`
- `D:/AIGC/MoviePilot/MoviePilot-Plugins/docs/faq/01-extend-notification-channel.md`
- `D:/AIGC/MoviePilot/MoviePilot-Plugins/docs/faq/02-remote-command-handler.md`
- `D:/AIGC/MoviePilot/MoviePilot-Plugins/plugins.v2/agentrank/__init__.py`
- `D:/AIGC/MoviePilot/MoviePilot-Plugins/plugins.v2/agentrank/service/telegram_interaction.py`
- `docs/plans/2026-07-04-downloadmanagerlocal-plugin-standard-completion-phased-plan.md`
- 当前用户确认的速度监控、Telegram 交互、删除全量数据和订阅助手联动要求

## 执行规则

- 工作目录固定为 `D:/AIGC/MoviePilot/.worktrees/downloadmanagerlocal-release`。
- 使用现有长期分支 `worldlinefix/downloadmanagerlocal`；当前干净基线保留已有 qB2 修复 commit `be446255`，不创建临时分支，不回退其他提交。
- 仅实现本计划范围，禁止修改 `SubscribeAssistantEnhanced` 或其他插件；禁止为本功能升级版本号、更新发布历史、推送、合并、发布或重启 MoviePilot。
- 每个任务只运行与当前改动相关的窄验证；每个 Phase 开始时运行一次基线 smoke check，只有触及共享边界或窄验证失败时才重复基线检查。每个通过验证的任务单独提交，并把 commit、验证命令和证据写入进度 JSON。验证失败不得提交。
- 阶段验收全部通过后自动进入下一阶段，不在阶段之间等待用户确认；只有发现产品决策与本计划冲突、或存在无法隔离的外部工作区改动时停止并报告。
- 真实下载器上的删除属于破坏性操作。自动化测试只使用 fake qBittorrent/Transmission；MP 运行验收只验证“将调用 `delete_file=True`”的模拟路径，不删除用户真实种子，除非用户另行明确授权。

验证节奏：任务级只做自动化窄测试，Phase 级做一次汇总验收，完整静态/构建/运行态审计统一放在 Phase 5.3；中间不插入人工审计、不暂停等待确认。

## `/goal` 协议

执行代理每轮必须：

1. 先读取 `docs/plans/2026-08-04-download-speed-monitor-progress.json`，只处理当前任务。
2. 每个 Phase 首个任务运行 `git status --short --branch`、`git log --oneline -15` 和本计划的 baseline smoke check；同一 Phase 后续任务运行当前任务的窄验证，发现共享基线失败再补跑 smoke check。
3. 只修改当前任务声明的文件和测试；不得顺手重构无关模块。
4. 通过窄验证后先更新进度 JSON 的状态、证据、commit 和 turn log，再提交当前任务；不得在验证失败时提交。
5. 当前阶段验收通过后直接进入下一阶段，不询问“是否继续”。

进度 JSON 的任务定义、验收条件、执行规则和阶段结构是只读契约；执行期间只允许翻转任务状态、填写验证和 commit、追加决策/回合日志及残余风险。任务之间不做重复完整审计，完整审计只在 Phase 5.3 收尾。

## 进度文件

`docs/plans/2026-08-04-download-speed-monitor-progress.json`

## 实现面图

| 边界 | 预计文件/模块 | 责任 |
| --- | --- | --- |
| 插件入口与生命周期 | `plugins.v2/downloadmanagerlocal/__init__.py`, `utils/config.py`, `service/lifecycle.py`, `service/scheduler.py`, `service/events.py` | 注册监控服务、独立判断监控启停、启动/停止生命周期、转发 `MessageAction` 回调；不承载算法细节 |
| 配置与状态 | `service/config.py`, `model/state.py` | 默认值、配置校验、会话/基准/告警持久化 key |
| 下载器适配 | `utils/torrent_adapter.py`, `adapter/moviepilot.py` | qB/TR 字段归一化、状态分类、字节和时间读取、区分空列表与 API 错误、删除任务及文件的调用边界 |
| 监控与统计 | 新增 `service/speed_monitor.py`, `service/speed_baseline.py` | 采样、有效时长、会话生命周期、健康样本和异常判断 |
| 通知与动作 | 新增 `service/speed_notification.py` | MP 分类解析、TG 卡片、回调 token、关闭/二次确认/删除幂等处理 |
| API 与总览 | `controller/handlers.py`, `controller/api.py`, `api.py` | 总览卡片、监控状态/基准摘要、必要的手动重置入口；保持现有 API 兼容 |
| 配置页 | `frontend/src/components/Config.vue`, `frontend/src/components/api.js`, `dist/assets/**` | 监控配置、删除种子及全部数据警告、外部联动说明、仅展示本插件内部运行链路 |
| 测试 | `tests/static/test_downloadmanagerlocal_speed_monitor_*.py`, `plugins.v2/downloadmanagerlocal/tests/test_speed_monitor*.py` | 静态契约、qB/TR 替身、统计算法、回调安全、前端文案和构建契约 |

## 运行链路与所有权

监控服务的内部数据流如下：

```text
选择的 qB/TR 下载器
        |
        v
下载器字段归一化 -> 监控会话 -> 有效采样/暂停排除 -> 自动基准或手动阈值
                                                   |
                         +-------------------------+------------------------+
                         |                                                  |
                    任务完成                                             连续异常
                         |                                                  |
                         v                                                  v
             统计有效平均速度并更新健康基准                 MP 分类通知 + Telegram 交互
                                                                                |
                                                        +-----------------------+------------------+
                                                        |                                          |
                                                     关闭                                     删除并清理
                                                        |                                          |
                                            确认告警、停止重复通知                 二次确认 -> delete_file=True
```

配置页“运行总览”的运行链路固定展示：

`下载任务 -> 监控会话 -> 有效采样 -> 基准/手动阈值 -> TG 通知 -> 关闭 / 删除并清理`

订阅助手不出现在上述链路中。配置页另放一段说明：删除完成后，若订阅助手增强版已启用下载器删除监听，它会自行决定清理、重试或换种；本插件不调用订阅助手接口，也不保证外部插件已安装或启用。

监控启停必须与旧的转移/IYUU 能力解耦：新增独立的 `is_speed_monitor_active` 判定（插件启用、速度监控开关开启且至少选择一个已配置且受支持的下载器），`is_plugin_active()` 和 `get_state()` 将其与转移/IYUU 能力做 OR 合并；`service/lifecycle.py` 和 `service/scheduler.py` 在转移关闭、IYUU 关闭时仍能注册并运行监控服务，全部能力关闭时才停止调度器。下载器临时断连不能让启停门禁把监控服务注销。`get_form()` 必须在转种关闭时仍展示和保存速度监控配置，不能用旧转移校验把监控一并禁用。

下载器轮询采用三态结果而不是只返回列表：`success(items)`、`success([])` 和 `error(cause)`。成功空列表才允许把本地 session 对账为缺失/已删除；API 超时、鉴权失败或断连必须保留 session、记录诊断错误并等待恢复，不能误判成删除。

## 配置契约

首期配置键及默认行为：

| 配置键 | 默认值 | 说明 |
| --- | --- | --- |
| `speed_monitor_enabled` | `false` | 速度监控总开关，保持旧版本默认行为不变 |
| `speed_monitor_downloaders` | `[]` | 选择要监控的下载器实例，可多选 |
| `speed_monitor_mode` | `auto` | `auto` 等历史健康样本；`manual` 使用每个下载器的最低期望速度 |
| `speed_monitor_tolerance` | `1.5` | 预期完成时长容忍倍数，必须大于 `1.0` |
| `speed_monitor_min_samples` | `5` | 自动模式允许告警前的健康完成样本数 |
| `speed_monitor_interval_minutes` | `5` | 采样间隔，范围 `1-60` 分钟 |
| `speed_monitor_grace_minutes` | `10` | 会话启动后宽限时间，范围 `0-1440` 分钟 |
| `speed_monitor_consecutive_abnormal_samples` | `2` | 连续异常采样次数，范围 `1-10` |
| `speed_monitor_manual_speed_bps` | `{}` | 手动模式按下载器名称保存最低期望速度，单位 B/s |
| `speed_monitor_floor_speed_bps` | `{}` | 自动模式按下载器名称保存可选保护下限，单位 B/s；为空时不设置绝对速度下限 |
| `speed_monitor_notification_type` | `Plugin` | MP `NotificationType` 合法枚举值，非法值回退 `Plugin` |

删除语义不是可选开关：Telegram 的确认删除动作固定删除任务及该种子的全部数据，包括已经下载完成的文件。配置页必须显示不可恢复警告，并说明换种需要订阅助手增强版配合。

内部状态保留策略固定为：每个下载器健康样本窗口最近 20 条；终态 session 和已处理告警保留 30 天、各最多 1000 条并按时间清理，清理只针对终态历史，不触碰活跃 session；状态记录带 schema version，缺失或旧版本按显式迁移函数处理，迁移失败则停用监控并报告，不静默丢弃数据。

## 分阶段计划

### Phase 1: 契约、适配器与失败门禁

目标：把配置、状态、qB/TR 归一化字段和 Telegram 回调边界固定下来，并先用测试锁定破坏性删除与外部联动边界。

实现面：`service/config.py`, `model/state.py`, `utils/torrent_adapter.py`, `adapter/moviepilot.py`, `__init__.py`, 新增 speed service 文件，以及 `tests/static/` 和插件单元测试。

任务 1.1：新增配置/状态契约与静态红门禁。

- 任务：定义配置默认值、范围校验、每下载器手动速度映射、每下载器可选保护下限、会话/基准/告警状态 key；固定 `NotificationType.Plugin` 默认和 `delete_file=True` 语义。
- 验收：静态测试能从源码确认所有配置键、默认值、状态 key 和删除种子及全部数据警告契约；在生产代码完成前，测试对缺失实现至少出现一次可复现失败。
- 验证：`pytest --confcutdir=tests/static tests/static/test_downloadmanagerlocal_speed_monitor_contract.py`；记录红测输出和 baseline smoke check。
- 提交边界：只提交契约测试、状态/配置契约变更及进度证据。

任务 1.2：建立 qBittorrent/Transmission 统一任务字段和删除边界。

- 任务：归一化 hash、名称、总字节、已下载字节、加入时间、当前状态、保存路径和下载器实例身份；区分 active、paused、queued、checking、completed、error；轮询结果明确区分成功空列表和 API 错误；统一暴露删除任务及文件的适配器调用。
- 验收：qB/TR fake 对象在字段缺失或类型不同的情况下返回稳定 DTO；成功空列表与 API 错误不会混淆；删除动作对两类下载器都只允许显式传入 `delete_file=True` 才执行，且没有转种前置条件。
- 验证：`pytest --confcutdir=tests/static tests/static/test_downloadmanagerlocal_speed_monitor_adapter.py plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_adapter.py`；`python -m compileall plugins.v2/downloadmanagerlocal`。
- 提交边界：提交适配器和对应测试。

任务 1.3：核验 MoviePilot Telegram `MessageAction` 回调契约。

- 任务：复用 MP 现有通知与 AgentRank 的回调格式，确认 plugin id、Telegram channel、MP 主程序提供的目标用户/回调用户身份、原消息 id、64 字节 callback_data 限制和原地收束方式；为 DownloadManagerLocal 规划独立 callback prefix，不新增插件自有白名单或管理员规则。
- 验收：fake `MessageAction` 能被当前插件识别，非本插件、非 Telegram、非 MP 目标用户、越权用户和过期 token 都被拒绝；回调协议不要求改核心或其他插件，权限来源只复用 MP 主程序。
- 验证：`pytest --confcutdir=tests/static plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_telegram.py`；静态检查 `MessageAction` 注册和 callback prefix。
- 提交边界：提交回调契约测试和最小入口注册骨架。

阶段验收：配置/状态/适配器/回调契约测试通过；没有触碰订阅助手；失败门禁已经能阻止缺少删除种子及全部数据语义的实现。

### Phase 2: 监控会话生命周期与持久化

目标：实现多下载器独立采样、启动/完成/删除会话状态和 MoviePilot 重载后的恢复，不依赖转种。

实现面：新增 `service/speed_monitor.py`，调整 `utils/config.py`, `service/lifecycle.py`, `service/scheduler.py`, `service/events.py`, `model/state.py`, `__init__.py` 的 `get_state()`/`get_form()`，并新增会话单元测试。

任务 2.1：接入可选下载器监控服务。

- 任务：实现独立的 `is_speed_monitor_active` 门禁和监控调度 job；启用插件且选择下载器后注册间隔服务，转移/IYUU 开关不作为前置条件；首次观察到任务时建立 session，已有任务不凭空补算未知的有效时长；按下载器实例和 session 隔离扫描与锁。
- 验收：qB、TR、多个下载器可同时被扫描；关闭监控开关或未选择下载器时不注册服务；`get_state()`、生命周期、调度器和 `get_form()` 在转种/IYUU 关闭时仍正确反映和运行速度监控。
- 验证：`pytest plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_lifecycle.py`；服务构造器静态测试；baseline smoke check。
- 提交边界：提交服务注册和会话创建。

任务 2.2：持久化采样快照并处理重载/缺失任务。

- 任务：保存每个 session 的 downloader id、hash、名称快照、总字节、首次观察时的 `start_downloaded_bytes` 与 `start_remaining_bytes`、最近已下载字节、有效时长、最后有效采样时间、最后成功轮询时间、最后状态、告警周期和 schema version；重载后恢复并执行显式迁移；任务消失、外部删除和完成均只终止一次；按 30 天 TTL/各 1000 条上限清理终态历史，按下载器保留最近 20 条健康样本；下载器 API 错误期间暂停有效时长和超时钟，恢复成功后继续。
- 验收：模拟重载不会重置有效时长、初始字节或剩余体积；同一 hash 不产生重复 session；成功空列表导致任务进入 deleted/missing 终态，API 错误不会终止 session、有效时长或超时钟；任务消失不会再次发送删除动作或告警；旧/缺失状态可迁移，迁移失败有明确错误且不静默清空；终态历史超过 TTL/上限时只清理最旧终态记录。
- 验证：`pytest plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_state.py`；状态 key 静态清单；`git diff --check`。
- 提交边界：提交持久化和幂等状态处理。

任务 2.3：结束会话并生成原始统计。

- 任务：完成时按 `effective_bytes = max(0, completed_downloaded_bytes - start_downloaded_bytes)` 及每次正向字节增量计算有效下载字节，按 active 状态累计有效下载时长，平均速度为 `effective_bytes / valid_active_seconds`；暂停、排队、校验和首次观察前的未知时间不计入分母；手动删除/超时删除任务只记录处置结果，不作为健康完成样本。
- 验收：对已下载一部分后才被首次观察的任务，统计只使用观察期间的新增字节，不把总下载字节除以监控墙钟时长；fake 时间线能证明暂停/校验不污染有效时长，完成统计可复现；删除和完成互斥且只结束一次。
- 验证：`pytest plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_stats.py`；覆盖 qB/TR 两种状态序列。
- 提交边界：提交统计和会话终止逻辑。

阶段验收：多下载器会话、重载恢复、完成/删除终止和有效时长测试全部通过；没有发送通知或删除真实任务。

### Phase 3: 基准、手动阈值与异常判断

目标：按照已确认公式判定“规定时间内未完成”的异常，支持自动/手动两种模式，并防止连续慢速任务污染基准。

实现面：新增 `service/speed_baseline.py`，扩展 `service/speed_monitor.py` 和 `model/state.py`；新增算法与污染保护测试。

任务 3.1：实现有效时长、预计时限和连续异常判定。

- 任务：自动模式有基准时使用 `reference_speed = max(robust_baseline, floor_speed_bps)`，未填写保护下限时只使用稳健基准；手动模式必须使用每个选中下载器的正数最低期望速度。预算以会话首次观察时的剩余体积为准：`expected_seconds = start_remaining_bytes / reference_speed`，`allowed_seconds = expected_seconds * tolerance`；若首次观察时已完成则不建立异常会话；会话超过允许时限且未完成时进入异常计数；下载器 API 错误期间暂停计时，无有效速度按连续采样规则处理。
- 验收：单位换算、部分下载后的剩余体积、零字节、速度为零、任务已完成、启动宽限、连续异常次数、断连暂停、保护下限为空和保护下限高于历史基准都有明确结果；异常通知包含进度、当前速度、参考速度、有效时长和允许时限。
- 验证：`pytest plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_decision.py`；至少覆盖边界值 `tolerance=1.0` 拒绝、`1.5` 接受和任务完成前后状态切换。
- 提交边界：提交判定算法和测试。

任务 3.2：实现自动健康基准与手动模式。

- 任务：按下载器实例保存最近 20 条健康完成样本；自动模式至少 5 个有效样本后，以样本中位数作为中心、MAD（`1.4826 * MAD`）作为离散尺度，使用 `median ± max(3 * 1.4826 * MAD, 0.25 * median)` 过滤新样本；MAD 为 0 时使用 25% 相对带；通过过滤的样本才更新可信基准。首次校准阶段只形成 provisional 基准，样本不足不告警；设置了保护下限时，低于保护下限的样本不得进入 provisional；未设置保护下限时无法仅凭首批样本识别“整个网络环境都偏慢”，必须把 provisional 标记为相对基准并允许显式重置。达到门槛且通过过滤后才提升为 trusted，保留最后 trusted 基准直到显式重置。自动参考速度再叠加该下载器可选保护下限；手动模式直接使用配置速度，不读取历史基准。
- 验收：qB/TR 基准和保护下限互不影响；少于 5 个健康样本且未设置手动模式时自动模式不告警；首次校准、首批整体偏慢且未设置保护下限、保护下限过滤、MAD 为 0、离群样本、可信基准保留和显式重置均有测试；手动模式缺少选中下载器的正数速度时配置不可运行；未填写保护下限时只做相对历史判断并在状态中标记该限制；所有公式和单位在测试中固定。
- 验证：`pytest plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_baseline.py`；状态持久化回读测试。
- 提交边界：提交基准和手动阈值。

任务 3.3：加入基准污染保护和告警去重。

- 任务：异常、超时、手动删除、错误、无连接和无有效速度任务不进入健康样本；健康样本按 3.2 的 MAD/相对带过滤；保留最后可信基准，连续慢速任务不得把基准线逐次压低；保护下限由用户按下载器实例设置，不设全局固定值；提供手动重置而不是静默重算；同一 hash 同一异常周期只通知一次，恢复正常/完成后清除该周期的去重状态。
- 验收：构造首次校准连续慢速（无保护下限时只标记为 provisional/相对基准，不能伪称已识别绝对异常；有保护下限时低速样本被排除）、已有 trusted 基准后连续慢速、单个极快异常、混合正常任务和不同下载器保护下限，证明 trusted 基准不会被慢速异常逐步污染，且正常完成任务可以更新基准；重置后回到 provisional 并重新等待 5 个样本；保护下限为空时不凭空生成绝对慢速结论。
- 验证：`pytest plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_contamination.py plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_dedup.py`。
- 提交边界：提交污染保护、去重和基准重置入口。

阶段验收：自动/手动模式、公式边界、样本门槛、污染保护和通知去重均通过；自动判断只产生通知状态，不自动删除任务。

### Phase 4: MP 分类通知、Telegram 交互与配置页

目标：把异常状态变成可操作的 MP/TG 通知，并在配置页展示准确的本插件运行链路和删除/外部联动说明。

实现面：新增 `service/speed_notification.py`，调整 `__init__.py`, `controller/handlers.py`, `controller/api.py`, `frontend/src/components/Config.vue`, `frontend/src/components/api.js` 和对应测试/构建产物。

任务 4.1：发送可配置分类的异常通知卡片。

- 任务：解析合法 `NotificationType`，默认 `Plugin`；通知正文显示下载器、种子名/hash、体积、进度、有效时长、当前/参考速度、允许时限和处置风险；Telegram 使用短 callback token，不把完整 hash 直接塞入 64 字节字段。
- 验收：配置任意合法分类能按该分类发送；非法分类回退 Plugin；未配置 Telegram 时普通 MP 通知仍可发送且不抛异常；消息正文明确“删除会同时清理该种子的全部数据且不可恢复”。
- 验证：`pytest plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_notification.py`；静态检查通知类型选项和默认值。
- 提交边界：提交通知服务和分类配置。

任务 4.2：实现关闭、二次确认和删除全量数据交互。

- 任务：`关闭` 只确认告警并收束按钮/重复提醒；`删除` 先进入二次确认，确认后调用所选下载器 `delete_torrents(ids=[hash], delete_file=True)` 删除该种子的全部数据，成功/失败均持久化结果；回调必须校验 plugin id、Telegram channel、MP 目标用户身份、token 和 session 当前状态，重复点击是幂等操作；采样线程与回调线程共享 session 级锁/终态条件更新，完成、删除和通知只能有一个获胜。
- 验收：关闭不改变下载器任务；取消删除不调用删除 API；确认删除对 qB/TR fake 都带 `delete_file=True` 且删除语义标记为全量数据；任务已完成、已删除、token 过期或越权点击均不得再次删除；模拟完成与删除并发时至多一个终态动作和一条异常通知；删除后 session 终止且不进入健康基准。
- 验证：`pytest plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_telegram.py plugins.v2/downloadmanagerlocal/tests/test_speed_monitor_delete.py`；回调 payload 长度检查。
- 提交边界：提交 Telegram 回调、删除全量数据和幂等处理。

任务 4.3：扩展总览 API 和配置页。

- 任务：总览返回监控服务状态、选中下载器、活跃 session 数、待处理告警数、每下载器基准样本/参考速度和最近处置结果；配置页增加监控设置、速度单位/范围校验、删除种子及全部数据的不可恢复警告及订阅助手外部联动说明。
- 任务：更新 `runtimeFlows` 为 `下载任务 -> 监控会话 -> 有效采样 -> 基准/手动阈值 -> TG 通知 -> 关闭 / 删除并清理`；订阅助手不得出现在运行链路节点，只能出现在说明文本。
- 验收：API 字段与配置页展示一致；运行总览不显示虚假的订阅助手运行状态；移动端和桌面端文字不溢出、不横向滚动；配置保存后重载仍保留选择和阈值。
- 验证：`pytest --confcutdir=tests/static tests/static/test_downloadmanagerlocal_speed_monitor_frontend.py tests/static/test_downloadmanagerlocal_api_response_inventory.py`；`pnpm --dir plugins.v2/downloadmanagerlocal/frontend build`；浏览器在 `390x844`、`768x1024`、`1440x900` 检查运行链路和说明文本。
- 提交边界：提交 API、配置页源码和由未改变源码生成的 federation dist 资产。

阶段验收：MP 分类通知、Telegram 两步删除、关闭幂等、配置页警告、运行总览链路和前端三视口验收全部通过；没有订阅助手代码或接口改动。

### Phase 5: 集成验证与 MP 本地运行闭环

目标：在不删除真实任务的前提下，证明 qB/TR、自动/手动、通知和外部删除监听边界能够在 MP 本地插件运行态闭合。

实现面：新增/扩展全部 speed monitor 测试、`scripts/sync_to_mp_local.py`、MP 本地插件源和运行态 API/日志读取；不修改 `SubscribeAssistantEnhanced`。

任务 5.1：执行全量窄测试和模拟任务矩阵。

- 验收：qB/TR 各覆盖完成、暂停、排队、校验、慢速、错误、手动关闭、确认删除和重载恢复；转种关闭时仍能监控；多下载器基准隔离；连续慢速样本不污染基准；测试全部退出码为 0。
- 验证：
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `pytest --confcutdir=tests/static tests/static/test_downloadmanagerlocal_*.py`
  - `pytest plugins.v2/downloadmanagerlocal/tests`
  - `git diff --check`
- 提交边界：只提交最后的测试补强和修复。

任务 5.2：同步 MP 本地源并回读运行态。

- 任务：按现有本地插件流程 dry-run 后同步 DownloadManagerLocal，reload 后读取 `/api/v1/plugin/history/DownloadManagerLocal` 和目标 overview，确认版本仍为 `3.2.7`、`is_local=true`、配置和运行总览契约生效。
- 验收：源文件与 MP 本地文件 hash 一致；reload 成功；history、overview 和前端 remoteEntry 可读；日志无插件导入异常；不安装在线仓库版本，不执行真实删除。
- 验证：`scripts/sync_to_mp_local.py --plugin DownloadManagerLocal --dry-run`、目标插件同步命令、`/api/v1/plugin/reload/DownloadManagerLocal`、`/api/v1/plugin/history/DownloadManagerLocal` 和 overview 回读；记录 URL 状态码、关键响应字段和日志证据。
- 提交边界：只提交实现与测试，不提交运行态生成文件。

任务 5.3：完成发布前审计与残余风险记录。

- 验收：计划、进度 JSON、配置键、API 字段、运行链路文案和测试命令一致；`SubscribeAssistantEnhanced` 无 diff；删除行为、外部联动和未授权回调风险均有记录；未得到用户明确发布确认前不 push/merge/release。
- 验证：`git diff --name-only origin/main...worldlinefix/downloadmanagerlocal` 只包含 DownloadManagerLocal、计划、测试和必要构建资产；`rg -n "SubscribeAssistantEnhanced|订阅助手"` 仅命中说明/测试，不命中外部插件源码改动。
- 提交边界：提交审计文档和进度最终状态。

阶段验收：所有任务状态为 completed，进度 JSON 记录每项验证和 commit，残余风险明确，插件在 MP 本地运行态可回读；未发生真实破坏性删除或发布。

## 基线 smoke check

在目标 worktree 执行：

```powershell
git status --short --branch
& 'C:/Users/ZhaoYu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m compileall plugins.v2/downloadmanagerlocal
$files = Get-ChildItem -LiteralPath 'tests/static' -Filter 'test_downloadmanagerlocal_*.py' | ForEach-Object { $_.FullName }
& 'C:/Users/ZhaoYu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m pytest --confcutdir=tests/static @files
```

若 bundled Python 或 pytest 不可用，必须记录确切错误，并运行最接近的可用窄检查；不能把跳过测试写成通过。

## 测试与评估矩阵

| 类别 | 必须覆盖 |
| --- | --- |
| 字段适配 | qB dict、TR object、缺失字段、零字节、不同状态名 |
| 会话时间 | active、暂停、排队、校验、完成、错误、重载、任务消失 |
| 判定算法 | 自动首次校准、样本不足、MAD 为 0、自动样本足够、手动阈值、按下载器保护下限、保护下限为空、容忍倍数、预计时限、速度为零 |
| 统计边界 | 已部分下载后首次观察、剩余体积预算、正向字节增量、暂停/排队/校验、有效时长、断连暂停、重载恢复 |
| 污染保护 | 连续慢速、单个极快离群、正常样本恢复、显式基准重置 |
| 通知 | MP 分类选择、默认 Plugin、未配置 TG、正文字段、同 hash 去重 |
| Telegram 安全 | 关闭、取消删除、确认删除、越权、过期、重复点击、64 字节限制 |
| 删除语义 | qB/TR 都传 `delete_file=True` 删除该种子全部数据，删除终态不进基准，关闭不调用删除 |
| UI | 运行链路不含订阅助手、说明文本完整、三视口无溢出、构建资产可加载 |
| 运行态 | MP 本地 reload、history/overview 回读、插件日志无导入异常 |
| 生命周期与轮询 | 转种/IYUU 全关闭仍监控、成功空列表、API 错误、断连恢复 |

## 已存在能力

- `Config.vue` 已有“运行总览”和 `runtimeFlows`，本计划扩展其链路，不另建第二个总览页面。
- `controller/handlers.py` 已有 `api_overview`，本计划在保持旧字段的前提下扩展 monitor 摘要。
- `service/lifecycle.py`、`service/scheduler.py` 已有 APScheduler 生命周期和服务声明，可复用调度边界。
- `utils/torrent_adapter.py` 已有 qB/TR hash、标签、分类、保存路径和体积读取 helper，可在其上补充速度监控字段。
- MoviePilot 已提供 `DownloadDeleted`、`NoticeMessage`、`MessageAction` 事件和 `NotificationHelper`/`post_message` 约定；Telegram 回调参考 AgentRank 的 plugin id、token、身份校验和原消息收束模式。

## 不在本计划范围

- 修改或调用订阅助手增强版代码、配置或私有接口。
- 插件自行搜索资源、重建订阅、自动换种或判断订阅助手是否已安装。
- 超过 qBittorrent/Transmission 适配能力的第三方下载器专用字段；未支持类型必须在配置/诊断中明确不可用。
- 异常检测后无用户确认的自动删除。
- 真实下载器上的破坏性删除压力测试。
- 版本号递增、GitHub 发布、合入 `main`、在线仓库安装验收。

## 失败模式与残余风险

| 失败模式 | 用户可见行为 | 计划处理 |
| --- | --- | --- |
| 下载器断连 | 总览显示监控服务异常/最近错误，不发送误导性的完成结论 | 适配器返回不可用状态，保留 session，恢复连接后继续；测试断连恢复 |
| 轮询返回空列表 | 仅在确认 API 成功时把未返回任务视为缺失 | 适配器使用 `success([])` 与 `error(cause)` 三态结果，错误不触发删除/终止 |
| qB/TR 字段缺失 | 该任务标记为不可测，不触发删除按钮 | DTO 校验失败进入诊断计数，不能写入健康基准 |
| Telegram 回调过期或越权 | 原通知保持未处理，点击者收到拒绝/已失效提示 | token TTL、plugin id、channel、userid、session 状态和幂等校验 |
| 删除 API 失败 | 通知显示删除失败，任务保留，允许重新处理 | 持久化失败原因，不重复自动调用 |
| 手动速度或保护下限缺失 | 该下载器显示未就绪，不发送无依据的异常通知 | 选中下载器必须配置手动正数速度；自动保护下限为空时明确标记为相对判断 |
| 订阅助手未启用 | 删除仍完成，但不会自动换种 | 配置页明确说明外部联动是可选行为，不伪造联动状态 |
| 连续慢速样本 | 不降低健康基准，不把错误速度当作新基线 | 排除异常任务、稳健统计、可信基准保留和显式重置 |
| 插件重载 | 会话和告警不重复创建/通知 | 持久化 hash 状态、版本化状态读取、重载测试 |
| 状态迁移或历史膨胀 | 迁移失败时监控进入明确停用/诊断状态，终态历史按 TTL/数量上限清理 | schema version、显式迁移、终态 30 天 TTL/各 1000 条上限、健康样本窗口 20 条，不清理活跃 session |
| 完成/删除并发 | 只保留一个终态，避免重复通知或误删已完成任务 | session 级锁与原子终态条件更新，回调和采样共享同一状态源 |
| 首次校准整体偏慢 | 未设置保护下限时只提供相对基准，不声称识别绝对慢速；设置保护下限后排除低于下限的样本 | 这是仅凭历史样本无法消除的识别边界，提供总览提示和显式重置，不伪造确定性结论 |
| 告警关闭后的再次异常 | 同一异常周期不重复打扰，任务恢复后再次超时允许重新通知 | 以 session 的 anomaly_epoch/恢复状态去重，不用永久 hash 黑名单 |

## 决策记录

| 决策 | 原因 | 取舍/被拒方案 | 来源 |
| --- | --- | --- | --- |
| 运行总览主链路不包含订阅助手 | 订阅助手是可选外部监听方，不属于本插件控制面 | 不画成内部节点，避免用户误以为插件能保证换种 | 用户确认 |
| Telegram 删除固定清理全部种子数据 | 用户明确要求整个种子不要，包括已经下载的内容 | 不提供“只删任务”或“只删未完成文件”按钮，避免按钮语义与实际行为分离 | 用户确认 |
| 自动异常只通知，不静默删除 | 删除不可恢复，TG 明确确认才是授权边界 | 不采用后台自动删除/自动换种 | 用户确认的 TG 交互方向与破坏性操作门禁 |
| 健康基准按下载器实例隔离 | qB/TR 和不同用户下载器速度不可直接混用 | 不使用全局平均速度 | 用户确认的多下载器与 qB/TR 独立统计 |
| 健康样本使用稳健统计并排除异常 | 连续慢速种子不能污染基准 | 不使用简单平均、不把超时任务写入基准 | 用户确认的污染保护要求 |
| 自动基准固定为中位数 + MAD 过滤 | 需要可复现地处理首次校准、离群和连续慢速样本 | 不使用未定义的“同等稳健统计”；窗口 20 条，3 MAD 且至少 25% 相对带，显式重置保留可信基准 | 计划实现约束 |
| 保护下限按下载器实例可选配置 | 不同用户和下载器网络条件不同，不能设置全局固定速度 | 默认不填写；填写后取保护下限与稳健基准的较大值 | 用户确认 |
| 默认通知分类为 `Plugin` | 与 MP 主程序分类兼容且不改变旧通知语义 | 不硬编码 Telegram 专属分类 | 用户确认 |

## 提交规则

- 每个任务一个可验证 commit，标题使用 `type(downloadmanagerlocal): 具体动作`；commit 是开发留痕，不代表额外人工审计。
- 未通过该任务验收不得提交；不要把未验证实验、其他插件改动或版本 metadata 混入 commit。
- 只允许提交当前 DownloadManagerLocal 业务分支、相关测试和本计划文档；不 push、不 merge、不 amend。
- 最终合入和发布必须由用户另行明确确认。

## Copy-ready `/goal` starter

```text
/goal Implement docs/plans/2026-08-04-download-speed-monitor-phased-plan.md by following its execution ledger.

Each turn:
1. Read docs/plans/2026-08-04-download-speed-monitor-progress.json and work only on the current task.
2. On the first task of each Phase, run git status --short --branch, git log --oneline -15, and the plan baseline smoke check; on later tasks run only the current task's narrow tests unless a shared-boundary failure requires the smoke check.
3. Implement only the current task, including its named tests and files.
4. After verification passes, update the progress JSON status/evidence/commit/log fields, then commit the task. Task commits are development trace only, not extra manual audits. Never commit on failed verification; never push, merge, amend, release, or modify SubscribeAssistantEnhanced.
5. When a phase acceptance is proven, advance to the next phase without asking for confirmation. Perform the complete static/build/runtime audit only in Phase 5.3.

Done when every task is completed, all hard acceptance checks are recorded, MP local runtime readback succeeds, and residual risks are documented.
```
