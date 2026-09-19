# LocalToolkit V3

工具中心是 MoviePilot V3 本地专属维护插件，把三个本地工具收敛到一个插件入口：清理库存、扫描缺集、清理 TMDB 缓存。插件只发布在本地插件源（元数据位于 `package.local.v3.json`，同步时物化为本地仓库的 `package.v3.json`），不进入公共插件市场。

## 模块构成

| 模块 key | 名称 | 触发方式 |
| --- | --- | --- |
| `library_cleanup` | 清理库存 | 周期计划 + 手动 |
| `check_missing` | 扫描缺集 | 仅手动 |
| `tmdb_cache` | 清理 TMDB 缓存 | 仅手动 |

只有清理库存会注册 MoviePilot 后台服务；扫描缺集与 TMDB 缓存清理是按需模块，不再拥有 cron 配置，插件停用时不返回任何服务条目。

## 启用前提

- 插件总开关 `enabled` 打开后才会注册服务并接受运行请求。
- 清理库存还需要 `library_cleanup.enabled` 打开，并选定媒体服务器、媒体库与用户。
- 扫描缺集需要在 `check_missing.scan_paths` 填写可访问的本地目录，每行一个。
- 清理 TMDB 缓存需要可用 Redis；连接地址取 `CACHE_BACKEND_URL`，默认 `redis://localhost:6379`。

首次启用会从旧插件 `ClearTmdbCache`、`CheckMissing`、`LibraryCleanup` 迁移配置，并写入 `migration_done` 防止重复迁移。

## 配置要点

清理库存

- `cron`：清理周期，默认 `9 0 * * *`；每次周期先完整扫描，再处理清理计划。
- `cycle_cooldown_minutes`：周期冷却分钟数，默认 `60`；冷却中只扫描入队，不重复删除。
- `selected_server`、`selected_library`、`selected_user`：媒体服务器、媒体库与判定播放状态所用用户。
- `filter_played`、`filter_favorite`、`days_threshold`：第一组条件，默认已播放、未收藏、20 天。
- `filter_played_2`、`filter_favorite_2`、`days_threshold_2`：第二组条件，默认未播放、未收藏、40 天；两组条件按并集取候选。
- `auto_delete`、`auto_delete_delay`、`auto_delete_max_count`、`dry_run`：自动删除开关、延迟秒数、每周期删除数量与演练模式。数量默认 10，可在设置页调整；自动删除默认关闭。
- `notify`：清理结果通知，Telegram 使用 HTML 分节和逐条影片列表。

扫描缺集

- `scan_paths`：待扫描目录，多行输入。
- `skip_empty`：跳过空目录，默认开启。
- `notify`：扫描结果通知，默认开启；Telegram 按路径、剧集和季度显示 HTML 报告，长清单保留总数及省略提示，其他渠道使用纯文本。

清理 TMDB 缓存

- `threshold_mb`：缓存体积阈值，默认 50 MB。
- `auto_clear`：达到阈值时自动清理，默认关闭。
- `notify`：清理结果通知，默认开启，使用简短纯文本回执。

## API 路由

全部路由使用 `bear` 认证，由 Vue 联邦组件通过宿主注入的客户端调用。

| path | method | 用途 |
| --- | --- | --- |
| `/local_toolkit/status` | GET | 读取三模块运行状态 |
| `/local_toolkit/run/{module}` | POST | 手动运行指定模块 |
| `/local_toolkit/history` | GET | 分页读取运行历史 |
| `/local_toolkit/options` | GET | 读取媒体服务器、媒体库与用户候选 |
| `/local_toolkit/invalidate_cache` | POST | 失效候选与选项缓存 |
| `/local_toolkit/cleanup_plan` | GET | 分页读取持久化清理计划 |
| `/local_toolkit/cleanup_plan/scan` | POST | 完整扫描并合并清理计划，不执行删除 |
| `/local_toolkit/cleanup_plan/clear` | POST | 清空清理计划，不删除媒体库条目 |

`history` 接受 `page` 与 `page_size`，非法值会被收敛，返回 `total`、`page`、`page_size`、`total_pages` 和 `items`；历史存储损坏时返回空列表而不是报错。

## 运行流程

1. 清理库存按 `cron` 拉取所选媒体库候选，两组条件取并集后去重。
2. 当前周期必须先完成完整扫描；扫描结果按“媒体服务器 + 条目 ID”去重并写入 `library_cleanup_plan`，不在扫描过程中删除。
3. 扫描完成后，若开启自动删除且不在冷却期，从持久化队列尾部倒序取设置数量处理；每周期只处理这一批。
4. 自动删除前发送一份 Telegram 报告，删除与复核阶段编辑同一条消息；最终结果位于原报告底部。长名单按完整条目收起，保留总数和全部核验统计。
5. 删除后仅对本轮媒体 ID 做最多三轮只读复核，间隔两秒；明确确认已移除的条目从计划移除，仍存在或无法核验的条目保留并记录尝试次数，下一周期重试。
6. 本轮结束时间写入计划并启动周期冷却；手动执行与后台周期共用同一冷却和互斥锁。
7. 扫描缺集按行遍历目录，用季集正则识别缺口并汇总。
8. TMDB 缓存清理先统计 Redis 中 TMDB 相关键的体积，再按阈值与开关决定是否清理。
9. 每次运行写入 `tool_history`（`get_data` / `save_data`），供详情页分页展示；本轮扫描、队列和复核明细保存在 `library_cleanup_result` 与 `library_cleanup_plan`。

## 边界与限制

- 清理库存直接由工具中心实现，不导入也不加载旧的独立 `LibraryCleanup` 插件；旧配置迁移只发生在 `service/lifecycle.py`。
- `modules/` 下的文件只是兼容 shim，不承载业务编排与外部边界。
- 扫描缺集与 TMDB 缓存清理不得恢复 cron 配置或后台服务注册。
- 删除是不可逆操作：`auto_delete` 与 `auto_delete_max_count` 共同限制本轮影响面，验收阶段建议先用 `dry_run`。
- 删除后复核只确认媒体库条目状态，不证明磁盘文件已经删除；复核不会启动新一轮清理或重复发出删除请求。
- Telegram 回执缺失或编辑失败时不另发一份完成报告；记录通知失败并保留本轮结果。旧宿主缺少回执或编辑接口时，仅在结束后发送一次报告。其他渠道接收一次纯文本结果。
- 同一模块实例的清理任务互斥，手动操作与定时任务重叠时拒绝重复执行。
- 前端不硬编码任何浏览器侧 token，`api.js` 只读取宿主返回的 `response.data`，不做二次解包。
- 渲染模式固定为 `("vue", "dist/assets")`；`remoteEntry.js` 与其引用的 hash 资源必须同时存在。
- 移动端在 600px 以下把历史表格改为卡片展示，验收覆盖 390px、768px、1440px。

## 常见故障

| 现象 | 可能原因 | 处理方向 |
| --- | --- | --- |
| 插件启用但无清理计划 | `library_cleanup.enabled` 未打开 | 打开清理库存开关并保存 |
| 候选列表为空 | 未选媒体库/用户，或两组条件过严 | 检查服务器、媒体库、用户与天数阈值 |
| 选项下拉为空 | 媒体服务器不可达或缓存过期 | 确认媒体服务器连接后调用 `invalidate_cache` |
| 缺集扫描无结果 | `scan_paths` 为空或路径不可访问 | 填写容器内可访问的绝对路径 |
| TMDB 缓存状态未知 | Redis 连接失败 | 检查 `CACHE_BACKEND_URL` 与 Redis 可用性 |
| 有候选但未删除 | `dry_run` 打开或 `auto_delete` 关闭 | 确认演练模式与自动删除开关 |
| 历史为空 | `tool_history` 存储损坏后已重置 | 重新运行一次模块即可写入新记录 |

## 运行要求

- MoviePilot `>= 3.0.0`
- MoviePilot V3 原生插件格式与 Vue 联邦渲染
- 清理库存需要可用媒体服务器（Emby 等）
- 清理 TMDB 缓存需要可用 Redis
- 本地插件源安装，不经公共插件市场分发
