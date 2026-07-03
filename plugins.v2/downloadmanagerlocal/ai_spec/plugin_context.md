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

- `plugins.v2/downloadmanagerlocal/src/**`
- `plugins.v2/downloadmanagerlocal/dist/**`
- `plugins.v2/downloadmanagerlocal/index.html`
- `plugins.v2/downloadmanagerlocal/vite.config.js`
- `plugins.v2/downloadmanagerlocal/package.json`
- `plugins.v2/downloadmanagerlocal/package-lock.json`
- `plugins.v2/downloadmanagerlocal/pnpm-lock.yaml`

如后端改动看起来需要 UI 配合，停止执行并报告决策缺口。

## 当前入口职责

`__init__.py` 当前仍承担较多职责：

- `_PluginBase` 插件身份、版本、权限和配置前缀。
- 运行时配置字段和默认值。
- `init_plugin()` 读取配置、清空 IYUU 缓存、过滤站点、启动一次性任务和 scheduler。
- `get_state()`、`get_command()`、`get_api()`、`get_service()`、`get_render_mode()`、`get_form()`、`get_page()` 等插件扩展点。
- `TransferComplete` 事件监听与延迟转移调度。
- 大量包装方法，把调用转发到 `api.py`、`modules/*.py` 和 `utils/*.py`。
- `stop_service()` 停止 scheduler、设置退出事件。

目标方向是让 `__init__.py` 只保留插件契约、生命周期和薄委托；业务逻辑归入 controller/service/adapter/model 或现有 modules 的明确边界。

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

- `api.py`：当前 API handler 和响应 shape。后续应迁入 `controller/api.py` 或保留兼容 shim。
- `modules/transfer.py`：配置校验、种子下载、转移主流程、转移后处理、兜底扫描、补刀入口。
- `modules/iyuu.py`：IYUU 下载器选择、辅种扫描、IYUU 查询、下载链接解析、种子下载、缓存更新。
- `modules/rename.py`：重命名模板、原始发布名候选、下载历史候选、补刀、单 hash 补刀、IYUU 母种记录复用。
- `modules/rename_archive.py`：失败分类、连续失败归档、恢复、删除、列表和统计。
- `modules/recheck.py`：做种校验队列、后台线程、状态判断和超时判断。
- `modules/site_tag.py`：tracker 域名解析和站点标签写入。
- `modules/diagnostics.py`：诊断数据构建。
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
git diff --name-only -- plugins.v2/downloadmanagerlocal/src plugins.v2/downloadmanagerlocal/dist plugins.v2/downloadmanagerlocal/index.html plugins.v2/downloadmanagerlocal/vite.config.js plugins.v2/downloadmanagerlocal/package.json plugins.v2/downloadmanagerlocal/package-lock.json plugins.v2/downloadmanagerlocal/pnpm-lock.yaml
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

## 2026-07-03 后端重构收尾状态

本轮后端重构已完成 Phase 1-5.1，并进入最终上下文记录阶段。当前边界如下：

- `__init__.py`：保留插件身份、运行时字段、生命周期、事件监听、扩展点声明和兼容包装方法；业务入口通过 `controller/` 与 `service/` 委托。
- `controller/api.py`：集中维护 API route metadata，保持 path/method/auth/summary 不变。
- `controller/handlers.py`：集中维护 API handler 与响应 shape。
- `model/state.py`：集中维护持久化 key、IYUU 动态 key helper 和 dict 数据读写 helper；旧 key 名保持不变，不需要迁移。
- `adapter/moviepilot.py`：集中访问 MoviePilot 下载器、站点、系统配置、HTTP、TorrentHelper、下载历史、随机标签和 URL 域名工具。
- `service/config.py`、`service/scheduler.py`：分别维护运行时配置初始化和 scheduler service 构造。
- `service/archive.py`、`service/diagnostics.py`、`service/iyuu.py`、`service/recheck.py`、`service/rename.py`、`service/site_tag.py`、`service/transfer.py`：作为服务 facade，入口层从这些文件导入；当前实现仍兼容委托到 `modules/*`。
- `service/boundaries.py`：记录服务 owner、legacy module 和保留的跨模块依赖例外。

保留的 legacy 例外：

- `modules/transfer.py -> modules/rename.py`：转移后补刀复用重命名候选解析，留到后续物理迁移时再消除。
- `modules/rename.py -> modules/site_tag.py`：补刀成功后复用站点标签写入，保留动态导入避免旧模块初始化环。

最终验证命令：

```powershell
& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall plugins.v2/downloadmanagerlocal
```

```powershell
$tests = Get-ChildItem tests/static -Filter 'test_downloadmanagerlocal_*.py' | ForEach-Object { $_.FullName }
& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest --confcutdir=tests/static @tests
```

```powershell
git diff --check
git diff --name-only -- plugins.v2/downloadmanagerlocal/src plugins.v2/downloadmanagerlocal/dist plugins.v2/downloadmanagerlocal/index.html plugins.v2/downloadmanagerlocal/vite.config.js plugins.v2/downloadmanagerlocal/package.json plugins.v2/downloadmanagerlocal/package-lock.json plugins.v2/downloadmanagerlocal/pnpm-lock.yaml
```

最新验证结果：

- `compileall`：exit 0。
- 全量 DownloadManagerLocal static tests：`52 passed`。
- `git diff --check`：exit 0。
- no-UI gate：空输出。

残余风险：

- 本轮只做 Win 本地仓库静态/编译验证，尚未同步到 MP 本地仓库安装重载，也未做运行时 API/页面验收。
- 本轮未改 UI、未改 `dist/`、未改版本元数据、未发布；发布前必须重新跑完整回归并由用户确认 release/merge。
- `service/*` 目前是 facade，`modules/*` 仍是主要实现层；后续若做物理迁移，需要逐项消除 `service/boundaries.py` 中记录的 legacy 例外。
- IYUU 外部站点下载链路仍主要靠静态回归和编译保护，未进行真实网络调用测试。
