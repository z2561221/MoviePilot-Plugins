"""
DoubanCenter - 历史数据迁移工具
"""
import re
from importlib import import_module
from typing import Any, Iterable, Optional
from urllib.parse import urlsplit

try:
    from app.sdk.logging import logger
except Exception:
    logger = None

from .model.identity import identity_payload, normalize_record
from .service.observation_metadata import enrich_log_metadata
from .storage import records as storage

TARGET_SUBSCRIBE_USERNAME = "豆瓣中心"
LEGACY_SUBSCRIBE_USERNAMES = {
    "豆瓣榜单",
    "豆瓣中心-即映",
    "豆瓣中心-仪表盘",
}
IDENTITY_HINT_FIELDS = {
    "media_source",
    "media_id",
    "tmdb_id",
    "tmdbid",
    "douban_id",
    "doubanid",
    "bangumi_id",
    "bangumiid",
}


def normalize_subscribe_username(username: Any) -> str:
    """归一化豆瓣中心历史订阅用户名。"""
    value = str(username or "")
    if value in LEGACY_SUBSCRIBE_USERNAMES:
        return TARGET_SUBSCRIBE_USERNAME
    return value


def _log_warning(message: str) -> None:
    """写入兼容测试环境的警告日志。"""
    if logger and hasattr(logger, "warning"):
        logger.warning(message)


def _log_info(message: str) -> None:
    """写入兼容测试环境的信息日志。"""
    if logger and hasattr(logger, "info"):
        logger.info(message)


def _record_id(record: Any) -> Optional[Any]:
    """读取订阅记录主键。"""
    if isinstance(record, dict):
        return record.get("id")
    return getattr(record, "id", None)


def _record_username(record: Any) -> str:
    """读取订阅记录用户名。"""
    if isinstance(record, dict):
        return str(record.get("username") or "")
    return str(getattr(record, "username", "") or "")


def _list_records(oper: Any) -> Iterable[Any]:
    """读取操作类记录列表，兼容需要 state 参数的订阅查询。"""
    if not oper or not hasattr(oper, "list"):
        return []
    try:
        return oper.list() or []
    except TypeError:
        try:
            return oper.list(state="N,R,S,P") or []
        except TypeError:
            return []


def normalize_operation_records(oper: Any) -> int:
    """将一个 MP 数据操作类中的豆瓣中心旧订阅用户名归一。"""
    if not oper or not hasattr(oper, "update"):
        return 0
    changed = 0
    for record in _list_records(oper):
        username = _record_username(record)
        normalized = normalize_subscribe_username(username)
        if normalized == username:
            continue
        record_id = _record_id(record)
        if record_id in (None, ""):
            continue
        try:
            oper.update(record_id, {"username": normalized})
            changed += 1
        except Exception as err:
            _log_warning(f"豆瓣中心：订阅者归一失败，记录 {record_id}：{err}")
    return changed


def _normalize_oper(module_name: str, class_name: str, required: bool = False) -> int:
    """按模块名加载 MP 数据操作类并执行订阅者归一。"""
    try:
        module = import_module(module_name)
        oper_cls = getattr(module, class_name)
    except Exception as err:
        if required:
            _log_warning(f"豆瓣中心：订阅者归一操作类加载失败：{err}")
        return 0
    try:
        return normalize_operation_records(oper_cls())
    except Exception as err:
        _log_warning(f"豆瓣中心：订阅者归一执行失败：{err}")
        return 0


def normalize_legacy_subscribe_usernames() -> int:
    """归一化订阅表和订阅历史表中的豆瓣中心旧订阅者名。"""
    changed = 0
    changed += _normalize_oper("app.db.oper.subscribe", "SubscribeOper", required=True)
    changed += _normalize_oper("app.db.oper.subscribehistory", "SubscribeHistoryOper")
    if changed:
        _log_info(f"豆瓣中心：已归一历史订阅者 {changed} 条为「{TARGET_SUBSCRIBE_USERNAME}」")
    return changed


def _read_plugin_data(plugin: Any, key: str) -> Any:
    """读取插件存储中的原始数据。"""
    try:
        return plugin.get_data(key)
    except Exception as err:
        _log_warning(f"豆瓣中心：读取迁移数据 {key} 失败：{err}")
        return None


def _save_plugin_data(plugin: Any, key: str, value: Any) -> bool:
    """保存迁移后的插件数据。"""
    try:
        plugin.save_data(key, value)
        return True
    except Exception as err:
        _log_warning(f"豆瓣中心：保存迁移数据 {key} 失败：{err}")
        return False


def _has_identity_hint(record: Any) -> bool:
    """判断记录是否声明过需要迁移的媒体身份字段。"""
    if not isinstance(record, dict):
        return False
    return any(record.get(field) not in (None, "") for field in IDENTITY_HINT_FIELDS)


def _identity_from_record_link(record: dict) -> dict:
    """仅从可信来源的条目链接补齐完全缺失的身份，不覆盖半截身份。"""
    if _has_identity_hint(record):
        return record
    try:
        parsed = urlsplit(str(record.get("link") or ""))
    except ValueError:
        return record
    if parsed.scheme not in {"http", "https"}:
        return record
    if parsed.hostname in {"douban.com", "www.douban.com", "movie.douban.com"}:
        source = "douban"
        pattern = r"/(?:subject|doubanapp/dispatch/movie)/([1-9]\d*)/?"
    elif parsed.hostname in {"bgm.tv", "bangumi.tv", "chii.in"}:
        source = "bangumi"
        pattern = r"/subject/([1-9]\d*)/?"
    else:
        return record
    match = re.fullmatch(pattern, parsed.path)
    if not match:
        return record
    return identity_payload(record, media_source=source, media_id=match.group(1))


def _is_pending_folio_identity(record: Any) -> bool:
    """已知播放来源但尚未核实豆瓣分季的队列项无需迁移目标身份。"""
    if not isinstance(record, dict) or record.get("identity_status") != "unresolved":
        return False
    if _has_identity_hint(record) or record.get("subject_id") not in (None, "", "0"):
        return False
    origin = record.get("origin")
    if not isinstance(origin, dict) or not origin.get("media_source") or not origin.get("media_id"):
        return False
    _, _, unresolved = normalize_record(origin)
    return not unresolved


def _migrate_record(
    record: Any,
    *,
    subject_id_as_douban: bool = False,
    identity_optional: bool = False,
) -> tuple[Any, bool, bool]:
    """迁移一条记录并返回新记录、是否变化及是否 unresolved。"""
    if not isinstance(record, dict):
        return record, False, False
    migrated, changed, unresolved = normalize_record(record)
    if unresolved:
        migrated = _identity_from_record_link(migrated)
        migrated, _, unresolved = normalize_record(migrated)
        changed = migrated != record
    if unresolved and subject_id_as_douban:
        subject_id = migrated.get("subject_id")
        if subject_id not in (None, "", "0"):
            subject_identity = identity_payload(
                migrated,
                media_source="douban",
                media_id=subject_id,
            )
            if subject_identity.get("media_source") and subject_identity.get("media_id"):
                migrated = subject_identity
                changed = migrated != record
                unresolved = False
    if unresolved and identity_optional and not _has_identity_hint(record):
        unresolved = False
    return migrated, changed, unresolved


def _migrate_list(
    records: Any,
    *,
    subject_id_as_douban: bool = False,
    identity_optional: bool = False,
) -> tuple[list, bool, int]:
    """迁移列表记录并统计 unresolved 条目。"""
    if not isinstance(records, list):
        return records if isinstance(records, list) else [], False, 0
    migrated_records = []
    changed = False
    unresolved_count = 0
    for record in records:
        migrated, item_changed, unresolved = _migrate_record(
            record,
            subject_id_as_douban=subject_id_as_douban,
            identity_optional=identity_optional,
        )
        migrated_records.append(migrated)
        changed = changed or item_changed
        unresolved_count += int(unresolved)
    return migrated_records, changed, unresolved_count


def _migrate_dict_records(
    data: Any,
    *,
    subject_id_as_douban: bool = False,
    pending_origin_allowed: bool = False,
) -> tuple[dict, bool, int]:
    """迁移以标题或 subject id 为键的字典记录。"""
    if not isinstance(data, dict):
        return {}, False, 0
    migrated_data = {}
    changed = False
    unresolved_count = 0
    for key, value in data.items():
        if pending_origin_allowed and _is_pending_folio_identity(value):
            migrated_data[key] = dict(value)
            continue
        migrated, item_changed, unresolved = _migrate_record(
            value,
            subject_id_as_douban=subject_id_as_douban,
        )
        migrated_data[key] = migrated
        changed = changed or item_changed
        unresolved_count += int(unresolved)
    return migrated_data, changed, unresolved_count


def _migrate_archive_list(records: Any) -> tuple[list, bool, int]:
    """迁移归档外层与嵌套原始记录的媒体身份。"""
    if not isinstance(records, list):
        return [], False, 0
    migrated_records = []
    changed = False
    unresolved_count = 0
    for archive in records:
        if not isinstance(archive, dict):
            migrated_records.append(archive)
            continue
        copied = dict(archive)
        identity_optional = archive.get("source") == "anti_cheat_log"
        nested, nested_changed, nested_unresolved = _migrate_record(
            archive.get("record") or {},
            identity_optional=identity_optional,
        )
        if isinstance(nested, dict):
            copied["record"] = nested
            source = nested.get("media_source")
            media_id = nested.get("media_id")
            if source and media_id:
                if copied.get("media_source") != source or str(copied.get("media_id") or "") != str(media_id):
                    copied["media_source"] = source
                    copied["media_id"] = media_id
                    nested_changed = True
        migrated, outer_changed, outer_unresolved = _migrate_record(
            copied,
            identity_optional=identity_optional,
        )
        migrated_records.append(migrated)
        changed = changed or nested_changed or outer_changed
        unresolved_count += int(nested_unresolved or outer_unresolved)
    return migrated_records, changed, unresolved_count


def _migration_storage_keys(rank_keys, custom_rank_sources) -> tuple[list[str], set[str]]:
    """收集迁移范围及可用于补全观察日志的存储键。"""
    list_keys = [
        storage.SUBSCRIBE_RECORDS_KEY,
        storage.ANTI_CHEAT_LOGS_KEY,
        storage.FOLIO_WISH_SEEN_KEY,
        storage.FOLIO_WISH_QUEUE_KEY,
        storage.FOLIO_WISH_PROCESSED_KEY,
        storage.FOLIO_WISH_FAILED_KEY,
    ]
    seen_keys = set(list_keys)
    metadata_keys = {storage.SUBSCRIBE_RECORDS_KEY}
    for rank_key in rank_keys or ():
        key = storage.rank_history_key(str(rank_key))
        metadata_keys.add(key)
        if key not in seen_keys:
            list_keys.append(key)
            seen_keys.add(key)
    for source in custom_rank_sources or ():
        key = storage.custom_rank_history_key(str(source))
        metadata_keys.add(key)
        if key not in seen_keys:
            list_keys.append(key)
            seen_keys.add(key)
    return list_keys, metadata_keys


def _migrate_history_storage(plugin: Any, list_keys: list[str], metadata_keys: set[str]) -> dict:
    """迁移列表存储并复用迁移结果补全日志，避免反复读取榜单。"""
    result = {"changed_keys": [], "unresolved_count": 0, "migrated_count": 0,
              "pending_folio_count": 0}
    metadata_sources = []
    for key in list_keys:
        raw = _read_plugin_data(plugin, key)
        migrated, changed, unresolved = _migrate_list(
            raw,
            subject_id_as_douban=key in {
                storage.FOLIO_WISH_SEEN_KEY, storage.FOLIO_WISH_QUEUE_KEY,
                storage.FOLIO_WISH_PROCESSED_KEY, storage.FOLIO_WISH_FAILED_KEY,
            },
            identity_optional=key == storage.ANTI_CHEAT_LOGS_KEY,
        )
        if changed and _save_plugin_data(plugin, key, migrated):
            result["changed_keys"].append(key)
        if key in metadata_keys:
            metadata_sources.extend(migrated)
        if isinstance(raw, list):
            result["migrated_count"] += sum(before != after for before, after in zip(raw, migrated))
        result["unresolved_count"] += unresolved

    raw_logs = _read_plugin_data(plugin, storage.ANTI_CHEAT_LOGS_KEY)
    if isinstance(raw_logs, list):
        enriched_logs, logs_changed = enrich_log_metadata(raw_logs, metadata_sources)
        if logs_changed and _save_plugin_data(plugin, storage.ANTI_CHEAT_LOGS_KEY, enriched_logs):
            result["changed_keys"].append(storage.ANTI_CHEAT_LOGS_KEY)
    return result


def _migrate_remaining_storage(plugin: Any, result: dict) -> None:
    """迁移归档与观影存储，将待分季状态和真实迁移缺失分别累计。"""
    raw = _read_plugin_data(plugin, storage.ARCHIVE_RECORDS_KEY)
    migrated, changed, unresolved = _migrate_archive_list(raw)
    if changed and _save_plugin_data(plugin, storage.ARCHIVE_RECORDS_KEY, migrated):
        result["changed_keys"].append(storage.ARCHIVE_RECORDS_KEY)
    result["unresolved_count"] += unresolved

    for key in (storage.FOLIO_DATA_KEY, storage.FOLIO_WAIT_KEY):
        raw = _read_plugin_data(plugin, key)
        pending_origin_allowed = key == storage.FOLIO_WAIT_KEY
        if pending_origin_allowed and isinstance(raw, dict):
            result["pending_folio_count"] = sum(
                _is_pending_folio_identity(record) for record in raw.values()
            )
        migrated, changed, unresolved = _migrate_dict_records(
            raw,
            subject_id_as_douban=True,
            pending_origin_allowed=pending_origin_allowed,
        )
        if changed and _save_plugin_data(plugin, key, migrated):
            result["changed_keys"].append(key)
        result["unresolved_count"] += unresolved


def migrate_plugin_media_identity(
    plugin: Any,
    *,
    rank_keys: Optional[Iterable[str]] = None,
    custom_rank_sources: Optional[Iterable[str]] = None,
) -> dict:
    """幂等迁移豆瓣中心各类存量记录到 V3 媒体身份对。"""
    list_keys, metadata_keys = _migration_storage_keys(rank_keys, custom_rank_sources)
    result = _migrate_history_storage(plugin, list_keys, metadata_keys)
    _migrate_remaining_storage(plugin, result)
    result["changed_keys"] = list(dict.fromkeys(result["changed_keys"]))
    if result["changed_keys"]:
        _log_info(f"豆瓣中心：V3 身份迁移完成，更新 {len(result['changed_keys'])} 个存储键")
    if result["unresolved_count"]:
        _log_warning(f"豆瓣中心：V3 身份迁移保留 {result['unresolved_count']} 条无法回填的历史记录")
    if result["pending_folio_count"]:
        _log_info(f"豆瓣中心：{result['pending_folio_count']} 条观影记录待豆瓣分季匹配，已保留来源身份")
    return result
