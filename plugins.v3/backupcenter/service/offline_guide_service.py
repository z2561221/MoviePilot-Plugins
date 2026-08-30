"""生成不含秘密的逻辑恢复教程与校验工具副本。"""

import shutil
from pathlib import Path
from typing import Any, Dict, List


class OfflineGuideService:
    """将公开 manifest 转换为逻辑恢复说明，不重复实现宿主整库恢复。"""

    _tool_names = ("verify-backup.ps1", "decrypt-backup.py")

    @classmethod
    def _tools_source(cls) -> Path:
        """返回随插件分发的离线工具目录。"""
        return Path(__file__).resolve().parent.parent / "tools"

    @classmethod
    def copy_tools(cls, destination: Path) -> List[Path]:
        """复制校验与解密辅助工具到备份外层。"""
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
            "5. 使用含 `cryptography` 的 Python 3 环境执行 "
            "`python tools\\decrypt-backup.py <本目录> <解密输出目录>`，"
            "按提示输入口令并得到 `payload.zip`；完全离线时请预先准备对应 wheel。"
            if encrypted
            else "5. 直接使用本目录中的 `payload.zip`。"
        )
        return f"""# MoviePilot 备份中心恢复教程

## 备份摘要

- 备份 ID：`{backup_id}`
- 创建时间：`{created_at}`
- 来源 MoviePilot：`{source_version}`
- 负载格式：{payload_summary}

本教程不包含 Cookie、API Token、数据库口令、连接 URL、备份口令或原始绝对路径。备份包仍应按敏感文件限制访问权限。

## 恢复前检查

1. 保留当前 MoviePilot 配置目录与数据库副本，确认可以回退。
2. 执行 `tools\\verify-backup.ps1 -BackupRoot <本目录>`；任一哈希失败时立即停止。
{payload_step}
6. 使用压缩工具解压 `payload.zip`，确认目标 MoviePilot 为同一主版本。

## 选择性恢复

启动 MoviePilot 后打开备份中心：先预览差异，再创建恢复前应急备份，最后选择设置、PluginData 或插件标准数据目录进行恢复。插件会在写入前停用目标插件并在结束后逐个重载。

## 数据库恢复边界

完整数据库备份与停机恢复由 MoviePilot 主程序统一管理。备份中心不会导出、替换或删除数据库文件；
在线选择性恢复开始前会请求宿主创建一个数据库恢复点。需要整库回退时，请使用宿主提供的数据库备份列表、校验与恢复命令。

## 失败与回滚

- 哈希不匹配、主版本不兼容或负载无法解密时，停止恢复。
- 选择性恢复失败时，优先使用恢复前自动创建的应急备份和宿主数据库恢复点。
- 未经停机和宿主确认，不要替换数据库文件或执行整库导入。
"""

    @classmethod
    def build_checklist(cls, public_manifest: Dict[str, Any]) -> str:
        """生成可在终端或纸面逐项核对的恢复清单。"""
        backup_id = cls._value(public_manifest, "backup_id")
        encrypted = bool((public_manifest.get("encryption") or {}).get("enabled"))
        password_item = (
            "[ ] 已准备正确的备份口令并成功解密 payload.enc\n"
            if encrypted
            else "[ ] 已确认该备份为未加密 payload.zip\n"
        )
        return f"""MoviePilot 备份恢复核对清单
备份 ID: {backup_id}

[ ] 已确认来源与目标均为 MoviePilot V3
[ ] 已运行 verify-backup.ps1 且全部哈希通过
{password_item}[ ] 已确认数据库恢复由 MoviePilot 主程序管理
[ ] 在线恢复前已创建宿主数据库恢复点
[ ] 已预览差异并确认目标插件范围
[ ] 已保留恢复前应急备份
[ ] 已检查设置、插件清单和受影响插件数据
"""
