"""AgentRank Telegram 旧宿主消息终态兼容适配器。"""

from contextlib import contextmanager
from functools import wraps
from threading import RLock
from typing import Any, Callable, Iterator, List, Optional, Tuple


_PATCH_LOCK = RLock()
_MISSING = object()
_BOT_METHOD_ERRORS = {
    "delete_message": "message to delete not found",
    "edit_message_text": "message to edit not found",
    "edit_message_caption": "message to edit not found",
    "edit_message_media": "message to edit not found",
}


def _telegram_bots(
    module_manager_factory: Optional[Callable[[], Any]] = None,
) -> List[Any]:
    """返回当前运行 Telegram 模块内去重后的 bot 实例。"""
    try:
        if module_manager_factory is None:
            from app.sdk.plugins import ModuleManager

            module_manager_factory = ModuleManager
        manager = module_manager_factory()
        module = manager.get_running_module("TelegramModule")
        get_instances = getattr(module, "get_instances", None)
        instances = get_instances() if callable(get_instances) else {}
    except Exception:
        return []

    bots: List[Any] = []
    visited = set()
    for client in dict(instances or {}).values():
        bot = getattr(client, "_bot", None)
        identity = id(bot)
        if bot is None or identity in visited:
            continue
        visited.add(identity)
        bots.append(bot)
    return bots


def _guarded_bot_method(
    original: Callable[..., Any], expected_error: str
) -> Callable[..., Any]:
    """包装 bot 方法，仅把指定的消息不存在错误转换为幂等成功。"""

    @wraps(original)
    def guarded(*args: Any, **kwargs: Any) -> Any:
        """执行原方法，并兼容 Telegram 已不存在的终态消息。"""
        try:
            return original(*args, **kwargs)
        except Exception as error:
            if expected_error in str(error).lower():
                return True
            raise

    return guarded


@contextmanager
def telegram_message_not_found_guard(
    module_manager_factory: Optional[Callable[[], Any]] = None,
) -> Iterator[None]:
    """在 AgentRank 消息终态调用期间兼容旧宿主的 Telegram 不存在错误。"""
    patches: List[Tuple[Any, str, Any, Any, Callable[..., Any]]] = []
    with _PATCH_LOCK:
        for bot in _telegram_bots(module_manager_factory):
            try:
                namespace = vars(bot)
            except TypeError:
                namespace = None
            for method_name, expected_error in _BOT_METHOD_ERRORS.items():
                original = getattr(bot, method_name, None)
                if not callable(original):
                    continue
                previous = (
                    namespace.get(method_name, _MISSING)
                    if namespace is not None
                    else original
                )
                guarded = _guarded_bot_method(original, expected_error)
                try:
                    setattr(bot, method_name, guarded)
                except Exception:
                    continue
                patches.append((bot, method_name, previous, original, guarded))
        try:
            yield
        finally:
            for bot, method_name, previous, original, guarded in reversed(patches):
                try:
                    if getattr(bot, method_name, None) is not guarded:
                        continue
                    if previous is _MISSING:
                        delattr(bot, method_name)
                    else:
                        setattr(bot, method_name, previous)
                except Exception:
                    try:
                        setattr(bot, method_name, original)
                    except Exception:
                        pass
