"""
DoubanCenter - 历史数据迁移工具
"""
from importlib import import_module
from typing import Any, Iterable, Optional

try:
    from app.sdk.logging import logger
except Exception:
    logger = None

from .model.identity import identity_payload, normalize_record
from .storage import records as storage


TARGET_SUBSCRIBE_USERNAME = "豆瓣中心"
LEGACY_SUBSCRIBE_USERNAMES = {
    "豆瓣榜单",
    "豆瓣中心-即映",
    "豆瓣中心-仪表盘",
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
    changed += _normalize_oper("app.db.subscribe_oper", "SubscribeOper", required=True)
    changed += _normalize_oper("app.db.subscribehistory_oper", "SubscribeHistoryOper")
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


def _migrate_record(record: Any, *, subject_id_as_douban: bool = False) -> tuple[Any, bool, bool]:
    """迁移一条记录并返回新记录、是否变化及是否 unresolved。"""
    if not isinstance(record, dict):
        return record, False, False
    migrated, changed, unresolved = normalize_record(record)
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
    return migrated, changed, unresolved


def _migrate_list(records: Any, *, subject_id_as_douban: bool = False) -> tuple[list, bool, int]:
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
        )
        migrated_records.append(migrated)
        changed = changed or item_changed
        unresolved_count += int(unresolved)
    return migrated_records, changed, unresolved_count


def _migrate_dict_records(data: Any, *, subject_id_as_douban: bool = False) -> tuple[dict, bool, int]:
    """迁移以标题或 subject id 为键的字典记录。"""
    if not isinstance(data, dict):
        return {}, False, 0
    migrated_data = {}
    changed = False
    unresolved_count = 0
    for key, value in data.items():
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
        nested, nested_changed, nested_unresolved = _migrate_record(archive.get("record") or {})
        if isinstance(nested, dict):
            copied["record"] = nested
            source = nested.get("media_source")
            media_id = nested.get("media_id")
            if source and media_id:
                if copied.get("media_source") != source or str(copied.get("media_id") or "") != str(media_id):
                    copied["media_source"] = source
                    copied["media_id"] = media_id
                    nested_changed = True
        migrated, outer_changed, outer_unresolved = _migrate_record(copied)
        migrated_records.append(migrated)
        changed = changed or nested_changed or outer_changed
        unresolved_count += int(nested_unresolved or outer_unresolved)
    return migrated_records, changed, unresolved_count


def migrate_plugin_media_identity(
    plugin: Any,
    *,
    rank_keys: Optional[Iterable[str]] = None,
    custom_rank_sources: Optional[Iterable[str]] = None,
) -> dict:
    """幂等迁移豆瓣中心各类存量记录到 V3 媒体身份对。"""
    list_keys = [
        storage.SUBSCRIBE_RECORDS_KEY,
        storage.ANTI_CHEAT_LOGS_KEY,
        storage.FOLIO_WISH_SEEN_KEY,
        storage.FOLIO_WISH_QUEUE_KEY,
        storage.FOLIO_WISH_PROCESSED_KEY,
        storage.FOLIO_WISH_FAILED_KEY,
    ]
    seen_keys = set(list_keys)
    for rank_key in rank_keys or ():
        key = storage.rank_history_key(str(rank_key))
        if key not in seen_keys:
            list_keys.append(key)
            seen_keys.add(key)
    for source in custom_rank_sources or ():
        key = storage.custom_rank_history_key(str(source))
        if key not in seen_keys:
            list_keys.append(key)
            seen_keys.add(key)

    changed_keys = []
    unresolved_count = 0
    migrated_count = 0
    for key in list_keys:
        raw = _read_plugin_data(plugin, key)
        if key == storage.ARCHIVE_RECORDS_KEY:
            migrated, changed, unresolved = _migrate_archive_list(raw)
        else:
            migrated, changed, unresolved = _migrate_list(
                raw,
                subject_id_as_douban=key in {
                    storage.FOLIO_WISH_SEEN_KEY,
                    storage.FOLIO_WISH_QUEUE_KEY,
                    storage.FOLIO_WISH_PROCESSED_KEY,
                    storage.FOLIO_WISH_FAILED_KEY,
                },
            )
        if changed and _save_plugin_data(plugin, key, migrated):
            changed_keys.append(key)
        migrated_count += sum(1 for before, after in zip(raw or [], migrated or []) if before != after) if isinstance(raw, list) else 0
        unresolved_count += unresolved

    raw_archive = _read_plugin_data(plugin, storage.ARCHIVE_RECORDS_KEY)
    migrated_archive, archive_changed, archive_unresolved = _migrate_archive_list(raw_archive)
    if archive_changed and _save_plugin_data(plugin, storage.ARCHIVE_RECORDS_KEY, migrated_archive):
        changed_keys.append(storage.ARCHIVE_RECORDS_KEY)
    unresolved_count += archive_unresolved

    for key in (storage.FOLIO_DATA_KEY, storage.FOLIO_WAIT_KEY):
        raw = _read_plugin_data(plugin, key)
        migrated, changed, unresolved = _migrate_dict_records(raw, subject_id_as_douban=True)
        if changed and _save_plugin_data(plugin, key, migrated):
            changed_keys.append(key)
        unresolved_count += unresolved

    result = {
        "changed_keys": list(dict.fromkeys(changed_keys)),
        "migrated_count": migrated_count,
        "unresolved_count": unresolved_count,
    }
    if result["changed_keys"]:
        _log_info(f"豆瓣中心：V3 身份迁移完成，更新 {len(result['changed_keys'])} 个存储键")
    if unresolved_count:
        _log_warning(f"豆瓣中心：V3 身份迁移保留 {unresolved_count} 条无法回填的历史记录")
    return result
