# DoubanCenter AI Context

## 插件用途

DoubanCenter 是 MoviePilot V2 本地插件，整合豆瓣榜单订阅、豆瓣时间同步、仪表盘概览、观察期治理和归档管理。

## 入口与渲染

- 主类入口：`__init__.py` 中的 `DoubanCenter`。
- API 路由：`controller/api.py`，只做路由声明、入参转换、异常兜底和转发。
- 渲染模式：`get_render_mode()` 返回 `("vue", "dist/assets")`。
- Vue 联邦运行产物：`dist/assets/remoteEntry.js` 及其引用资源。
- 禁止未确认时修改 Vue 联邦产物：`src/`、`dist/`、`remoteEntry.js`、`vite.config.js`、前端构建依赖都需要用户确认后再动。

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

## 关键调用链

- 定时 / 立即运行：`DoubanCenter.__run_all()` -> `feed.run_scheduled()` / `feed.run_once()` -> `feed.refresh_rank_data()` -> `feed.subscribe_to_ranks()`。
- 榜单订阅：`feed._process_coming()` / `feed._process_general()` / `feed._process_items()` -> `service/observation.py` -> `service/subscription.py`。
- 详情 API：`controller/api.py` -> `dashboard.py` -> `storage/records.py` / `service/archive.py`。
- 豆瓣时间：Webhook event -> `service/webhook.py` -> `folio.py` -> `DoubanApi`。

## 验收方式

- Python 语法：`python -m compileall -q plugins.v2/doubancenter`。
- 行为回归：`python -m unittest discover -s plugins.v2/doubancenter/tests -p "test_*.py"`。
- 静态前端契约：`python -m pytest tests/static/test_doubancenter_native_subscribe.py tests/static/test_doubancenter_observation_order.py`。
- MP 本地闭环：同步到 `Z:\moviepilot-v2\config\local plugins`，调用 `/api/v1/plugin/reload/DoubanCenter`，再回读 `/api/v1/plugin/ state=installed force=true`。

## 禁止改动区

- 未经用户确认，不修改 Vue 联邦源码和产物。
- 不 push Git 在线仓库，除非用户明确要求。
- 不改全局 MoviePilot 宿主逻辑，除非问题已定位为宿主契约缺口并单独确认。
- 不把新业务逻辑继续塞回 `__init__.py`。
