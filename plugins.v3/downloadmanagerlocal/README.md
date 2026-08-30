# DownloadManagerLocal V3

下载中心是 MoviePilot V3 原生插件，把转移做种、IYUU 辅种、种子重命名、站点标签、做种校验、下载速度监控和上传限速聚合到一个插件里，并通过 Vue 联邦页面提供配置、运行总览与只读诊断。

## 能力构成

- 转移做种：从源下载器复制种子到目标下载器，支持路径映射、删除源任务、删除重复任务。
- IYUU 辅种：扫描可辅种任务，查询 IYUU 并把辅种种子写入指定下载器。
- 种子重命名：按 MoviePilot 识别结果与原始发布名模板重命名，支持补刀与恢复原名。
- 站点标签：按 tracker 域名映射站点名并写入下载器标签，支持临时标签清理。
- 做种校验：转移或辅种后登记队列，后台轮询任务状态并按配置自动开始做种。
- 速度监控：按下载器建立稳健速度基准，识别异常下载会话并提供处置入口。
- 上传限速：为 qBittorrent 与 Transmission 写入全局上传上限，并按站点合计上限分配额度。

## 启用前提

插件总开关 `enabled` 之外，每项能力各有独立门禁；任意一项满足即视为运行中，配置不全的能力只保留配置意图，不会执行。

| 能力 | 生效条件 |
| --- | --- |
| 转移做种 | `transfer_enabled` 开启，且已填写 `fromdownloader`、`todownloader`、`fromtorrentpath` |
| IYUU 辅种 | `iyuu_enabled` 开启，且已填写 `iyuu_token` 与至少一个 `iyuu_downloaders` |
| 速度监控 | `speed_monitor_enabled` 开启并选择下载器；`manual` 模式下每个下载器必须填写正数手动基准 |
| 上传限速 | `upload_limit_enabled` 开启并选择下载器，且每个下载器都填写正数 `upload_limit_downloader_limits_kib` |

## 配置要点

- `delay_minutes`、`transfer_fallback_enabled`、`transfer_fallback_interval_minutes`：转移延迟与兜底扫描周期。
- `nolabels`、`includelabels`、`includecategory`、`nopaths`：转移任务的标签、分类与路径筛选。
- `frompath`、`topath`：源与目标下载器之间的保存路径映射。
- `deletesource`、`deleteduplicate`、`add_torrent_tags`、`remainoldcat`、`remainoldtag`：转移后的处置与标签保留策略。
- `rename_movie_format`、`rename_tv_format`、`rename_exclude_dirs`：重命名模板与排除目录。
- `tag_siteprefix`、`tag_tracker_mappings_str`：站点标签前缀与自定义 tracker 映射。
- `iyuu_sites`、`iyuu_nolabels`、`iyuu_nopaths`、`iyuu_size`、`iyuu_labelsafterseed`、`iyuu_categoryafterseed`：辅种范围与辅种后的标签分类。
- `seed_autostart`、`seed_skipverify`、`seed_check_interval`、`seed_max_wait_minutes`：做种校验行为与等待上限。
- `speed_monitor_mode`、`speed_monitor_tolerance`、`speed_monitor_min_samples`、`speed_monitor_interval_seconds`、`speed_monitor_grace_minutes`、`speed_monitor_consecutive_abnormal_samples`：基准来源、判定容忍度、采样与宽限。
- `upload_limit_site_rules`、`upload_limit_grace_minutes`：站点合计上限与新种宽限；站点值为空或 `0` 时不写单种限速。
- `notify`、`speed_monitor_notification_type`：通知开关与消息通道。

## 运行流程

1. 转移做种在下载完成事件后按 `delay_minutes` 延迟执行，兜底扫描按周期补齐漏掉的任务。
2. 转移成功后按模板执行重命名并写入站点标签，失败记录进入重命名历史，可单条或批量补刀。
3. 连续补刀失败的记录自动归档，归档后跳过后续兜底扫描，可手动恢复或删除。
4. 转移与辅种完成的种子登记做种校验队列，后台线程轮询并按配置自动开始做种。
5. 速度监控按采样周期建立基准，连续异常样本达到阈值后在总览暴露处置入口。
6. 上传限速以 30 秒协调周期读取实时上传流量，在下载器全局上限内为受限站点等权分配额度。

## 边界与限制

- 目标下载器为 Transmission 时，种子重命名、命名补刀和恢复原名不生效，配置页与运行诊断会明确提示。
- 上传限速默认关闭；`allocated_kib` 只是插件写入的额度，不代表实际吞吐或 Peer 能力。
- 普通 `stop_service()` 只停止协调 worker，下载器保留最后写入值；只有明确停用上传限速时才按 compare-and-set 恢复原值。
- 扫描站点标签只追加 `{limit_kib: 0}`；未知标签、无标签和多站点标签的种子不写单种限速。
- 原始种子名被污染且无可信候选时跳过自动重命名，不会用脏名字套模板。
- IYUU 查询带限速与 Token/站点绑定预检，遇到服务端异常、空响应或限流连续失败时停止本轮任务。
- 20 条插件 API 全部要求 `bear` 认证，Vue 组件使用宿主注入的实例 ID，不硬编码源插件路径。
- 运行状态、队列、缓存和锁按插件实例隔离，多实例之间不共享。

## 常见故障

| 现象 | 可能原因 | 处理方向 |
| --- | --- | --- |
| 插件显示未运行 | 四项能力门禁均未满足 | 按上表补齐对应必填项后保存 |
| 转移不触发 | 源/目标下载器或种子目录未填写，或任务被标签、分类、路径规则过滤 | 查看运行诊断中的转移配置检查与筛选条件 |
| 重命名保持原名 | 目标下载器为 Transmission，或原始发布名不可信 | 改用 qBittorrent 目标，或在重命名历史中手动补刀 |
| 辅种无结果 | Token 无效、站点未绑定或体积/标签过滤过严 | 核对 IYUU Token 与站点绑定，放宽 `iyuu_size` 与标签过滤 |
| 站点标签为空 | tracker 域名未命中内置映射 | 在 `tag_tracker_mappings_str` 补充自定义映射 |
| 速度监控无基准 | 采样不足或 `manual` 模式缺少手动基准 | 等待样本积累，或为每个选中下载器填写正数基准 |
| 上传额度未写入 | 下载器全局上限为空或站点合计上限为 `0` | 填写正数下载器上限，并为需要限速的站点填写正数合计上限 |

## 运行要求

- MoviePilot `>= 3.0.0`
- MoviePilot V3 原生插件格式与 Vue 联邦渲染
- 至少一个可用下载器；转移做种需要源与目标两个下载器
- IYUU 辅种需要有效 IYUU Token 与已绑定站点
