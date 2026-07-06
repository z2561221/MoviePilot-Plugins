# DownloadManagerLocal 后端上下文

## 插件定位

`DownloadManagerLocal` 是 V2 插件，展示名为“下载中心”。后端能力聚合为：

- 转移做种：从源下载器复制种子到目标下载器，支持路径映射、删除源任务、删除重复任务和转移后做种校验。
- IYUU 辅种：按配置扫描可辅种任务，查询 IYUU，下载辅种种子，写入缓存与辅种历史。
- 种子重命名：转移或补刀时根据 MoviePilot 识别结果与原始发布名模板重命名。
- 站点标签：根据 tracker 域名映射站点名并写入下载器标签。
- 做种校验：转移或辅种后登记队列，后台线程轮询任务状态并按配置自动开始做种。
- 诊断与总览：为 Vue 详情页提供只读诊断、运行总览、重命名历史和归档记录。

本文件只描述后端。UI、Vue 联邦组件、构建产物和页面文案不在本轮重构范围内。

## 禁止改动区域

本轮后端重构不得修改：

- `plugins.v2/downloadmanagerlocal/frontend/src/**`
- `plugins.v2/downloadmanagerlocal/dist/**`
- `plugins.v2/downloadmanagerlocal/frontend/index.html`
- `plugins.v2/downloadmanagerlocal/frontend/vite.config.js`
- `plugins.v2/downloadmanagerlocal/frontend/package.json`
- `plugins.v2/downloadmanagerlocal/frontend/package-lock.json`
- `plugins.v2/downloadmanagerlocal/frontend/pnpm-lock.yaml`

如后端改动看起来需要 UI 配合，停止执行并报告决策缺口。

## 当前完成状态

2026-07-04 标准化收口后，`DownloadManagerLocal` 已按 MoviePilot 插件维护规范完成后端分层与运行态闭环验收，UI 源码和可见行为保持不变。

- 入口层：`__init__.py` 保持 520 行，只维护 `_PluginBase` 契约、插件身份、配置生命周期、事件注册、扩展点声明和薄委托。
- Controller 层：`controller/api.py` 维护 API route metadata，`controller/handlers.py` 维护 handler 调度和响应 shape。
- Service 层：`service/lifecycle.py`、`events.py`、`transfer.py`、`iyuu.py`、`rename.py`、`archive.py`、`site_tag.py`、`diagnostics.py`、`recheck.py` 等模块承载业务编排。
- Adapter 层：`adapter/moviepilot.py` 集中访问 MoviePilot 下载器、站点、系统配置、HTTP、TorrentHelper、下载历史和外部链接能力。
- Model 层：`model/state.py` 集中维护持久化 key、IYUU 动态 key helper 和 dict 数据读写 helper，保持旧 key 后向兼容。
- Utils 层：只保留无业务状态的解析、脱敏、路径、tracker、种子字段适配等小工具。
- `modules/`：保留为兼容 shim；AST 扫描显示 `modules/*.py` 顶层 class/function 定义数均为 0，不再承载业务决策。
- 文档质量：public class/function/method 中文 docstring 缺口为 0；本轮新增或改动的 private helper 中文 docstring 缺口为 0。

## 2026-07-04 完整插件标准完成证据

完成证据以执行账本为准：

- 计划：`docs/plans/2026-07-04-downloadmanagerlocal-plugin-standard-completion-phased-plan.md`
- 账本：`docs/plans/2026-07-04-downloadmanagerlocal-plugin-standard-completion-progress.json`
- `tests/static/test_downloadmanagerlocal_standard_completion.py`：最终标准断言通过。
- 全量 `tests/static/test_downloadmanagerlocal_*.py`：62 passed。
- `compileall -q plugins.v2/downloadmanagerlocal`：exit 0。
- `git diff --check`：exit 0。
- no-UI gate：空输出，证明 `frontend/src/**`、`frontend/index.html`、`frontend/vite.config.js`、前端 package/lock 文件未被本轮重构改变。
- MP 本地仓库同步成功；运行态 history 显示 `plugin_version=3.2.4` 且 history 包含 `v3.2.4`。
- `/api/v1/plugin/remotes?token=moviepilot` 包含 `/plugin/file/downloadmanagerlocal/dist/assets/remoteEntry.js`。
- `/api/v1/plugin/form/DownloadManagerLocal` 返回 `render_mode=vue`。
- `/api/v1/plugin/DownloadManagerLocal/overview` 返回有效数据。
- 重载后 `moviepilot.log` 追加片段中 DownloadManagerLocal 相关 `ERROR`、`Traceback`、`Exception` 数量为 0。

## API 路由契约

`get_api()` 当前暴露以下路由，均为 Vue 前端调用，`auth` 必须保持 `bear`：

| path | methods | summary | handler |
| --- | --- | --- | --- |
| `/downloaders` | GET | 获取下载器列表 | `api_downloaders` |
| `/rename_history` | GET | 获取重命名历史 | `api_rename_history` |
| `/overview` | GET | 获取下载中心总览 | `api_overview` |
| `/diagnostics` | GET | 获取诊断信息 | `api_diagnostics` |
| `/retry_renames` | POST | 一键补刀重命名 | `api_retry_renames` |
| `/retry_rename` | POST | 单条补刀重命名 | `api_retry_rename` |
| `/delete_rename_history` | POST | 删除重命名历史记录 | `api_delete_rename_history` |
| `/rename_archive` | GET | 获取补刀归档记录 | `api_rename_archive` |
| `/restore_rename_archive` | POST | 恢复补刀归档记录 | `api_restore_rename_archive` |
| `/delete_rename_archive` | POST | 删除补刀归档记录 | `api_delete_rename_archive` |
| `/recovery_torrent` | POST | 恢复种子原始名称 | `api_recovery_torrent` |
| `/sites` | GET | 获取站点列表（用于辅种站点选择） | `api_sites` |

守护测试：

- `tests/static/test_downloadmanagerlocal_backend_contract.py`

## 服务与事件

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
- `service/site_tag.py`：tracker 域名解析和站点标签写入。
- `service/diagnostics.py`：诊断数据构建。
- `modules/*.py`：兼容 shim，只重导出 service 实现；不得新增业务判断。
- `utils/config.py`：启用状态、安全整数、转移/IYUU 活跃判定。
- `utils/torrent_adapter.py`：qBittorrent 和 Transmission 的 hash、标签、分类、保存路径和大小适配。
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

## 验证命令

当前隔离 worktree 使用 Codex bundled Python：

```powershell
& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall plugins.v2/downloadmanagerlocal
```

静态测试使用 `--confcutdir=tests/static`，避免仓库根 `tests/conftest.py` 强制 v1/v2 会话选择导致 static 目录测试无法直接运行：

```powershell
$env:MOVIEPILOT_BACKEND_PATH='D:\AIGC\MoviePilot\tmp\MoviePilot-core-v2'
& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest --confcutdir=tests/static tests/static/test_downloadmanagerlocal_backend_contract.py tests/static/test_downloadmanagerlocal_private_helpers.py tests/static/test_downloadmanagerlocal_stability_baseline.py
```

no-UI gate：

```powershell
git diff --name-only -- plugins.v2/downloadmanagerlocal/frontend plugins.v2/downloadmanagerlocal/dist
```

该命令必须输出为空。

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

## 2026-07-04 标准化收口记录

本轮已经完成从“后端拆层历史基线”到“完整插件标准闭环”的收口：

- Win 本地仓库：`worldlinefix/downloadmanagerlocal` 分支完成分层、docstring、静态守护和上下文更新。
- MP 本地仓库：已通过 `scripts/sync_to_mp_local.py --plugin DownloadManagerLocal` 同步。
- 运行态 MoviePilot：已从 MP 运行态本地仓库路径 `/vol1/1000/docker/moviepilot-v2/config/local plugins` force install，并显式 reload。
- 版本：源码 `plugin_version`、MP 本地 `package.v2.json`、运行态 history 均指向 `3.2.4`；history 含 `v3.2.4`。
- UI：未修改前端源码、前端配置或依赖；Vue federation 仍通过 `dist/assets/remoteEntry.js` 加载。

最终验证命令：

```powershell
& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q plugins.v2/downloadmanagerlocal
```

```powershell
$tests = Get-ChildItem tests/static -Filter 'test_downloadmanagerlocal_*.py' | ForEach-Object { $_.FullName }
& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest --confcutdir=tests/static @tests
```

```powershell
git diff --check
git diff --name-only -- plugins.v2/downloadmanagerlocal/frontend/src plugins.v2/downloadmanagerlocal/frontend/index.html plugins.v2/downloadmanagerlocal/frontend/vite.config.js plugins.v2/downloadmanagerlocal/frontend/package.json plugins.v2/downloadmanagerlocal/frontend/package-lock.json plugins.v2/downloadmanagerlocal/frontend/pnpm-lock.yaml
```

最新验证结果：

- `compileall -q`：exit 0。
- 全量 DownloadManagerLocal static tests：`62 passed`。
- `git diff --check`：exit 0。
- no-UI gate：空输出。
- MP runtime history：`plugin_version=3.2.4`，history 包含 `v3.2.4`。
- MP runtime remotes：包含 `/plugin/file/downloadmanagerlocal/dist/assets/remoteEntry.js`。
- MP runtime form：`render_mode=vue`。
- MP runtime overview：返回有效数据。
- reload 后日志：DownloadManagerLocal 相关 `ERROR`、`Traceback`、`Exception` 数量为 0。

残余风险：

- 未 push 到 Git 在线仓库，未合入 `main`，未发布 Release；这些动作必须由用户明确确认后才能执行。
- IYUU 外部站点真实网络链路未做生产站点实测，本轮以静态回归、编译、服务边界测试和运行态 API 验收保护。
