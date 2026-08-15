"""备份负载的可选 AES-GCM 加解密服务。"""

import base64
import hashlib
import os
from pathlib import Path
from typing import Any, Dict

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class BackupCryptoError(RuntimeError):
    """表示备份口令或加密负载无效。"""


class CryptoService:
    """使用 scrypt 派生密钥并以 AES-256-GCM 保护负载。"""

    _format = "backupcenter-aesgcm-v1"
    _scrypt_n = 2**14
    _scrypt_r = 8
    _scrypt_p = 1
    _chunk_size = 1024 * 1024

    @staticmethod
    def _encode(value: bytes) -> str:
        """将二进制加密参数编码为 Base64 文本。"""
        return base64.b64encode(value).decode("ascii")

    @staticmethod
    def _decode(value: Any, field: str) -> bytes:
        """读取并验证 Base64 加密参数。"""
        try:
            return base64.b64decode(str(value or ""), validate=True)
        except Exception as error:
            raise BackupCryptoError(f"无效加密参数：{field}") from error

    @classmethod
    def validate_password(cls, password: Any, allow_empty: bool = True) -> str:
        """验证可选备份口令并返回规范化文本。"""
        value = str(password or "")
        if not value and allow_empty:
            return ""
        if len(value) < 4:
            raise BackupCryptoError("备份口令至少需要 4 个字符")
        return value

    @classmethod
    def _derive_key(cls, password: str, salt: bytes) -> bytes:
        """使用 scrypt 从口令派生 256 位 AES 密钥。"""
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=cls._scrypt_n,
            r=cls._scrypt_r,
            p=cls._scrypt_p,
            dklen=32,
        )

    @classmethod
    def encrypt_file(cls, source: Path, destination: Path, password: Any) -> Dict[str, Any]:
        """将源文件加密写入目标路径并返回公开加密参数。"""
        normalized = cls.validate_password(password, allow_empty=False)
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = cls._derive_key(normalized, salt)
        try:
            encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
            with source.open("rb") as input_file, destination.open("wb") as output_file:
                while chunk := input_file.read(cls._chunk_size):
                    output_file.write(encryptor.update(chunk))
                output_file.write(encryptor.finalize())
            tag = encryptor.tag
        except (OSError, ValueError) as error:
            destination.unlink(missing_ok=True)
            raise BackupCryptoError("无法写入加密备份负载") from error
        return {
            "enabled": True,
            "format": cls._format,
            "cipher": "AES-256-GCM",
            "kdf": {
                "name": "scrypt",
                "n": cls._scrypt_n,
                "r": cls._scrypt_r,
                "p": cls._scrypt_p,
                "salt": cls._encode(salt),
            },
            "nonce": cls._encode(nonce),
            "tag": cls._encode(tag),
        }

    @classmethod
    def decrypt_file(
        cls, source: Path, destination: Path, password: Any, encryption: Dict[str, Any]
    ) -> None:
        """依据公开参数解密负载到目标路径。"""
        normalized = cls.validate_password(password, allow_empty=False)
        header = encryption or {}
        if header.get("format") != cls._format or header.get("cipher") != "AES-256-GCM":
            raise BackupCryptoError("不支持的备份加密格式")
        kdf = header.get("kdf") or {}
        expected = {
            "name": "scrypt",
            "n": cls._scrypt_n,
            "r": cls._scrypt_r,
            "p": cls._scrypt_p,
        }
        if any(kdf.get(key) != value for key, value in expected.items()):
            raise BackupCryptoError("不支持的密钥派生参数")
        salt = cls._decode(kdf.get("salt"), "salt")
        nonce = cls._decode(header.get("nonce"), "nonce")
        tag = cls._decode(header.get("tag"), "tag")
        if len(salt) != 16 or len(nonce) != 12 or len(tag) != 16:
            raise BackupCryptoError("加密参数长度无效")
        key = cls._derive_key(normalized, salt)
        try:
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            with source.open("rb") as input_file, destination.open("wb") as output_file:
                while chunk := input_file.read(cls._chunk_size):
                    output_file.write(decryptor.update(chunk))
                output_file.write(decryptor.finalize())
        except InvalidTag as error:
            destination.unlink(missing_ok=True)
            raise BackupCryptoError("备份口令错误或加密负载已损坏") from error
        except (OSError, ValueError) as error:
            destination.unlink(missing_ok=True)
            raise BackupCryptoError("无法读取或写入加密备份负载") from error
