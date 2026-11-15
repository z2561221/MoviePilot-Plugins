# DoubanCenter AI Context

## 插件用途

DoubanCenter 3.0.21 是 MoviePilot V3 专用本地插件，整合豆瓣榜单订阅、豆瓣时间同步、仪表盘概览、观察期治理和归档管理。V2 实现独立保留在 `plugins.v2/doubancenter`。

## 入口与渲染

- 主类入口：`__init__.py` 中的 `DoubanCenter`。
- API 路由：`controller/api.py`，只做路由声明、入参转换、异常兜底和转发。
- 渲染模式：`get_render_mode()` 返回 `("vue", "dist/assets")`。
- Vue 联邦运行产物：`dist/assets/remoteEntry.js` 及其引用资源。
- Vue 注入客户端返回最终 `{success,message,data}` envelope，业务数据从 `response.data` 读取。

## 后端模块边界

- `service/scheduler.py`：定时服务声明和调度器停止。
- `service/webhook.py`：Webhook 播放事件串行化和豆瓣时间入口。
- `service/subscription.py`：订阅历史判断、已存在订阅记录、自动订阅执行、订阅记录去重写入；查重失败返回未知，停止该条写入并保留待重试记录。
- `service/observation.py`：观察期启用判断、观察期日志、观察队列首次记录、观察期完成和跌出候选标记。
- `service/observation_metadata.py`：日志写入时保留媒体快照，按唯一身份补齐旧记录的海报与榜单信息，保留原始时间、状态和计数。
- `service/archive.py`：归档读写、首次匹配/完整度替换协调、归档恢复和移除；旧匹配符号兼容转发到纯模型。
- `model/archive_match.py`：归档键/评分及匹配规则、单次操作的投影和候选索引；不持有插件或持久化句柄。
- `adapter/rss.py`：RSSHub / RSS 抓取与 RSS 条目解析。
- `model/rank.py`：内置榜单定义和默认观察期榜单。
- `model/config.py`：默认配置、配置选项和默认表单模型。
- `storage/records.py`：插件持久化 key、读写封装、记录裁剪和榜单历史 key。
- `model/identity.py`：统一 `(media_source, media_id)`、旧字段回填和 V3 `MediaChain` 参数。
- `migration.py`：初始化时幂等迁移各类记录，从可信豆瓣/Bangumi 条目链接补回缺失身份并保存旧日志补齐结果；半截身份原样保留，待分季队列单独统计。
- `controller/schemas.py`：普通 JSON 路由的具体 Pydantic 业务模型。
- `service/rank_pipeline.py`：榜单运行编排与必要旧入口；根 `feed.py` 仅保留兼容转发。
- `service/rank_media.py`：榜单跨源识别、展示元数据与Bangumi历史补全；识别服务直接使用此模块，不回调主流水线。
- `service/rank_candidates.py`：传统RSS和已识别快照共用候选筛选、查重、观察及订阅循环，保留两类榜单各自的日期和想看数策略。
- `model/rank_candidate.py`：内存候选视图，传统RSS延迟识别以保留黑名单先于网络请求的顺序；持久化仍为既有字典。
- `service/rank_refresh.py`：RSS 目标选择、拉取窗口和仪表盘刷新编排。
- `service/rank_recognition.py`：RSS 条目与快照的识别器选择。
- `service/rank_snapshot.py`：榜单快照构造、历史合并和观察状态保留。
- `service/rank_subscription.py`：订阅筛选策略、快照订阅和运行周期编排。
- `service/dashboard.py`：仪表盘和详情页 API 编排，归档核心算法委托给 `service/archive.py`；根 `dashboard.py` 仅保留兼容转发。
- `service/folio.py`：播放事件身份、分季核验及观影同步；外层事件串行化由 `service/webhook.py` 承担，根 `folio.py` 保留兼容。
- `service/wish_sync.py`：想看账号基线、队列、识别、失败重试及订阅回执的完整服务，生产调度直接调用。
- `service/folio_account.py`：共用账号客户端、登录探测与通知节流。
- `model/runtime.py`：实例独有的缓存、锁、运行代次和待处理内存状态；保留既有字段名作为适配，停止/重载合同由lifecycle执行。
- `src/components/dashboard/useDashboardRuntime.js`：仪表盘请求、时间线和操作状态，Dashboard.vue只装配视图。
- `src/components/useRankDialog.js` / `rankDisplay.js`：详情及仪表盘共用弹窗识别状态和榜单显示定义。
- `service/wish_accounts.py`：逐账号读取想看结果、合并同一 subject ID、维护各账号首次基线与读取错误；部分账号失败不阻断其他账号。
- 明确填写的想看账号优先于 Cookie 默认账号；只有匹配登录账号时使用想看页，其余账号使用 feed。响应缺失按 `response is None` 判断，HTTP 错误保留真实状态码。
- CK 请求失败通过统一客户端回调强制通知，不受插件通知开关影响；同类故障仍按 6 小时节流，发送失败不占用节流窗口。

## 最新 V3 宿主适配

- 已按 MoviePilot V3 `da51ff1a5feea9c22451968e4b86bc8f32011925` 使用
  `app.sdk.media` 的媒体身份规范化函数，以及 `app.sdk.services` 的媒体服务器
  Helper。
- `app.adapters.external.cookiecloud.CookieCloudHelper` 当前仍没有稳定 SDK 出口，
  是唯一保留的宿主内部导入；精确例外登记在仓库根目录
  `.github/plugin-quality-exceptions.json`，修改前应先重新核对宿主 `app.sdk` 的 `__all__`。
- 普通 JSON 插件 API 显式返回 `schemas.Response[T]`，前端注入客户端读取最终
  `success/message/data` envelope，不允许再增加一层 `data`。

## 主要数据 key

- `subscribe_records`：自动订阅成功和失败历史。
- `anti_cheat_logs`：黑名单、观察期、防刷相关日志。
- `archive_records`：从详情页删除或溢出的归档记录。
- `folio_data`：豆瓣时间已同步条目。
- `folio_wait`：豆瓣时间待重试条目。
- `coming_history`：即将上映榜单历史。
- `rank_history_<rank_key>`：内置榜单历史。
- `rank_history_custom_<sha1>`：自定义 RSS 榜单历史。
- `folio_wish_seen` / `folio_wish_queue` / `folio_wish_processed` / `folio_wish_failed`：豆瓣想看状态记录。
- `folio_wish_state.accounts`：按账号保存 `initialized`、`baseline_at`、`last_run` 和 `last_error`。旧单账号基线按旧 Cookie 优先逻辑承接；无法归属时保留旧记录，新账号首次成功仅建基线。队列处理不清除账号读取错误。

所有 V3 新记录以完整 `media_source` 与字符串 `media_id` 为主身份。同来源旧主键字段在成功迁移后删除；跨源辅助 ID 可保留用于外链和展示。半身份、非法来源和字符串 `0` 不写入统一主身份。

`folio_wait` 中 `identity_status=unresolved` 且 `origin` 身份完整的记录表示目标豆瓣分季尚待核验，不是旧身份迁移失败；保留队列及原因，不能把播放来源冒充目标豆瓣身份。

## 关键调用链

- 定时 / 立即运行：`DoubanCenter.__run_all()` -> `service/rank_pipeline.py:run_scheduled()` / `run_once()` -> `service/rank_subscription.py:refresh_then_subscribe()` -> `service/rank_refresh.py:refresh_rank_data()`。
- 榜单刷新：`service/rank_refresh.py` -> `service/rank_snapshot.py` -> `service/rank_recognition.py` -> `service/rank_media.py` 领域识别实现。
- 榜单订阅：`service/rank_subscription.py` -> `service/rank_candidates.py:_process_snapshots()` -> `service/observation.py` -> `service/subscription.py`。
- 本季日期：`service/rank_timing.py` 在当前快照内按 TMDB 身份及原生季号复用日期；分段年份与原生季日期分别保留，不能直接使用剧集组 `season_years`。记录年份单独传递，不改写宿主媒体对象。
- 分季退避：`service/folio_retry.py` 保留未到期同类失败的原期限；到期失败才递增，身份、状态或库内季事实变化可立即复核。
- 详情 API：`controller/api.py` -> `service/dashboard.py` -> `storage/records.py` / `service/archive.py`。
- 豆瓣时间：Webhook event -> `service/webhook.py` -> `service/folio.py` -> `adapter/douban_account.py:DoubanApi`。
- 想看同步：`service/wish_sync.py:run_wish_sync()` -> `service/wish_accounts.py:read_wish_accounts()` -> `adapter/douban_account.py:DoubanApi.get_wish_items()`；已有账号的新条目先处理，再保存新账号基线，避免同作品被另一账号的首次基线吞掉。

## 验收方式

- V3 聚焦测试：设置 `MOVIEPILOT_BACKEND_PATH` 为固定 V3 宿主后运行 `python -m pytest tests/v3/doubancenter -q`。
- Python 语法：`python -m compileall -q plugins.v3/doubancenter`。
- 联邦构建：`pnpm --dir plugins.v3/doubancenter build`，并确认 `dist/assets/remoteEntry.js` 引用的资产均存在。
- 前端行为及产物渲染：`node --experimental-vm-modules --test tests/v3/doubancenter/*.test.cjs`；`frontend_render.test.cjs`实际加载四个联邦暴露入口并渲染有榜单海报/时间线数据的Dashboard模板和插槽。Vue使用共享实例，Vuetify仅替代表面，不代表浏览器布局及宿主加载验收。
- 版本门禁：核对 `package.v3.json` 的 `DoubanCenter` 条目、`plugin.json`、源码 `plugin_version` 与当前 `history`，本周期均为 `3.0.21`；不修改 V2 元数据。
- MP 本地闭环：使用开发技能的 `accept_local.py` 同步至可用的 MP 本地仓库；需要时从发现结果安装准确的本地来源，再执行 `POST /api/v1/plugin/reload/DoubanCenter`，回读 history、installed、overview、remotes 和静态资产。页面验收由用户完成。

## 禁止改动区

- 不 push Git 在线仓库，除非用户明确要求。
- 不改全局 MoviePilot 宿主逻辑，除非问题已定位为宿主契约缺口并单独确认。
- 不把新业务逻辑继续塞回 `__init__.py`。
- 不在验收中触发真实订阅、真实自动订阅或破坏性数据清理。

## 订阅查重兼容边界

- `adapter/subscription_query.py` 在提供 `app.sdk.queries` 的宿主上使用
  `list_subscriptions` / `list_subscription_history`，按来源、ID、季、剧集组
  在服务端精确过滤，只取一个命中；SDK 合同核对于 `bbaec9d6`。
- 旧宿主 `2fe39d85` 没有该 SDK，限于 `SubscribeOper.exists` 与
  `SubscribeHistoryOper.exists` 两个独立入口。最低宿主要求提高到具备 queries SDK
  后移除回退。任一必要查询失败或缺失返回未知，已确认命中优先。
- 聚焦覆盖：`tests/v3/doubancenter/test_review_regressions.py`，包括真实旧 Oper
  方法形状、完成历史命中、SDK 故障和不完整返回。

- 播放事件用实例锁串行处理，不丢弃锁忙时到达的不同媒体事件。
- 详情加载按请求代次、插件实例和组件存活状态回写；原生订阅需明确 success=true。

## 管理权限

删除共享记录、恢复归档、档案修复与主动刷新RSS由HTTP路由依赖统一检查超级用户。permissions只返回当前身份的can_manage，页面按当前实例禁用维护按钮；只读内容和原生订阅入口保留。后台同步不经过HTTP权限依赖。

## 3.0.21 性能边界

- 非raw时间线先限制三个有记录月份/每月50条再补图；raw保留完整档案。同实例补图串行复用缓存，旧代次停止后不能重新挂回缓存。
- 订阅历史正常新增和初始化维护批量归档；底层保存及归档恢复不自动裁剪，保留先存目标再移除恢复副本的边界。stats、subscribe_history、overview、archive_records仅投影读取。
- 归档去重按来源/标题激活单次索引；强输入只查同身份与缺身份组，弱输入保留全桶候选，必要时按兼容字段列缩小集合。精确键候选始终加入，候选按原位置合并；完整度替换同步更新索引，不追溯合并其他留存位置，保留缺字段兼容、输出顺序及500裁剪语义。索引在操作结束后释放，不挂实例缓存。
- 差分参考`tests/v3/doubancenter/archive_reference.py`冻结自17ff14fd，验证入口`test_archive_index.py`；覆盖强弱桥接、辅助ID冲突、替换后重复键、列更新和随机混合分布。单字段候选列不保证任意组合分布线性；复杂同名分布以短期内存换比较次数下降，重复单身份的小样本可有额外开销。
- RSS刷新立即发出，以单独榜单代次阻止旧页面快照覆盖新结果；时间线异步回包仍独立完成。
- Dashboard模板使用的来源链接与海报函数直接从source/api绑定；抽出composable后须验证有数据模板，setup及暴露模块能导入不能替代渲染检查。
