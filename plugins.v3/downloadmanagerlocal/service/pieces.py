"""通用 Pieces-hash 指纹工具。"""

import hashlib
import re
import time
from contextlib import suppress
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import PurePosixPath

from app.sdk.logging import logger
from bencode import bdecode

from ..adapter.moviepilot import is_flux_site, pieces_hash_url, request_pieces_res
from ..model.state import record_pieces_result

MAX_TORRENT_BYTES = 16 * 1024 * 1024


def count_result(plugin, *, success: bool) -> None:
    """统计写入不是提交回执；失败时不能重放已经提交的铺种任务。"""
    with suppress(Exception):
        record_pieces_result(plugin, success=success)
        return
    logger.warning("辅助铺种统计未能写入；不重放本次铺种操作")


def parse_site_keys(text: str, sites: list[dict]) -> list[dict]:
    """按精确站名解析参与站点，错误只显示行号并避免泄露凭据。"""
    resolved = {}
    by_name = {}
    for site in sites:
        by_name.setdefault(site.get("name"), []).append(site)
    for line_number, line in enumerate(str(text or "").splitlines(), 1):
        if not line.strip():
            continue
        name, separator, values = line.partition(":")
        fields = [field.strip() for field in values.split(",")]
        if not separator or not name.strip() or len(fields) not in (2, 3) or not all(fields):
            raise ValueError(f"第 {line_number} 行应为 站名:/查询路径,Passkey，可在末尾加 ,秒数")
        query_path, passkey = fields[:2]
        if not all(char.isprintable() and not char.isspace() for char in passkey):
            raise ValueError(f"第 {line_number} 行凭据格式无效")
        interval = fields[2] if len(fields) == 3 else "1"
        if not re.fullmatch(r"[0-9]{1,5}", interval) or not 1 <= int(interval) <= 86400:
            raise ValueError(f"第 {line_number} 行请求间隔应为 1 至 86400 的整数")
        matches = by_name.get(name.strip(), [])
        if len(matches) != 1 or not matches[0].get("id"):
            raise ValueError(f"第 {line_number} 行站点名称不存在或不唯一")
        site = dict(matches[0])
        base = str(site.get("url") or site.get("domain") or "").rstrip("/")
        if site.get("is_active") is False:
            raise ValueError(f"第 {line_number} 行站点已停用")
        site.update(url=base + "/", query_path=query_path, passkey=passkey, interval=int(interval))
        try:
            pieces_hash_url(site)
        except ValueError as error:
            raise ValueError(f"第 {line_number} 行：{error}") from None
        identity = str(site["id"])
        if identity in resolved and any(site[key] != resolved[identity][key] for key in ("query_path", "passkey", "interval")):
            raise ValueError(f"第 {line_number} 行重复站点的配置不一致")
        resolved[identity] = site
    if not resolved:
        raise ValueError("请填写辅助铺种站点的查询路径与凭据")
    return list(resolved.values())


def _bencode_end(content: bytes, offset: int, depth: int = 0) -> int:
    """定位原始 bencode 值的结束位置，保留 info 字典原始编码。"""
    if depth > 64 or offset >= len(content):
        raise ValueError("torrent 编码层级或长度无效")
    token = content[offset:offset + 1]
    if token == b"i":
        end = content.index(b"e", offset + 1)
        int(content[offset + 1:end])
        return end + 1
    if token in (b"d", b"l"):
        cursor = offset + 1
        while cursor < len(content) and content[cursor:cursor + 1] != b"e":
            cursor = _bencode_end(content, cursor, depth + 1)
        if cursor >= len(content):
            raise ValueError("torrent 容器未结束")
        return cursor + 1
    colon = content.index(b":", offset)
    length_text = content[offset:colon]
    if not length_text.isdigit():
        raise ValueError("torrent 字符串长度无效")
    end = colon + 1 + int(length_text)
    if end > len(content):
        raise ValueError("torrent 字符串已截断")
    return end


def _raw_info(content: bytes) -> bytes:
    """从顶层字典取得唯一 info 原始字节以准确计算目标 hash。"""
    if not content.startswith(b"d") or _bencode_end(content, 0) != len(content):
        raise ValueError("torrent 顶层编码无效")
    cursor = 1
    found = []
    while content[cursor:cursor + 1] != b"e":
        key_end = _bencode_end(content, cursor)
        key = bdecode(content[cursor:key_end], decode=0)
        value_end = _bencode_end(content, key_end)
        if key == b"info":
            found.append(content[key_end:value_end])
        cursor = value_end
    if len(found) != 1:
        raise ValueError("torrent 必须包含唯一 info 字典")
    return found[0]


def _path_component(value: bytes) -> str:
    """拒绝不能明确映射到本地文件的路径组件。"""
    if not isinstance(value, bytes):
        raise ValueError("torrent 文件路径格式无效")
    text = value.decode("utf-8")
    if not text or text in {".", ".."} or any(char in text for char in ("/", "\\", "\x00", ":")):
        raise ValueError("torrent 包含不安全的文件路径")
    return text


def torrent_metadata(content: bytes) -> dict:
    """解析整种指纹、真实 info hash 和按分片顺序排列的文件布局。"""
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_TORRENT_BYTES:
        raise ValueError("torrent 内容为空或超过大小限制")
    try:
        raw = _raw_info(content)
        info = bdecode(raw, decode=0)
        raw_pieces = info.get(b"pieces")
        piece_length = info.get(b"piece length")
        if not isinstance(raw_pieces, bytes) or not raw_pieces or len(raw_pieces) % 20:
            raise ValueError("种子缺少 v1 pieces，暂不支持纯 v2 种子")
        if type(piece_length) is not int or piece_length <= 0:
            raise ValueError("torrent 分片长度无效")
        name = _path_component(info.get(b"name.utf-8", info.get(b"name")))
        rows = info.get(b"files")
        files = []
        if rows is None:
            rows = [{b"path": [name.encode()], b"length": info.get(b"length")}]
            prefix = []
        else:
            prefix = [name]
        if not isinstance(rows, list) or not rows:
            raise ValueError("torrent 文件列表为空")
        for row in rows:
            components = row.get(b"path.utf-8", row.get(b"path"))
            length = row.get(b"length")
            if not isinstance(components, list) or not components or type(length) is not int or length < 0:
                raise ValueError("torrent 文件布局无效")
            path = str(PurePosixPath(*(prefix + [_path_component(part) for part in components])))
            files.append([path, length])
        if len({row[0] for row in files}) != len(files):
            raise ValueError("torrent 包含重复文件路径")
        total = sum(row[1] for row in files)
        if total <= 0 or (total + piece_length - 1) // piece_length != len(raw_pieces) // 20:
            raise ValueError("torrent 分片数量与文件总长度不符")
        return {"hash": hashlib.sha1(raw).hexdigest(), "pieces_hash": hashlib.sha1(raw_pieces).hexdigest(),
                "piece_length": piece_length, "total": total, "files": files}
    except (KeyError, TypeError, UnicodeError, IndexError, AttributeError) as error:
        raise ValueError("torrent 元数据或路径无法解析") from error


def verify_target(source: dict, target: dict) -> None:
    """要求目标与来源分片及完整文件路径逐项一致。"""
    if any(source[key] != target[key] for key in ("pieces_hash", "piece_length", "total", "files")):
        raise ValueError("目标分片、大小或文件布局与来源不一致")


def retry_after_seconds(headers: dict, default: int = 300) -> int:
    """解析限流响应头，兼容秒数、HTTP 日期和重置时间戳。"""
    raw = str(headers.get("Retry-After") or "").strip()
    try:
        if raw.isdecimal():
            return max(1, int(raw))
        if raw:
            return max(1, int((parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()))
        reset = float(headers.get("X-RateLimit-Reset") or 0)
        if reset > time.time():
            return max(1, int(reset - time.time()))
    except (ValueError, TypeError, OverflowError):
        pass
    return default


def query_site(site: dict, fingerprints: list[str]) -> tuple[dict, int, str]:
    """请求通用 Pieces 接口，区分空命中、鉴权错误和限流。"""
    try:
        response = request_pieces_res(site, fingerprints)
    except Exception:
        return {}, 60, "接口请求失败"
    if response is None:
        return {}, 60, "接口未响应"
    if response.status_code == 429:
        return {}, retry_after_seconds(response.headers), "站点限流，等待冷却"
    if response.status_code in (401, 403):
        return {}, 1800, "站点拒绝认证，请检查凭据与接口权限"
    if response.status_code != 200:
        return {}, 300, f"接口返回 HTTP {response.status_code}"
    try:
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("success") is False or payload.get("code", 0) not in (0, 200, "0", "200"):
            raise ValueError("站点返回业务错误")
        return_code = payload.get("ret", 0)
        if isinstance(return_code, bool) or return_code not in (0, "0"):
            return {}, 300, "站点接口返回业务错误"
        matches = payload.get("data")
        if not isinstance(matches, dict):
            raise ValueError("站点响应格式不符合约定")
        result = {}
        if is_flux_site(site):
            candidates = matches.get("results")
            if not isinstance(candidates, list):
                raise ValueError("站点响应缺少候选列表")
            for candidate in candidates:
                if (not isinstance(candidate, dict) or candidate.get("query") not in fingerprints
                        or candidate.get("match") != "pieces_sha1"):
                    raise ValueError("站点返回了无效匹配指纹")
                identity = str(candidate.get("torrent_id"))
                if not re.fullmatch(r"[1-9][0-9]*", identity):
                    raise ValueError("站点返回了无效匹配结果")
                identities = result.setdefault(candidate["query"], [])
                if identity not in identities:
                    identities.append(identity)
            return result, 0, ""
        for fingerprint, torrent_id in matches.items():
            identity = str(torrent_id)
            if fingerprint not in fingerprints or not re.fullmatch(r"[1-9][0-9]*", identity):
                raise ValueError("站点返回了无效匹配结果")
            result[fingerprint] = identity
        return result, 0, ""
    except Exception:
        return {}, 300, "接口响应格式不符合约定"


def pieces_hash_from_torrent(content: bytes) -> str:
    """从原始 torrent bencode 的 v1 pieces 字段生成 SHA-1 指纹。"""
    if not isinstance(content, bytes):
        raise TypeError("torrent 元数据必须是二进制内容")
    if not content:
        raise ValueError("torrent 元数据为空")
    try:
        metadata = bdecode(content)
    except Exception as error:
        raise ValueError("torrent 元数据无法解码") from error
    if not isinstance(metadata, dict):
        raise TypeError("torrent 元数据根节点不是字典")
    info = metadata.get(b"info", metadata.get("info"))
    if not isinstance(info, dict):
        raise TypeError("torrent info 节点不是字典")
    pieces = info.get(b"pieces", info.get("pieces"))
    if isinstance(pieces, str):
        pieces = pieces.encode("utf-8")
    if not isinstance(pieces, bytes) or not pieces or len(pieces) % 20:
        raise ValueError("torrent 缺少有效的 v1 pieces 字段")
    return hashlib.sha1(pieces).hexdigest()
