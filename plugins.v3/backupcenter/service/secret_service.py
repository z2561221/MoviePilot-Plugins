"""备份口令的宿主密钥加密存储服务。"""

import base64
import hashlib
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken

from app.sdk.config import settings

from .crypto_service import BackupCryptoError, CryptoService


class SecretServiceError(RuntimeError):
    """表示备份口令保存或读取失败。"""


class SecretService:
    """将备份口令密文保存到 BackupCenter 自身 PluginData。"""

    _data_key = "backup_password_secret"

    def __init__(self, plugin: Any) -> None:
        """绑定插件实例并派生本机口令加密密钥。"""
        self.plugin = plugin

    def _fernet(self) -> Fernet:
        """从 MoviePilot SECRET_KEY 和插件 ID 派生稳定 Fernet 密钥。"""
        secret_key = str(settings.SECRET_KEY or "").strip()
        if not secret_key:
            raise SecretServiceError("MoviePilot SECRET_KEY 不可用")
        material = f"{secret_key}:{self.plugin.__class__.__name__}:backup-password"
        key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
        return Fernet(key)

    def has_password(self) -> bool:
        """返回是否存在已保存的备份口令密文。"""
        record = self.plugin.get_data(self._data_key)
        return isinstance(record, dict) and bool(record.get("ciphertext"))

    def set_password(self, password: Any) -> None:
        """验证并密文保存备份口令。"""
        try:
            normalized = CryptoService.validate_password(password, allow_empty=False)
        except BackupCryptoError as error:
            raise SecretServiceError(str(error)) from error
        ciphertext = self._fernet().encrypt(normalized.encode("utf-8")).decode("ascii")
        self.plugin.save_data(self._data_key, {"version": 1, "ciphertext": ciphertext})

    def clear_password(self) -> None:
        """删除已保存的备份口令密文。"""
        self.plugin.del_data(self._data_key)

    def get_password(self) -> str:
        """解密并返回备份口令，未配置时返回空字符串。"""
        record: Dict[str, Any] | None = self.plugin.get_data(self._data_key)
        if not isinstance(record, dict) or not record.get("ciphertext"):
            return ""
        try:
            plaintext = self._fernet().decrypt(str(record["ciphertext"]).encode("ascii"))
            return plaintext.decode("utf-8")
        except (InvalidToken, UnicodeError, ValueError) as error:
            raise SecretServiceError("已保存的备份口令无法解密，请重新设置") from error
