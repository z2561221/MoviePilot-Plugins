# DoubanCenter 插件上下文

## 插件用途

DoubanCenter 是 MoviePilot V2 本地插件，整合豆瓣榜单订阅、RSS 榜单刷新、观察队列、订阅历史、归档治理、豆瓣时间同步和 Vue 联邦页面展示。

## 当前重构目标

本插件正在按标准插件模板渐进重构。第一轮只建立 `ai_spec`、`controller`、`service`、`adapter`、`model`、`storage` 骨架并清理 Vue API 契约，不迁移核心业务逻辑。

## 标准模板边界

- `__init__.py`: 只保留插件生命周期、配置读取、API 路由声明、事件入口和服务注册。
- `controller/`: 负责前端 API 参数校验、异常包装和响应格式，不写核心业务。
- `service/`: 负责榜单、订阅、观察、归档、总览和豆瓣时间等业务逻辑。
- `adapter/`: 负责 RSSHub、Bangumi、MoviePilot MediaChain、SubscribeChain 等外部调用。
- `model/`: 负责内置榜单定义、默认值、常量和结构化记录字段约定。
- `storage/`: 负责 `get_data` / `save_data` 封装、历史记录去重、截断、归档恢复等持久化治理。
- `src/components/`: 过渡期保留 Vue 联邦源码；运行态仍依赖 `dist/assets/remoteEntry.js` 与关联产物。

## 主要入口

- `DoubanCenter.init_plugin`: 读取配置、初始化运行状态、触发一次性运行。
- `DoubanCenter.get_api`: 声明 Vue 前端使用的插件 API，路由必须使用 `auth: "bear"`。
- `DoubanCenter.get_service`: 注册定时任务。
- `DoubanCenter.get_render_mode`: 声明 Vue 联邦渲染，返回 `("vue", "dist/assets")`。
- `DoubanCenter.get_form`: Vue 模式下只返回默认配置模型。
- `DoubanCenter.get_page`: Vue 模式下不返回旧 Vuetify 页面树。
- `DoubanCenter.get_dashboard`: 返回首页仪表盘入口。
- `DoubanCenter.sync_log`: 接收媒体事件并委托豆瓣时间同步。
- `DoubanCenter.sync_played`: 从媒体事件中判断播放完成状态并委托同步。

## 主要数据 key

- `subscribe_records`: 自动订阅和手动订阅历史。
- `anti_cheat_logs`: 黑名单、观察期和过滤日志。
- `archive_records`: 详情页删除和溢出归档记录。
- `coming_history`: 即将上映榜单历史与观察状态。
- `rank_history_*`: 各 RSS 榜单历史，例如 `rank_history_bangumi`。
- `folio_data`: 豆瓣时间同步后的观影/追剧时间线数据。
- `folio_wait`: 豆瓣时间待处理队列。

## 主要调用链

### RSS 刷新链路

`api_refresh_rss` / 定时任务 -> `feed.refresh_rank_data` -> RSSHub 请求 -> XML 解析 -> 榜单历史合并 -> 仪表盘读取。

### 自动订阅链路

`feed.run_once` / `feed.run_scheduled` -> `feed.subscribe_to_ranks` -> 筛选条件检查 -> 媒体识别 -> 观察队列判断 -> `SubscribeChain.add` -> `subscribe_records` 写入。

### 观察队列链路

榜单候选 -> 观察期首次记录 -> `pending_observations` 展示 -> 用户删除或观察期满足 -> 订阅、忽略或归档。

### 归档治理链路

详情页删除、日志溢出、观察队列溢出 -> `archive_records` 写入 -> `archive_records` 分页展示 -> `restore_archive` 恢复或 `delete_archive` 永久删除。

### 豆瓣时间同步链路

MoviePilot Webhook 事件 -> `sync_log` / `sync_played` -> `folio.check_cookie_periodically` -> `folio.sync_log_handler` -> `folio_data` / `folio_wait` 更新。

### Vue 联邦页面 API 链路

Vue `Config` / `Page` / `Dashboard` 组件 -> 注入的 `api` prop -> `plugin/DoubanCenter/<path>` -> `get_api()` bearer 路由 -> 后端 API 方法。

## 禁止改动区域

- 不改变现有持久化 key 名称，除非同时提供迁移和回滚策略。
- 不让 Vue 前端默认回退裸 `fetch` 或浏览器端 API Token。
- 不让 `get_page()` 返回旧 Vuetify 页面树抢占 Vue 联邦渲染。
- 不在 `adapter/` 写业务判断。
- 不在 `controller/` 写核心业务。
- 不在 `utils.py` 继续堆有状态业务逻辑。
- 不绕过 MoviePilot `SubscribeChain`、`MediaChain`、`RequestUtils` 的现有约定。
- 不只修改 Win 本地仓而跳过 MP 本地仓同步和 reload 验收。

## 验收方式

- Python 语法检查：`python -B -m py_compile plugins.v2/doubancenter/*.py`
- 单元测试：`python -B -m unittest discover -s plugins.v2/doubancenter/tests`
- Vue 构建：在插件目录运行 `npm run build`
- 构建产物检查：确认 `dist/assets/remoteEntry.js` 存在且引用的 JS/CSS 文件存在。
- 本地同步：`python MoviePilot-Plugins/scripts/sync_to_mp_local.py --plugin DoubanCenter`
- MP reload：调用 `/api/v1/plugin/reload/DoubanCenter`
- 运行态回读：确认 `/api/v1/plugin/remotes`、`/api/v1/plugin/DoubanCenter/overview`、`/api/v1/plugin/DoubanCenter/pending_observations`、`/api/v1/plugin/DoubanCenter/anti_cheat_logs` 可用。

## 常见坑

- Vue API 必须走注入 `api` prop，对应后端路由必须声明 `auth: "bear"`。
- `remoteEntry.js` 文件名稳定，浏览器或 federation loader 缓存可能导致页面不更新。
- `dist/assets` 是运行必需产物，源码恢复不代表运行态会自动使用源码。
- `feed.py` 和 `dashboard.py` 当前仍是过渡期兼容壳，迁移时必须保持同名函数测试通过。
- `rank_history_*` 和 `coming_history` 中存在历史字段兼容逻辑，不能只按新字段读取。
