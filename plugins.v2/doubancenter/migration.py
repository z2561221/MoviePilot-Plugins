"""
DoubanCenter - 历史数据迁移工具
"""
from importlib import import_module
from typing import Any, Iterable, Optional

try:
    from app.log import logger
except Exception:
    logger = None


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
