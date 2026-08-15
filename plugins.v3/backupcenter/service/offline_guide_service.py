"""生成不含秘密的离线恢复教程与工具副本。"""

import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List


class OfflineGuideService:
    """将公开 manifest 转换为停机恢复所需的说明文件。"""

    _tool_names = (
        "verify-backup.ps1",
        "decrypt-backup.py",
        "restore-sqlite.ps1",
        "restore-postgresql.ps1",
    )

    @classmethod
    def _tools_source(cls) -> Path:
        """返回随插件分发的离线工具目录。"""
        return Path(__file__).resolve().parent.parent / "tools"

    @classmethod
    def copy_tools(cls, destination: Path) -> List[Path]:
        """复制校验与数据库恢复辅助工具到备份外层。"""
        destination.mkdir(parents=True, exist_ok=True)
        copied: List[Path] = []
        for tool_name in cls._tool_names:
            source = cls._tools_source() / tool_name
            if not source.is_file():
                raise RuntimeError(f"备份工具缺失：{tool_name}")
            target = destination / tool_name
            shutil.copy2(source, target)
            copied.append(target)
        return copied

    @staticmethod
    def _value(payload: Dict[str, Any], key: str, fallback: str = "未知") -> str:
        """读取公开字段并在缺失时提供不泄密的占位文本。"""
        value = str(payload.get(key) or "").strip()
        return value or fallback

    @classmethod
    def build_guide(cls, public_manifest: Dict[str, Any]) -> str:
        """生成包外明文恢复教程，不写入口令、令牌或绝对路径。"""
        database = public_manifest.get("database") or {}
        database_type = cls._value(database, "type", "未包含")
        backup_id = cls._value(public_manifest, "backup_id")
        source_version = cls._value(public_manifest, "source_mp_version")
        created_at = cls._value(public_manifest, "created_at")
        encrypted = bool((public_manifest.get("encryption") or {}).get("enabled"))
        payload_summary = (
            "AES-256-GCM 加密负载，密钥由 scrypt 从备份口令派生。"
            if encrypted
            else "普通 ZIP 负载，未设置备份口令。"
        )
        payload_step = (
            "5. 使用含 `cryptography` 的 Python 3 环境执行 `python tools\\decrypt-backup.py <本目录> <解密输出目录>`，按提示输入口令并得到 `payload.zip`；完全离线时请预先准备对应 wheel。"
            if encrypted
            else "5. 直接使用本目录中的 `payload.zip`。"
        )
        return f"""# MoviePilot 备份中心离线恢复教程

## 备份摘要

- 备份 ID：`{backup_id}`
- 创建时间：`{created_at}`
- 来源 MoviePilot：`{source_version}`
- 数据库类型：`{database_type}`
- 负载格式：{payload_summary}

本教程故意不包含 Cookie、API Token、数据库口令、数据库 URL、备份口令或原始绝对路径。无论负载是否加密，都应将备份包视为敏感文件并限制访问权限。

## 恢复前必须完成

1. 保留当前 MoviePilot 配置目录与数据库副本，确认可以回退。
2. 确认目标实例已完全停止；不要在运行中的 MoviePilot 上替换完整数据库。
3. 准备与来源兼容的 MoviePilot V3 和数据库客户端。
4. 在本目录执行 `tools\\verify-backup.ps1 -BackupRoot <本目录>`；任一哈希失败时立即停止。
{payload_step}
6. 使用压缩工具解压 `payload.zip`，再按数据库类型选择恢复步骤。

## SQLite 整库恢复

仅在 `database.type` 为 `sqlite` 且备份包含数据库快照时执行：

1. 解压后确认存在 `payload/database/user.db`。
2. 先保留目标 `user.db`、`user.db-wal`、`user.db-shm` 的副本。
3. 执行 `tools\\restore-sqlite.ps1`，它要求再次输入 `RESTORE` 后才会替换数据库。
4. 启动 MoviePilot，让其完成自身数据库迁移；检查启动日志、系统设置与插件清单。

## PostgreSQL 整库恢复

仅在 `database.type` 为 `postgresql` 且备份包含 `payload/database/moviepilot.dump` 时执行：

1. 让管理员准备空的目标数据库及具有恢复权限的账号。
2. 确认 `pg_restore --version` 与目标 PostgreSQL 主版本兼容。
3. 在当前终端设置 `PGHOST`、`PGPORT`、`PGUSER`、`PGDATABASE`、`PGPASSWORD`，再执行 `tools\\restore-postgresql.ps1 -Dump <payload/database/moviepilot.dump>`；脚本不会把口令放入命令行参数。
4. 脚本要求输入 `RESTORE`，并使用 `--clean --if-exists --no-owner --exit-on-error`；完成后再启动 MoviePilot。

## 选择性恢复

若只需要恢复设置、单个插件设置、`PluginData` 或插件标准数据目录，请启动 MoviePilot 后打开备份中心：先预览差异、创建应急备份、选择恢复项、确认恢复。插件会在写入前停用目标插件并在结束后逐个重载；完整数据库、`app.env` 与部署平台环境变量不属于在线恢复范围。

## 失败与回滚

- 哈希不匹配、数据库类型不一致、主版本不兼容或目标未停机时，停止恢复。
- 选择性恢复失败时，使用恢复前自动创建的应急备份。
- 离线整库恢复失败时，使用操作前保留的数据库/配置目录副本回退；不要在未知状态上继续覆盖。
"""

    @classmethod
    def build_checklist(cls, public_manifest: Dict[str, Any]) -> str:
        """生成可在终端或纸面逐项核对的离线恢复清单。"""
        backup_id = cls._value(public_manifest, "backup_id")
        encrypted = bool((public_manifest.get("encryption") or {}).get("enabled"))
        password_item = (
            "[ ] 已准备正确的备份口令并成功解密 payload.enc\n"
            if encrypted
            else "[ ] 已确认该备份为未加密 payload.zip\n"
        )
        return f"""MoviePilot 备份恢复核对清单
备份 ID: {backup_id}

[ ] 已停止目标 MoviePilot 实例
[ ] 已保留目标配置目录和数据库副本
[ ] 已确认来源与目标均为 MoviePilot V3
[ ] 已运行 verify-backup.ps1 且全部哈希通过
{password_item}[ ] 已准备兼容的数据库工具
[ ] 已按数据库类型选择正确恢复脚本
[ ] 已在脚本确认提示前复核目标位置
[ ] 已启动 MoviePilot 并检查迁移/启动日志
[ ] 已检查关键设置、插件清单和受影响插件数据
[ ] 已保留应急备份和恢复前副本，确认稳定后再清理
"""
