# DoubanCenter v1.2.7 运行验收记录

## 验收范围

- 插件安装状态与运行版本。
- Vue 联邦 remote 注册状态。
- 配置、概览、统计、榜单历史、豆瓣时间只读接口。
- 重载后的运行日志。

本轮只做只读验收，未触发 `/refresh_rss`、`/subscribe`、删除、恢复或归档写入接口。

## 运行端证据

- `GET /api/v1/plugin/installed` 返回包含 `DoubanCenter`。
- `GET /api/v1/plugin/ state=installed force=true` 返回：
  - `id = DoubanCenter`
  - `plugin_version = 1.2.7`
  - `installed = true`
  - `state = true`
  - `has_page = true`
  - `is_local = true`
- `GET /api/v1/plugin/remotes token=moviepilot` 返回：
  - `id = DoubanCenter`
  - `url = /plugin/file/doubancenter/dist/assets/remoteEntry.js`
  - `name = 豆瓣中心`
- `GET /api/v1/plugin/DoubanCenter` 返回当前配置，插件启用且定时表达式为 `45 12,20 * * *`。
- `GET /api/v1/plugin/DoubanCenter/overview` 返回 `code = 0`，包含 `rss`、`subscribe`、`archive`、`observe`、`folio` 卡片。
- `GET /api/v1/plugin/DoubanCenter/stats` 返回订阅统计，`total = 5`。
- `GET /api/v1/plugin/DoubanCenter/rank_history` 返回 `coming`、`tv_real_time`、`tv_chinese`、`tv_global`、`movie_weekly`、`bangumi` 榜单数据。
- `GET /api/v1/plugin/DoubanCenter/folio_data` 返回豆瓣时间数据。

## 日志证据

`Z:\moviepilot-v2\config\logs\moviepilot.log` 中观测到：

- `加载插件：DoubanCenter 版本：1.2.7`
- `注册插件豆瓣中心服务：豆瓣中心定时服务 - cron[month='*', day='*', day_of_week='*', hour='12,20', minute='45']`
- `/api/v1/plugin/DoubanCenter/*` 路由完成移除后重新添加。

未在本轮回读片段中发现 DoubanCenter 相关 `Traceback`。
