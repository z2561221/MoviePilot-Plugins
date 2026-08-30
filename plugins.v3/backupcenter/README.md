# BackupCenter V3

BackupCenter 负责 MoviePilot 的插件逻辑备份与选择性恢复，不重复实现主程序的整库备份。

## 职责边界

- 默认自动备份范围为插件设置、`PluginData` 和插件标准数据目录。
- 手动备份可按需选择 MoviePilot 设置、`app.env` 和登录 Cookie；这些范围默认关闭。
- MoviePilot 完整数据库的备份与整库恢复由主程序负责，插件不会生成、替换或删除数据库快照。
- 每次在线恢复逻辑数据前，插件调用宿主 `app.sdk.database.create_backup()` 创建恢复点；宿主恢复点失败时不会写入插件数据。

## 恢复方式

- 在线恢复：只替换备份中实际存在的设置、`PluginData` 和插件标准数据目录；插件数据写入失败时自动恢复写入前快照，完成后 reload 受影响插件。
- 整库恢复：使用 MoviePilot 主程序提供的停机恢复命令。BackupCenter 只提供备份包校验和恢复说明，不在运行中执行整库替换。
- 旧版 V2 备份包仍可读取和预检；V3 新备份包不再写入 `database` 清单或数据库文件。

## 安全与存储

- 备份包保存在插件数据目录的 `BackupCenter/backups` 下。
- 可选 AES-GCM 加密、口令校验和文件 SHA-256 清单均由插件维护。
- 备份包外层包含不含敏感值的恢复说明，便于离线校验和交接。

## 运行要求

- MoviePilot `>= 3.0.0`
- MoviePilot V3 原生插件格式
- 仅超级用户可调用备份、校验和恢复 API
