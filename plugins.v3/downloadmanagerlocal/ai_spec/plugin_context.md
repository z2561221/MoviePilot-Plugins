# DownloadManagerLocal 插件上下文

## 插件定位

`DownloadManagerLocal` 是 MoviePilot V3 专用插件，展示名为“下载中心”，当前开发版本为
`3.3.5`（基于已发布的 V3.3.4）。源码位于 `plugins.v3/downloadmanagerlocal/`，市场元数据位于
`package.v3.json`；V2 `3.2.9` 实现继续留在 `plugins.v2/downloadmanagerlocal/`，两代
源码不得交叉修改。后端能力聚合为：

- 转移做种：从源下载器复制种子到目标下载器，支持路径映射、删除源任务、删除重复任务和转移后做种校验。
- IYUU 辅种：按配置扫描可辅种任务，查询 IYUU，下载辅种种子，写入缓存与辅种历史。
- 种子重命名：转移或补刀时根据 MoviePilot 识别结果与原始发布名模板重命名。
- 站点标签：根据 tracker 域名映射站点名并写入下载器标签。
- 做种校验：转移或辅种后登记队列，后台线程轮询任务状态并按配置自动开始做种。
- 速度监控：按下载器建立稳健速度基准，跟踪活跃下载会话并提供异常处置入口。
- 上传限速：支持 qBittorrent 与 Transmission 下载器全局上传上限；用户可按需填写站点合计上限，正数站点跨下载器共享该额度，空值或 `0` 不写单种限速，并支持新种宽限和停用恢复。
- 诊断与总览：为 Vue 详情页提供只读诊断、运行总览、重命名历史和归档记录。

Vue 联邦配置页源码位于 `frontend/src/components/Config.vue`，运行产物位于 `dist/assets/`。前端通过注入的 `api` prop 调用 `bear` 认证插件 API。

## 当前开发边界

V3 迁移当前周期允许修改 V3 插件后端、Vue 配置页、联邦构建产物、分代仓库设施、
目标测试和本文件，但必须遵守：

- 上传限速默认关闭；MP 运行态验收时不得对真实下载器执行限速写入。
- 不执行真实种子删除、转移或标签清理。
- V3 `plugin_version`、`plugin.json`、`package.v3.json` 固定为当前开发版 `3.3.5`；V2 保持
  `3.2.9`，旧索引只增加 `"v3": false`。
- 不 push、merge 或发布。
- 普通 `stop_service()` 只停止协调 worker，下载器保留最后写入值；只有明确停用上传限速时才按 compare-and-set 恢复。

## 2026-08-14 MoviePilot V3 迁移

- 合同基线固定为 MoviePilot V3 commit
  `557cc0e2e3927b15c21de6796107cc037cae59e6`，测试通过
  `MOVIEPILOT_BACKEND_PATH` 指向该工作树。
- 媒体识别先使用宿主 `resolve_media_identity()` 校验完整
  `(media_source, media_id)`；半对、空白、非法来源与字符串 `"0"` 回退为仅按
  `meta/mtype` 识别，不再向通用链传 `tmdbid=`。
- 站点读取集中在 `adapter/moviepilot.py`，通过 V3 `SiteOper` 合并
  `SitesHelper` 模板与数据库凭据；不再读取 `SystemConfigKey.UserSite`。
- 20 条普通 JSON 路由均使用 `auth: "bear"` 和具体 Pydantic 模型。查询返回业务
  模型，操作返回 `schemas.Response[T]`，handler 不手写 envelope。
- Vue 注入客户端返回最终 `{success,message,data}`；`frontend/src/components/api.js`
  检查 `response.success` 后直接读取 `response.data`，轮询与批量请求传
  `feedback: "silent"`。
- 插件包内模块使用相对导入，不依赖源码预先安装到
  `app.plugins.downloadmanagerlocal`。
- V3 聚焦测试位于 `tests/v3/downloadmanagerlocal/`，与 V1/V2 同名包分进程运行；
  所有下载器写操作只使用 fake/mock，不连接真实下载器。

## 2026-08-12 上传限速周期

- 后端核心已拆分为 `model/upload_limit.py`、`adapter/upload_limit.py`、`service/upload_allocator.py`、`service/upload_limiter.py` 和 `service/upload_limit_worker.py`。
- 配置、生命周期、`DownloadAdded` 事件、总览 API 与 Vue 配置页已接入。
- qBittorrent 与 Transmission 均使用 fake client 做读写契约测试，不连接真实下载器。
- Vue 配置页包含基础设置、站点策略和运行状态，并已构建到 `dist/assets/`。
- 一级导航按运行链路将上传限速放在做种校验之后；运行状态中的“当前速率”表示实际上传流量，不是分配额度。
- 扫描站点只追加 `{limit_kib: 0}`，Vue 输入框默认显示为空；空值或 `0` 的站点、未知标签、无标签和多站点标签都不写单种限速，只受下载器全局上限约束。填写正数的站点进入受限池，多个受限站点等权并按实际上传需求共享下载器全局额度。
- 运行状态严格区分实时上传速率、下载器全局上限、站点合计上限和插件写入的站点额度；`allocated_kib` 不是实际吞吐或 Peer 能力证明。停用时状态 API 会清零上一周期的速率、额度和任务摘要。
- 当前周期只做本地 commit 与 MP 本地仓库默认关闭验收，不修改版本或发布元数据。

## 历史基线（2026-07-04）

2026-07-04 标准化收口后，`DownloadManagerLocal` 已按 MoviePilot 插件维护规范完成后端分层与运行态闭环验收，UI 源码和可见行为保持不变。

- 入口层：`__init__.py` 只维护 `_PluginBase` 契约、插件身份、配置生命周期、事件注册、扩展点声明和薄委托；配置页默认模型由 `utils/config.py` 统一构建。
- Controller 层：`controller/api.py` 维护 API route metadata，`controller/handlers.py` 维护 handler 调度和响应 shape。
- Service 层：`service/lifecycle.py`、`events.py`、`transfer.py`、`iyuu.py`、`rename.py`、`archive.py`、`site_tag.py`、`diagnostics.py`、`recheck.py` 等模块承载业务编排。
- Adapter 层：`adapter/moviepilot.py` 集中访问 MoviePilot 下载器、站点、系统配置、HTTP、TorrentHelper、下载历史和外部链接能力。
- SDK 导入：媒体身份使用 `app.sdk.media.resolve_media_identity`，站点模板使用
  `app.sdk.network.SitesHelper`，不再回退到宿主内部媒体或站点目录。
- 内部导入允许清单：仅保留
  `app.application.torrent.download.TorrentHelper`。原因是当前稳定 SDK 尚未导出
  TorrentHelper，插件仍需下载种子内容；2026-08-30 更新后的宿主已将该能力从
  `app.application.torrent` 包根迁入 `download` 子模块，旧的
  `app.services.torrent` 回退路径也已删除。实际运行态复核在同步/reload 阶段完成。
  SDK 提供等价出口后移除此例外；聚焦守护为
  `test_v3_internal_imports_match_symbol_allowlist`。
- 宿主数据访问例外（按 MoviePilot V3 `1f3d2b7f` 复核）：
  - 下载历史 hash 查询优先使用 `app.sdk.queries.list_download_history`，返回脱离 ORM 的
    `DownloadHistorySnapshot`；旧 V3 镜像缺少该 SDK 时才回退
    `DownloadHistoryOper.get_by_hash`，回退只为兼容旧宿主，不作为新路径。
  - `DownloadHistoryOper.get_hash_by_fullpath` 仅用于 `DownloadFiles` 的完整路径反查；
    当前稳定查询 SDK 没有文件级路径到 hash 的接口。宿主提供等价文件查询后移除。
  - `SiteOper` 用于读取已配置站点列表、优先级和域名记录；当前没有等价稳定 SDK，
    继续保留，待宿主提供站点查询 SDK 后迁移。
  - `SystemConfigOper` 用于合并当前插件实例的 IYUU 缓存配置；当前模块适配器没有等价
    稳定 SDK，继续保留，待基类配置快照可从适配器安全传入后迁移。
  - `UserOper` 用于读取管理员 Telegram 通知目标；当前没有等价稳定 SDK，继续保留，
    待宿主提供用户通知目标查询出口后迁移。
- 上传限速 Adapter：`adapter/upload_limit.py` 归一化 qBittorrent / Transmission 全局与单种上传设置，并负责读写和恢复。
- Model 层：`model/state.py` 集中维护持久化 key、IYUU 动态 key helper 和 dict 数据读写 helper，保持旧 key 后向兼容。
- 上传限速 Model：`model/upload_limit.py` 固定 schema、30 秒协调周期、下载器和站点状态 DTO。
- Utils 层：只保留无业务状态的解析、脱敏、路径、tracker、种子字段适配和配置默认值工厂等小工具。
- `modules/`：保留为兼容 shim；AST 扫描显示 `modules/*.py` 顶层 class/function 定义数均为 0，不再承载业务决策。
- 文档质量：public class/function/method 中文 docstring 缺口为 0；本轮新增或改动的 private helper 中文 docstring 缺口为 0。

## 2026-07-04 历史 V2 标准完成证据

以下执行账本只对应旧 V2 `3.2.4` 周期，不能作为当前 V3.3.5 的运行态证据：

- 计划：`docs/plans/2026-07-04-downloadmanagerlocal-plugin-standard-completion-phased-plan.md`
- 账本：`docs/plans/2026-07-04-downloadmanagerlocal-plugin-standard-completion-progress.json`
- 当时的静态测试、编译、MP 同步、reload、history 和 API 回读均属于旧 V2 实例。
- 当前 V3.3.5 必须按本文末尾的本周期验证记录重新核验。

## API 路由契约

`get_api()` 当前暴露以下路由，均为 Vue 前端调用，`auth` 必须保持 `bear`：

| path | methods | summary | handler |
| --- | --- | --- | --- |
| `/downloaders` | GET | 获取下载器列表 | `api_downloaders` |
| `/rename_history` | GET | 获取重命名历史 | `api_rename_history` |
| `/overview` | GET | 获取下载中心总览 | `api_overview` |
| `/reset_speed_monitor_baseline` | POST | 重置下载速度基准 | `api_reset_speed_monitor_baseline` |
| `/upload_limit_status` | GET | 获取上传限速状态 | `api_upload_limit_status` |
| `/upload_limit_reallocate` | POST | 立即重新分配上传额度 | `api_upload_limit_reallocate` |
| `/upload_limit_site_tags` | POST | 扫描上传限速站点标签 | `api_upload_limit_site_tags` |
| `/upload_limit_site_rules_update` | POST | 立即保存上传限速站点策略 | `api_upload_limit_site_rules_update` |
| `/upload_limit_disable_restore` | POST | 停用上传限速并恢复原值 | `api_upload_limit_disable_restore` |
| `/diagnostics` | GET | 获取诊断信息 | `api_diagnostics` |
| `/retry_renames` | POST | 一键补刀重命名 | `api_retry_renames` |
| `/retry_rename` | POST | 单条补刀重命名 | `api_retry_rename` |
| `/delete_rename_history` | POST | 删除重命名历史记录 | `api_delete_rename_history` |
| `/rename_archive` | GET | 获取补刀归档记录 | `api_rename_archive` |
| `/restore_rename_archive` | POST | 恢复补刀归档记录 | `api_restore_rename_archive` |
| `/delete_rename_archive` | POST | 删除补刀归档记录 | `api_delete_rename_archive` |
| `/recovery_torrent` | POST | 恢复种子原始名称 | `api_recovery_torrent` |
| `/sites` | GET | 获取站点列表（用于辅种站点选择） | `api_sites` |
| `/tag_cleanup_scan` | POST | 扫描下载器标签并清理临时标签 | `api_tag_cleanup_scan` |
| `/tag_cleanup_execute` | POST | 按扫描快照清理标签 | `api_tag_cleanup_execute` |

其中 7 条 GET 查询路由返回声明的裸业务模型，其余 13 条操作路由显式返回严格
`schemas.Response[T]`。Vue helper 仅在顶层字段恰好为
`success/message/data` 且 `success` 为布尔值时解包；裸业务模型及带额外字段的
自定义 payload 原样返回。这样既符合当前 V3 动态路由合同，也兼容旧镜像曾经提供
的自动 envelope。

守护测试：

- `tests/static/test_downloadmanagerlocal_backend_contract.py`

## 服务与事件

### 上传限速协调 worker

- `service/upload_limit_worker.py` 启用后立即执行一轮，此后每 30 秒协调一次；`DownloadAdded` 事件可提前唤醒。
- `service/upload_limiter.py` 每轮先写下载器全局上限；没有正数站点上限时不接管单种限速，有正数站点上限时再扫描已完成任务、识别新种宽限、聚合站点池、按站点合计上限和实际需求分配，并持久化最新状态。
- 首次启用和首次扫描的存量任务立即纳入管理，不进入宽限；后续新发现的已完成任务按 `max(completed_at, added_at)` 计算宽限。
- 宽限期间不写站点/单种额度，但仍受下载器总上传上限。
- 正数受限站点内部按实时上传和 Peer 信号估算各任务需求，并用轮换探测避免空闲任务长期占用额度；该探测只是单种额度分配的内部实现，不是用户可见的站点优先级，也不能作为真实吞吐能力的证明。
- 站点规则只接受唯一有效的 `{tag_siteprefix}站点名` 标签（默认前缀为 `🏠`）；空值或 `0` 规则、无标签、多个站点标签和未配置站点均不进入受限池，只受下载器全局上限约束。
- 站点硬上限跨所有受管下载器共享，下载器总上限分别独立生效。
- qBittorrent 同步普通与备用上传上限；Transmission 写 Session 上传上限。
- 运行中清空全部站点规则时，按 compare-and-set 恢复此前由插件写入的单种设置，同时继续保持下载器总上传上限。
- MP 或插件离线时下载器保留最后写入值；重新上线后从持久化状态继续协调。
- 运行期间插件分配覆盖单种手工值；若检测到用户后来手工修改，会更新恢复基线，明确停用时保留该新值。

### `DownloadAdded`

- 建立速度监控会话后唤醒速度 worker。
- 无论速度会话是否建立，都尝试唤醒上传限速 worker，以便新完成/新增任务尽快进入下一轮观测。

### `get_service()`

- `TorrentTransferFallback`
  - 条件：`_transfer_active` 且 `_transfer_fallback_enabled`
  - trigger：`interval`
  - func：`_fallback_transfer`
  - kwargs：`{"minutes": _transfer_fallback_interval_minutes}`

- `IYUUAutoSeed`
  - 条件：`_iyuu_enabled`、`_iyuu_cron`、`_iyuu_token`、`_iyuu_downloaders`
  - trigger：`CronTrigger.from_crontab(_iyuu_cron)`
  - func：`iyuu_auto_seed`
  - kwargs：`{}`

### `TransferComplete`

`on_transfer_complete()` 监听 `EventType.TransferComplete`：

- 插件转移功能未激活时直接返回。
- 事件下载器不匹配 `_fromdownloader` 时直接返回。
- 根据 `_delay_minutes` 创建 `delayed_transfer_<fromdownloader>` date job。
- 通过 `_delayed_transfer()` 委托转移实现。
- 事件驱动和兜底扫描进入共享转移循环后，会按 qB `completion_on` 再次校验完成年龄；不足 `_delay_minutes` 的任务跳过，达到阈值后再转移。
- 手动“立即运行一次”不受自动入口延迟门禁影响；缺少 `completion_on` 时保持原有候选行为。

## 后端模块边界

- `controller/api.py`：API route metadata，保持 path/method/auth/summary 与 Vue 前端契约一致。
- `controller/handlers.py`：API handler 与响应 shape，不写核心业务编排。
- `service/lifecycle.py`：配置初始化、一次性任务和 scheduler 生命周期编排。
- `service/events.py`：`TransferComplete` 事件过滤、延迟计算和 date job 注册。
- `service/transfer.py`：转移做种主流程、兜底扫描、转移后处理和补刀入口。
- `service/iyuu.py`：IYUU 下载器选择、辅种扫描、查询、下载链接解析、种子下载、缓存更新和后处理。
- `service/rename.py`：重命名模板、原始发布名候选、下载历史候选、补刀和单 hash 补刀。
- `service/archive.py`：失败分类、连续失败归档、恢复、删除、列表和统计。
- `service/recheck.py`：做种校验队列、后台线程、状态判断和超时判断。
- `service/site_tag.py`：tracker 域名解析、站点标签写入、临时标签回收和人工标签清理。
- `service/upload_allocator.py`：纯逻辑额度分配、需求估算、站点共享硬上限和单种轮换探测。
- `service/upload_limiter.py`：上传限速扫描、分配、持久化、状态摘要和 compare-and-set 恢复。
- `service/upload_limit_worker.py`：30 秒常驻协调、事件唤醒和只停 worker 的离线保持语义。
- `service/diagnostics.py`：诊断数据构建。
- `modules/*.py`：兼容 shim，只重导出 service 实现；不得新增业务判断。
- `utils/config.py`：配置默认值工厂、启用状态、安全整数、转移/IYUU 活跃判定。
- `adapter/upload_limit.py`：qBittorrent / Transmission 全局与单种上传设置适配，不承载额度业务判断。
- `model/upload_limit.py`：上传限速 DTO、schema 和站点规则归一化。
- `utils/torrent_adapter.py`：qBittorrent 和 Transmission 的 hash、标签、分类、保存路径和大小适配。
- `utils/tag_cleanup.py`：临时标签归属判定和标签类型分类。
- `utils/name_cleaner.py`：发布名清洗、污染名检测和补刀 hash 收集。
- `utils/path.py`、`utils/tracker.py`、`utils/sensitive.py`：无状态工具函数。
- `iyuu_helper.py`：IYUU API 请求与响应解析。

## 持久化数据 key

通过 `_PluginBase.get_data()` / `save_data()` 读写：

- `rename_records`
  - 重命名历史，hash -> record。
  - `api_rename_history()`、`api_recovery_torrent()`、`save_rename_record()`、诊断和补刀逻辑使用。

- `rename_retry_state`
  - 补刀失败状态、归档状态、失败次数和原因。
  - `rename_archive.py` 管理，归档列表和历史过滤依赖该 key。

- `seed_recheck_queue`
  - 类属性 `_seed_recheck_queue_key` 当前值。
  - 做种校验队列，结构为下载器名 -> hash -> item。

- `iyuu_<source_hash>`
  - 某个母种 hash 的 IYUU 辅种历史。

- `iyuu_source_<seed_hash>`
  - 辅种 hash 到母种 hash 的反向映射。

- `upload_limit_state`
  - schema v1 的上传限速运行态，保存管理状态、下载器原始/最后写入设置、内部探测状态、单种原始/最后写入设置、宽限截止时间、失败计数和最近状态摘要；这些字段保持向后兼容，但不构成站点策略配置。

插件配置中还持久化 IYUU 缓存字段：

- `iyuu_permanent_error_caches`
- `iyuu_error_caches`
- `iyuu_success_caches`
- `iyuu_clearcache`

重构时必须保持这些 key 后向兼容，不得迁移或改名，除非先写兼容读取和回归测试。

## 关键配置字段

转移做种：

- `enabled`
- `transfer_enabled`
- `onlyonce`
- `delay_minutes`
- `transfer_fallback_enabled`
- `transfer_fallback_interval_minutes`
- `fromdownloader`
- `todownloader`
- `frompath`
- `topath`
- `fromtorrentpath`
- `deletesource`
- `deleteduplicate`
- `nolabels`
- `includelabels`
- `includecategory`
- `nopaths`
- `transferemptylabel`
- `add_torrent_tags`
- `remainoldcat`
- `remainoldtag`

重命名和标签：

- `rename_enabled`
- `rename_movie_format`
- `rename_tv_format`
- `rename_exclude_dirs`
- `tag_enabled`
- `tag_siteprefix`
- `tag_tracker_mappings_str`

IYUU：

- `iyuu_enabled`
- `iyuu_cron`
- `iyuu_onlyonce`
- `iyuu_token`
- `iyuu_downloaders`
- `iyuu_auto_downloader`
- `iyuu_sites`
- `iyuu_nolabels`
- `iyuu_nopaths`
- `iyuu_size`
- `iyuu_auto_category`
- `iyuu_labelsafterseed`
- `iyuu_categoryafterseed`
- `iyuu_clearcache`

做种校验：

- `seed_autostart`
- `seed_skipverify`
- `seed_check_interval`
- `seed_max_wait_minutes`

速度监控：

- `speed_monitor_enabled`
- `speed_monitor_downloaders`
- `speed_monitor_mode`
- `speed_monitor_tolerance`
- `speed_monitor_min_samples`
- `speed_monitor_interval_seconds`
- `speed_monitor_grace_minutes`
- `speed_monitor_consecutive_abnormal_samples`
- `speed_monitor_manual_speed_bps`
- `speed_monitor_floor_speed_bps`
- `speed_monitor_notification_type`

上传限速：

- `upload_limit_enabled`：默认 `false`。
- `upload_limit_downloaders`：用户自定义选择的 qBittorrent / Transmission 实例；未选择的下载器不展示额度也不接管。
- `upload_limit_downloader_limits_kib`：每个受管下载器的正整数总上限，单位 KiB/s。
- `upload_limit_site_rules`：站点名到 `{limit_kib}`；正数表示该站点所有任务共享的合计上限，空值或 `0` 表示该站点不写单种限速，只受下载器全局上限约束。
- `upload_limit_grace_minutes`：站点策略模式的新种宽限，默认 30 分钟，0 表示完成后立即纳入单种分配。
- 扫描站点、清空策略和站点上限编辑会立即串行持久化 `upload_limit_site_rules`，不依赖插件配置页的整体保存；扫描新增站点默认保存为 `0`，前端显示为空。上述操作不直接触发额度重分配，用户点击“立即分配”时会先等待扫描和策略保存完成再执行，后台 worker 仍按 30 秒周期读取最新策略。

## 验证命令

V3 使用固定宿主、专用 Python 环境与 Codex bundled Node：

```powershell
$env:MOVIEPILOT_BACKEND_PATH = 'D:\AIGC\MoviePilot\.worktrees\upstream-moviepilot-v3'
$env:PATH = 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH
$python = 'D:\AIGC\MoviePilot\.agents\.local\python-envs\agentrank\Scripts\python.exe'

& $python -m pytest tests/v3/downloadmanagerlocal -q
& $python -m compileall -q plugins.v3/downloadmanagerlocal
& $python .github/scripts/check_plugin_versions.py package.json package.v2.json package.v3.json
npm --prefix plugins.v3/downloadmanagerlocal/frontend run build
git diff --check
& $python tests/run.py
```

上传限速、重命名、标签、删除与下载器控制测试不得连接真实下载器；使用 pure
allocator、fake qBittorrent / Transmission adapter、fake lifecycle worker 和静态
Vue/API 契约完成验证。运行验收前必须先取得目标 MoviePilot 实例的 V3 版本证据；
文件同步、哈希、reload、history/API 与 Chrome 页面验收分别记录，不能互相替代。

## 已知环境注意事项

- Windows PATH 中的 `python` 指向 Microsoft Store alias，不可用于验证。
- Codex bundled Python 初始没有 `pytest`，本执行分支已通过 `python -m pip install pytest` 安装到 bundled runtime。
- 直接 `python -m pytest tests/static/...` 会触发根 `tests/conftest.py` 的代际检查而失败；static 测试需使用 `--confcutdir=tests/static`。
- 正式 v1/v2 插件测试仍应遵守 `tests/run.py` 与 `tests/README.md`，不要把 static 测试入口误用于完整插件测试。

## 重构风险

- API 路由 path/method/auth/summary 改动会破坏现有 Vue 前端调用。
- 数据 key 改名会导致用户历史、归档、IYUU 缓存或做种队列丢失。
- `__init__.py` 包装方法删除过早会破坏现有模块对 plugin 对象的调用。
- IYUU 下载链接和日志脱敏涉及外部站点差异，不能用真实网络调用做单测。
- 做种校验后台线程需要保持退出事件和锁语义，否则可能导致重复 worker 或无法停止。

## 2026-07-04 历史标准化收口记录

以下记录属于旧 V2 `3.2.4` 周期，仅用于追溯，不代表当前 V3 运行态：

- 当时完成后端拆层、docstring、静态守护和 MP 本地仓库验收。
- 当时的源码、索引和运行态 history 均指向 V2 `3.2.4`。
- 当前 V3 源码、索引和运行态必须按本文顶部的当前版本规则单独核验。

## 2026-08-29 V3.3.3 结构修正记录

本周期针对已发布 V3.3.2 的下载中心进行 V3.3.3 结构收紧：

- Vue 联邦 API helper 改为使用宿主注入的 `pluginId`，组件不再固定请求 `DownloadManagerLocal` 路径。
- 下载中心入口和 `IyuuHelper` 的可变队列、缓存、锁、事件和站点摘要改为实例所有，避免多实例相互污染。
- 新增 V3 测试命名空间引导和实例隔离合同；前端联邦产物已由当前源码重新构建。
- 上下文文档、测试路径和 V3.3.3 版本边界统一，未宣称尚未完成的 MP reload 或浏览器验收。

本周期已完成的实验室验证：

```powershell
$env:MOVIEPILOT_BACKEND_PATH = 'D:\AIGC\MoviePilot\.worktrees\agentrank-host-v3'
$nodeDir = 'C:\Users\ZhaoYu\AppData\Local\Logi\LogiPluginService\PluginHosts\node22\node'
$env:Path = "$nodeDir;$env:Path"
& 'D:\AIGC\MoviePilot\.venv-test\Scripts\python.exe' -m pytest --confcutdir=tests -q tests/v3/downloadmanagerlocal
```

- V3 下载中心聚焦测试：`176 passed`。
- 前端 `npm run build`：exit 0，产物为 `dist/assets/remoteEntry.js` 及对应 hash 资源。
- `git diff --check`：exit 0。

残余边界：

- MP 本地源同步、目标实例 GET reload、history/API 回读和浏览器验收尚待本周期运行态窗口；本文件不把源码或构建结果当作运行态证据。
- IYUU 外部站点真实链路仍以目标实例配置和日志为准，实验室测试不替代生产站点实测。
- 未 push、merge 或发布；这些动作仍需用户明确确认。
