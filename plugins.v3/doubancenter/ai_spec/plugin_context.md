# DoubanCenter AI Context

## 插件用途

DoubanCenter 3.0.0 是 MoviePilot V3 专用本地插件，整合豆瓣榜单订阅、豆瓣时间同步、仪表盘概览、观察期治理和归档管理。V2 实现独立保留在 `plugins.v2/doubancenter`。

## 入口与渲染

- 主类入口：`__init__.py` 中的 `DoubanCenter`。
- API 路由：`controller/api.py`，只做路由声明、入参转换、异常兜底和转发。
- 渲染模式：`get_render_mode()` 返回 `("vue", "dist/assets")`。
- Vue 联邦运行产物：`dist/assets/remoteEntry.js` 及其引用资源。
- Vue 注入客户端返回最终 `{success,message,data}` envelope，业务数据从 `response.data` 读取。

## 后端模块边界

- `service/scheduler.py`：定时服务声明和调度器停止。
- `service/webhook.py`：Webhook 播放事件串行化和豆瓣时间入口。
- `service/subscription.py`：订阅历史判断、已存在订阅记录、自动订阅执行、订阅记录去重写入。
- `service/observation.py`：观察期启用判断、观察期日志、观察队列首次记录、观察期完成和跌出候选标记。
- `service/archive.py`：归档记录去重键、完整度评分、归档写入、重复归档合并、归档移除。
- `adapter/rss.py`：RSSHub / RSS 抓取与 RSS 条目解析。
- `model/rank.py`：内置榜单定义和默认观察期榜单。
- `model/config.py`：默认配置、配置选项和默认表单模型。
- `storage/records.py`：插件持久化 key、读写封装、记录裁剪和榜单历史 key。
- `model/identity.py`：统一 `(media_source, media_id)`、旧字段回填和 V3 `MediaChain` 参数。
- `migration.py`：初始化时幂等迁移榜单、订阅、观察、归档、豆瓣时间和想看记录；unresolved 原样保留。
- `controller/schemas.py`：17 条普通 JSON 路由的具体 Pydantic 业务模型。
- `feed.py`：榜单刷新和订阅主编排，旧 helper 名保留为兼容转发。
- `dashboard.py`：仪表盘和详情页 API 编排，归档核心算法委托给 `service/archive.py`。
- `folio.py`：豆瓣时间同步主流程，外层事件串行化由 `service/webhook.py` 承担。

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

所有 V3 新记录以完整 `media_source` 与字符串 `media_id` 为主身份。同来源旧主键字段在成功迁移后删除；跨源辅助 ID 可保留用于外链和展示。半身份、非法来源和字符串 `0` 不写入统一主身份。

## 关键调用链

- 定时 / 立即运行：`DoubanCenter.__run_all()` -> `feed.run_scheduled()` / `feed.run_once()` -> `feed.refresh_rank_data()` -> `feed.subscribe_to_ranks()`。
- 榜单订阅：`feed._process_coming()` / `feed._process_general()` / `feed._process_items()` -> `service/observation.py` -> `service/subscription.py`。
- 详情 API：`controller/api.py` -> `dashboard.py` -> `storage/records.py` / `service/archive.py`。
- 豆瓣时间：Webhook event -> `service/webhook.py` -> `folio.py` -> `DoubanApi`。

## 验收方式

- V3 聚焦测试：设置 `MOVIEPILOT_BACKEND_PATH` 为固定 V3 宿主后运行 `python -m pytest tests/v3/doubancenter -q`。
- Python 语法：`python -m compileall -q plugins.v3/doubancenter`。
- 联邦构建：`pnpm --dir plugins.v3/doubancenter build`，并确认 `dist/assets/remoteEntry.js` 引用的资产均存在。
- 版本门禁：解析 `package.v2.json` / `package.v3.json`，确认 V2 1.2.20 与 V3 3.0.0 分代一致。
- MP 本地闭环：优先同步到 `Z:\moviepilot-v2\config\local plugins` 的 V3 代际目录，GET reload 后分别回读 history、API、remotes 和静态资产。

## 禁止改动区

- 不 push Git 在线仓库，除非用户明确要求。
- 不改全局 MoviePilot 宿主逻辑，除非问题已定位为宿主契约缺口并单独确认。
- 不把新业务逻辑继续塞回 `__init__.py`。
- 不在验收中触发真实订阅、真实自动订阅或破坏性数据清理。
