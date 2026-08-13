# 备份中心稳定上下文

## 插件定位

`BackupCenter` 是面向 MoviePilot V3 的 V2 格式 Vue 联邦插件。宿主通过 V3 的 V2 插件兼容层加载 `plugins.v2/backupcenter` 与 `package.v2.json`；当前没有假设或实现 `plugins.v3`、`package.v3.json` 等尚未公开的原生格式。

插件不修改 MoviePilot 主程序。它负责创建可选加密的校验逻辑备份和完整数据库快照、校验并导出自说明离线恢复包，以及执行受限的在线选择性恢复。完整数据库恢复始终要求管理员停机后执行。

## 入口与页面

- 插件类：`BackupCenter`，配置前缀 `backupcenter_`，宿主最低版本 `>=3.0.0`。
- 渲染模式：`("vue", "dist/assets")`。
- 联邦暴露：`./Config`、`./Page`、`./AppPage`；不注册独立侧栏入口。`AppPage` 负责把详情页右上角的配置快捷按钮接入配置弹窗。
- 所有业务 API 均声明 `auth: "bear"`，并在控制器内再次要求 `TokenPayload.super_user=true`；浏览器只能通过宿主注入的 `api` 客户端调用。
- 第二阶段支持标准五段 Cron 周期自动备份，默认每周六 03:00，默认保留 5 份自动备份；周期范围由配置页保存，默认不包含 Cookie 和完整数据库快照。每次自动任务把配置范围内的全局内容与全部已安装插件打成一个包，默认名称为 `自动备份-日期`。
- 详情页只负责手动备份与单份备份恢复；配置页负责周期、周期范围、保留数量和口令设置。备份口令仅在配置页通过独立 Bearer API 设置、更新或清除；普通插件配置保存启用状态、执行时间、周期范围和保留数量。
- 手动备份可明确切换 `MoviePilot / 插件`，所有范围默认不选择。MoviePilot 模式提供系统设置、`app.env`、全部插件设置、Cookie、全部插件 `PluginData`、插件文件和缓存、完整数据库细项；插件模式每次必须选择一个插件，并提供“配置 / 数据”。手动包默认名称为 `MoviePilot-配置/数据/配置和数据-日期` 或 `插件中文名-配置/数据/配置和数据-日期`。
- 备份口令最低 4 个字符；未设置口令时生成普通 ZIP，设置口令后使用 AES-256-GCM 加密。
- 口令以宿主 `SECRET_KEY` 派生密钥加密后保存在 BackupCenter 自身 `PluginData`，前端只能读取“已设置/未设置”状态，不回显口令。

## 备份链路

1. 从 `SystemConfig` 读取非插件设置、插件配置和已安装插件清单。
2. 从 `PluginData` 按插件 ID 导出逻辑数据，并复制 `config/plugins/<PluginID>/` 标准数据目录；`BackupCenter` 自身始终从插件范围排除，避免历史备份递归嵌套。
3. SQLite 使用 Online Backup API；PostgreSQL 使用 `pg_dump -Fc`。
4. 负载 ZIP 内写入私有 manifest、逻辑数据、文件、数据库快照及 `docs/` 教程副本。
5. 未设置口令时保存普通 `payload.zip`；设置口令时使用 scrypt 派生密钥并以流式 AES-256-GCM 保存为 `payload.enc`。两种格式的外层文件都使用 SHA-256 清单校验。
6. 外层生成公开 manifest、恢复教程、核对清单、校验和及离线工具。
7. 导出 API 在校验通过后生成临时 ZIP，响应完成后删除临时文件。

自动备份与手动备份使用同一种清单格式。自动包和 MoviePilot 手动包可以在恢复时选择“配置”或“数据”，并进一步选择一个或多个已打包插件；完整数据库快照仍只能离线整体恢复。单插件手动包恢复时仍可只恢复配置或只恢复数据。

## 恢复边界

- 在线恢复只允许相同 MoviePilot 主版本。
- 完整数据库、`app.env` 与部署平台环境变量不在线恢复。
- 在线恢复前必须创建新的校验应急备份；当前配置页存在口令时应急备份同样加密，失败则不开始写入。
- 恢复插件 ID 必须符合 MoviePilot 类名格式，并且存在于备份私有范围中。
- 在线恢复拒绝 `BackupCenter` 自身，避免在请求处理中停止或覆盖当前插件。
- 解密后必须核对公开与私有 manifest 的 ID、版本、范围、插件列表、计数和数据库信息。
- 系统设置与插件配置通过宿主 `SystemConfigOper.set()` 逐项提交，以同步其内存缓存；它们不承诺跨键全局事务，失败时必须使用应急备份回退。
- `PluginData` 在一个 `ScopedSession` 事务中完成删除和重建；任何写入异常必须回滚。
- 插件恢复前停止当时处于运行态的目标插件，完成或失败后逐个重载；重载失败项由 `reload_required` 明确返回。
- 插件标准数据目录先复制到同卷临时目录，再逐插件原子替换；多个插件目录之间不承诺全局原子性。

## 离线包结构

```text
<显示名称>/
  RECOVERY-GUIDE.md
  RECOVERY-CHECKLIST.txt
  manifest.public.json
  payload.zip | payload.enc
  checksums.sha256
  tools/
```

普通负载或解密后的 `payload.zip` 包含 `payload/docs/RECOVERY-GUIDE.md` 和 `payload/docs/RECOVERY-CHECKLIST.txt`。加密包同时携带独立 `tools/decrypt-backup.py`，完全离线时需预先准备 `cryptography` wheel。包外与包内教程均不得包含 Cookie、Token、数据库口令、连接 URL、加密口令或宿主绝对路径。

导出文件名直接使用 `<显示名称>.zip`。内部 `backup_id` 继续保存在 manifest 中作为校验、确认和删除使用的稳定标识，不再拼入用户可见文件名。

## 禁止改动区域

- 禁止加入运行中整库导入、数据库文件替换或自动停启 MoviePilot。
- 禁止把口令、派生密钥、数据库凭据或敏感配置值写入日志、公开 manifest 或前端持久化状态。
- 禁止把媒体文件、下载内容、外部服务数据库、Docker 卷或插件代码纳入默认范围。
- 禁止跨 SQLite/PostgreSQL 执行整库恢复；跨库只允许逻辑数据迁移。
- 禁止只修改联邦源码而不重建并提交 `dist/assets` 全部引用资源。
- 未经明确确认，禁止 push、合并、发布或对生产数据库执行真实恢复。

## 验收

从插件仓根目录执行：

```powershell
& '<python>' -m compileall -q plugins.v2\backupcenter
& '<python>' -m pytest -q tests\static\test_backupcenter_contracts.py plugins.v2\backupcenter\tests
& '<pnpm>' --dir plugins.v2\backupcenter\frontend build
git diff --check
```

本地运行态闭环为：窄测试和前端构建通过 -> 目标插件同步到 MP 本地仓库 -> GET reload -> `/api/v1/plugin/history/BackupCenter` 回读版本、history 和 `is_local=true` -> 用户 Chrome 新标签页完成桌面与 `390x844` 验收。文件同步和哈希一致本身不代表运行态已验收。
