"""备份包 manifest、校验和与安全路径服务。"""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List


class ManifestError(RuntimeError):
    """表示 manifest 或备份文件完整性校验失败。"""


class ManifestService:
    """统一处理备份目录中的 JSON、哈希和路径验证。"""

    _chunk_size = 1024 * 1024
    _backup_id_pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")

    @classmethod
    def validate_backup_id(cls, backup_id: Any) -> str:
        """验证备份 ID，阻止目录穿越和歧义路径。"""
        value = str(backup_id or "").strip()
        if not cls._backup_id_pattern.fullmatch(value):
            raise ManifestError("备份 ID 无效")
        return value

    @staticmethod
    def write_json(path: Path, payload: Dict[str, Any]) -> None:
        """以稳定 UTF-8 格式写入 JSON 文件。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def read_json(path: Path) -> Dict[str, Any]:
        """读取并验证 JSON 对象根节点。"""
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:
            raise ManifestError(f"无法读取 {path.name}") from error
        if not isinstance(value, dict):
            raise ManifestError(f"{path.name} 必须是 JSON 对象")
        return value

    @classmethod
    def sha256_file(cls, path: Path) -> str:
        """计算文件 SHA-256，不将整个文件载入内存。"""
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(cls._chunk_size):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_relative(relative_path: str) -> Path:
        """验证校验清单中的相对 POSIX 路径。"""
        if "\\" in relative_path or ":" in relative_path:
            raise ManifestError("校验清单包含不安全路径")
        value = PurePosixPath(relative_path)
        if value.is_absolute() or ".." in value.parts or not value.parts:
            raise ManifestError("校验清单包含不安全路径")
        return Path(*value.parts)

    @classmethod
    def write_checksums(cls, root: Path, relative_paths: Iterable[Path]) -> None:
        """为指定文件生成不包含自身的 SHA-256 清单。"""
        rows: List[str] = []
        for relative_path in sorted(relative_paths, key=lambda item: item.as_posix()):
            target = root / relative_path
            if not target.is_file():
                raise ManifestError(f"无法生成校验和，文件缺失：{relative_path}")
            rows.append(f"{cls.sha256_file(target)}  {relative_path.as_posix()}")
        (root / "checksums.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")

    @classmethod
    def verify_checksums(cls, root: Path) -> List[str]:
        """验证备份外层全部校验和，并返回已验证文件列表。"""
        manifest = root / "checksums.sha256"
        if not manifest.is_file():
            raise ManifestError("缺少 checksums.sha256")
        verified: List[str] = []
        for raw_line in manifest.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                expected, relative = raw_line.split("  ", 1)
            except ValueError as error:
                raise ManifestError("校验清单格式无效") from error
            if not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ManifestError("校验清单中的 SHA-256 无效")
            safe_relative = cls._safe_relative(relative)
            target = root / safe_relative
            if not target.is_file():
                raise ManifestError(f"备份文件缺失：{relative}")
            if cls.sha256_file(target) != expected:
                raise ManifestError(f"备份文件校验失败：{relative}")
            verified.append(safe_relative.as_posix())
        if not verified:
            raise ManifestError("校验清单为空")
        return verified
