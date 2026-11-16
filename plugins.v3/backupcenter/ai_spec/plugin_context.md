# 备份中心稳定上下文

## 插件定位

`BackupCenter` 是面向 MoviePilot V3 的原生代际 Vue 联邦插件。宿主通过 `plugins.v3/backupcenter` 与 `package.v3.json` 加载当前 V3-only 实现，不为它建立或改动 V2 条目。当前维护版本 3.0.10，沿用已批准的 3.x 版本序列。

插件不修改 MoviePilot 主程序。它负责创建可选加密的校验逻辑备份、校验并导出自说明恢复包，以及执行受限的在线选择性恢复。完整数据库恢复始终要求管理员停机，并由主程序统一管理。

## 入口与页面

- 插件类：`BackupCenter`，配置前缀 `backupcenter_`，宿主最低版本 `>=3.0.0`。
- 渲染模式：`("vue", "dist/assets")`。
- 联邦暴露：`./Config`、`./Page`、`./AppPage`；不注册独立侧栏入口。`AppPage` 负责把详情页右上角的配置快捷按钮接入配置弹窗。
- 所有业务 API 均声明 `auth: "bear"`，并在控制器内再次要求 `TokenPayload.super_user=true`；浏览器只能通过宿主注入的 `api` 客户端调用。
- 第二阶段支持标准五段 Cron 周期自动备份，默认每周六 03:00，默认保留 5 份自动备份；新安装默认只备份插件设置、`PluginData` 与标准数据目录。每次自动任务把配置范围内的内容与全部已安装插件打成一个包，默认名称为 `自动备份-日期`。
- 详情页只负责手动备份与单份备份恢复；配置页负责周期、周期范围、保留数量和口令设置。备份口令仅在配置页通过独立 Bearer API 设置、更新或清除；普通插件配置保存启用状态、执行时间、周期范围和保留数量。
- 手动备份可明确切换 `MoviePilot / 插件`，所有范围默认不选择。MoviePilot 模式提供系统设置、`app.env`、全部插件设置、Cookie、全部插件 `PluginData`、插件文件和缓存；插件模式每次必须选择一个插件，并提供“配置 / 数据”。手动包默认名称为 `MoviePilot-配置/数据/配置和数据-日期` 或 `插件中文名-配置/数据/配置和数据-日期`。
- 备份口令最低 4 个字符；未设置口令时生成普通 ZIP，设置口令后使用 AES-256-GCM 加密。
- 口令以宿主 `SECRET_KEY` 派生密钥加密后保存在 BackupCenter 自身 `PluginData`，前端只能读取“已设置/未设置”状态，不回显口令。

## 备份链路

1. 在原操作锁内形成一次新鲜的 `BackupCreationContext`，读取系统配置与真实实例目录、排除同源家族，再按同一选择解析名称。仅查询插件选项时读取 `UserInstalledPlugins`，不读取完整配置。
2. 插件配置通过 `get_config(plugin_id=...)` 读取，`PluginData` 通过公开数据接口导出，标准目录通过 `get_data_path(plugin_id=...)` 定位；旧宿主才回退旧配置/目录。`BackupCenter` 本体和全部同源分身始终从插件范围排除，避免历史备份递归嵌套。
3. 负载 ZIP 内写入私有 manifest、逻辑数据、文件、空目录及 `docs/` 教程副本；保留存在但为空的插件根目录，缺席的目录不伪造为空目录。
4. 未设置口令时保存普通 `payload.zip`；设置口令时使用 scrypt 派生密钥并以流式 AES-256-GCM 保存为 `payload.enc`。两种格式的外层文件都使用 SHA-256 清单校验。
5. 外层生成公开 manifest、恢复教程、核对清单、校验和及离线工具。
6. 在线与离线校验均要求清单包含 `manifest.public.json` 和加密状态对应的 `payload.enc` / `payload.zip`，逐项验证文件存在与哈希。导出 API 在校验通过后生成临时 ZIP，响应完成后删除临时文件。

自动备份与手动备份使用同一种清单格式。自动包和 MoviePilot 手动包可以在恢复时选择“配置”或“数据”，并进一步选择一个或多个已打包插件。单插件手动包恢复时仍可只恢复配置或只恢复数据。

`service/backup_catalog.py` 管理目录、公开清单、索引和自动保留，`backup_service.py` 继续负责收集与创建负载并保留旧调用入口。公开列表保持 `package_size` 与原字段；自动保留使用轻量清单，不递归计算体积，仍只处理最旧自动包，保护手动、应急及指定保留包。创建上下文与目录清单不做跨请求缓存。

## 恢复边界

- 在线恢复只允许相同 MoviePilot 主版本。
- 完整数据库、`app.env` 与部署平台环境变量不在线恢复。
- 在线恢复前必须先通过备份包校验，再创建宿主数据库恢复点和新的插件应急备份；任一步失败都不开始恢复写入。
- 恢复插件 ID 必须符合 MoviePilot 类名格式，并且存在于备份私有范围中。
- 在线恢复拒绝 `BackupCenter` 本体与同源分身，避免在请求处理中停止或覆盖当前插件。
- 解密后必须核对公开与私有 manifest 的 ID、版本、范围、插件列表和计数。
- `service/restore_payload.py` 在安全解包和清单一致性校验后，为本次请求建立新的 `RestorePayloadPlan`。系统与插件配置 JSON 各解析一次，选中的 PluginData 行在创建宿主恢复点及停止目标之前验证；配置缺失用 `None` 保留，数据保留文件存在性、目标身份和已验证行，空根对象、显式空配置/数据列表和未包含目标键分别处理。原始数据行字典不跨阶段保留，配置写入后释放对应负载，目录阶段只保留实时补偿快照。
- `restore_service.py` 协调当前现场 snapshot、停止/重载、写入与补偿，旧 Path callable 入口继续有效。只复用本次已解包负载，不能复用上一请求预检或现用数据作为恢复负载。
- 系统设置通过宿主 `SystemConfigOper.set()` 逐项提交；插件配置通过基类 `get_config/update_config` 访问实际实例。它们不承诺跨键全局事务，失败时按 `modified_scopes` 对已开始写入的范围补偿，补偿失败才使用应急备份回退。
- `PluginData` 只通过插件公开的 `get_data/save_data/del_data` 接口读写；恢复前保存全部目标插件快照，任何写入异常都清理半成品并补偿回滚。
- 插件恢复前停止当时处于运行态的目标插件，完成或失败后逐个重载；重载失败项由 `reload_required` 明确返回。
- 恢复预检绑定请求代次、API、实例及备份 ID；选择变化或卸载后旧回包不再打开确认框，提交只使用已核验预检的 ID。
- 重载必须同时刷新动态 API、命令与任务注册，失败进入 `reload_required`。`app.application.plugin.management.refresh_plugin_registrations` 是按宿主 `338687bee8` 验证的精确兼容例外，登记于 `.github/plugin-quality-exceptions.json`；稳定 SDK 提供等价入口后移除。守护用例为 `test_reload_rebinds_apis_to_restored_instance_and_reports_registration_failure`。
- 插件标准数据目录先复制到同卷临时目录，再逐插件原子替换；多个插件目录之间不承诺全局原子性。
- 外层 SHA-256、AES-GCM、ZIP 危险/重复路径检查、100000 成员与 20 GiB 总展开限制不能省略。目录缺失必须跳过，不能当作空目录清除现场数据。

## 备份包结构

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

- 数据库整库备份与恢复由 MoviePilot 主程序统一管理；插件只请求宿主创建恢复点，不导出、替换或删除数据库文件。
- 禁止把口令、派生密钥、数据库凭据或敏感配置值写入日志、公开 manifest 或前端持久化状态。
- 禁止把媒体文件、下载内容、外部服务数据库、Docker 卷或插件代码纳入默认范围。
- 在线恢复前必须创建宿主数据库恢复点；插件逻辑恢复失败时不得自行回滚宿主数据库。
- 禁止只修改联邦源码而不重建并提交 `dist/assets` 全部引用资源。
- 未经明确确认，禁止 push、合并、发布或对生产数据库执行真实恢复。

## 验收

从插件仓根目录执行：

Windows 使用 PowerShell 7 和现用 `D:/AIGC/All In Docker/MoviePilot/.venv-test/Scripts/python.exe`。明确设置匹配宿主的 `MOVIEPILOT_BACKEND_PATH`，CONFIG_DIR、TEMP、TMP、字节码和 pytest 输出均归本任务 active archive 批次。静态替身和宿主 V3 测试必须分进程运行，不把两个命名空间混进同一 pytest 会话。

```powershell
$mpPython = 'D:/AIGC/All In Docker/MoviePilot/.venv-test/Scripts/python.exe'
& $mpPython -X utf8 -B -m pytest -p no:cacheprovider --confcutdir=tests/static tests/static/test_backupcenter_services.py -k restore -q
& $mpPython -X utf8 -B -m pytest -p no:cacheprovider --confcutdir=tests/v3/backupcenter tests/v3/backupcenter/test_api_contract.py -q
& $mpPython -X utf8 -B -m ruff check --no-cache plugins.v3/backupcenter
git diff --check
```

本地运行态闭环为：受影响路径窄测试与必要的前端构建通过 -> 目标插件同步到 MP 本地仓库并按需安装 -> 目标插件 POST reload -> `/api/v1/plugin/history/BackupCenter` 回读版本、history、`installed=true`、布尔 `state` 与 `is_local=true`，并回读受影响 API；state 对照本任务实际开关，不单凭它判断加载健康。未变化的前端源码和产物复用已有证据；文件同步和哈希一致本身不代表运行态已验收。浏览器页面验收默认由用户完成，Codex 仅在明确授权后使用指定浏览器的任务专用新标签页。
