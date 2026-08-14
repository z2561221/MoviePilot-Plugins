#!/usr/bin/env python3
"""将备份中心 AES-GCM 负载解密为 payload.zip。"""

import base64
import getpass
import hashlib
import json
import sys
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


CHUNK_SIZE = 1024 * 1024


def _decode(value, field):
    """读取并验证公开 manifest 中的 Base64 字段。"""
    try:
        return base64.b64decode(str(value or ""), validate=True)
    except Exception as error:
        raise ValueError(f"无效加密参数：{field}") from error


def decrypt(backup_root: Path, output_root: Path) -> None:
    """校验参数后将 payload.enc 解密为 payload.zip。"""
    manifest_path = backup_root / "manifest.public.json"
    encrypted_path = backup_root / "payload.enc"
    if not manifest_path.is_file() or not encrypted_path.is_file():
        raise FileNotFoundError("备份目录缺少 manifest.public.json 或 payload.enc")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    encryption = manifest.get("encryption") or {}
    kdf = encryption.get("kdf") or {}
    if encryption.get("format") != "backupcenter-aesgcm-v1":
        raise ValueError("不支持的备份加密格式")
    if {
        "name": kdf.get("name"),
        "n": kdf.get("n"),
        "r": kdf.get("r"),
        "p": kdf.get("p"),
    } != {"name": "scrypt", "n": 2**14, "r": 8, "p": 1}:
        raise ValueError("不支持的密钥派生参数")
    password = getpass.getpass("输入备份口令: ")
    if len(password) < 4:
        raise ValueError("口令至少需要 4 个字符")
    salt = _decode(kdf.get("salt"), "salt")
    nonce = _decode(encryption.get("nonce"), "nonce")
    tag = _decode(encryption.get("tag"), "tag")
    if len(salt) != 16 or len(nonce) != 12 or len(tag) != 16:
        raise ValueError("加密参数长度无效")
    key = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32
    )
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / "payload.zip"
    try:
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        with encrypted_path.open("rb") as input_file, destination.open("wb") as output_file:
            while chunk := input_file.read(CHUNK_SIZE):
                output_file.write(decryptor.update(chunk))
            output_file.write(decryptor.finalize())
    except InvalidTag as error:
        destination.unlink(missing_ok=True)
        raise ValueError("口令错误或加密负载已损坏") from error
    except (OSError, ValueError) as error:
        destination.unlink(missing_ok=True)
        raise ValueError("无法读取或写入加密备份负载") from error
    print(f"解密完成：{destination}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: decrypt-backup.py <备份目录> <解密输出目录>", file=sys.stderr)
        raise SystemExit(2)
    decrypt(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
