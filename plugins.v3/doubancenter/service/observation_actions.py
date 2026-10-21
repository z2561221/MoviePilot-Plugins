"""观察通知的短期、绑定用户和实例的 Telegram 操作。"""

import copy
import re
import secrets
import time

from app.schemas.types import NotificationChannel
from app.sdk.logging import logger

from ..adapter import notification as notification_adapter
from ..storage import records as storage
from . import lifecycle, rank_notifications

SESSIONS_KEY = "observation_action_sessions"
MAX_SESSIONS = 2048
CALLBACK = re.compile(r"^dco:([A-Za-z0-9_-]{16}):([sr])$")


def fingerprint(item: dict) -> list[str]:
    """标题可被补正，动作必须绑定不变的观察周期、媒体身份和季号。"""
    keys = ("rank_key", "unique", "first_seen", "media_source", "media_id", "media_type", "season", "year")
    return [str(item.get(key) if item.get(key) is not None else "") for key in keys] + [
        str((item.get("observation_notice") or {}).get("cycle") or ""),
    ]


def _buttons(plugin, token: str) -> list[list[dict]]:
    buttons = [{"text": text, "callback_data": f"[PLUGIN]{plugin.__class__.__name__}|dco:{token}:{action}"}
               for text, action in (("立即订阅", "s"), ("移除观察", "r"))]
    return [buttons] if all(len(button["callback_data"].encode("utf-8")) <= 64 for button in buttons) else []


def prepare_buttons(plugin, item: dict, route: dict, actor: str) -> list[list[dict]]:
    """先保存不可猜测的引用；回调不接受任何客户端传来的媒体参数。"""
    if not item.get("media_source") or not item.get("media_id") or item.get("media_type") not in ("tv", "movie"):
        return []
    token = secrets.token_urlsafe(12)
    buttons = _buttons(plugin, token)
    if not buttons:
        return []
    now = time.time()
    sessions = copy.deepcopy(storage.read_dict(plugin, SESSIONS_KEY))
    sessions = {key: value for key, value in sessions.items()
                if isinstance(value, dict) and float(value.get("expires_at") or 0) > now}
    while len(sessions) >= MAX_SESSIONS:
        sessions.pop(next(iter(sessions)))
    sessions[token] = {
        "instance": plugin.__class__.__name__, "userid": actor, "source": route["name"], "source_id": route["id"],
        "rank_key": item["rank_key"], "unique": item["unique"], "fingerprint": fingerprint(item),
        "expires_at": now + rank_notifications.NOTICE_TTL, "state": "open",
    }
    storage.write_dict(plugin, SESSIONS_KEY, sessions)
    return buttons


def _reply(plugin, data: dict, text: str, *, token: str = "", edit: bool = True) -> None:
    """普通纯文本回执；业务成功与消息编辑成功分开，不重新生成操作令牌。"""
    payload = {
        "channel": NotificationChannel.Telegram, "source": data["source"], "userid": str(data["userid"]),
        "targets": {"telegram_userid": str(data["userid"])}, "mtype": rank_notifications.resolve_notification_type(plugin),
        "title": "豆瓣中心 · 观察操作", "text": text, "parse_mode": "plain",
        "buttons": _buttons(plugin, token) if token else None,
    }
    try:
        lifecycle.checkpoint(plugin)
        if edit:
            chain = getattr(plugin, "chain", None)
            edit_message = getattr(chain, "run_module", None)
            if callable(edit_message):
                try:
                    edited = edit_message(
                        "edit_message", channel=NotificationChannel.Telegram, source=data["source"],
                        message_id=data["original_message_id"], chat_id=data["original_chat_id"],
                        title=payload["title"], text=text, parse_mode="plain", buttons=payload["buttons"],
                    )
                    if edited is True:
                        return
                except Exception:
                    logger.warning("豆瓣中心：原观察卡片编辑失败，改为无按钮回执")
            lifecycle.checkpoint(plugin)
        # 编辑失败也不再创建一张可操作卡，防止同一令牌出现多个入口。
        payload["buttons"] = None
        plugin.post_message(**payload)
    except lifecycle.RunStopped:
        raise
    except Exception as error:
        logger.warning(f"豆瓣中心：观察操作回执提交失败（{type(error).__name__}），请以观察区状态为准")


def _current_item(plugin, session: dict):
    history = storage.read_rank_history(plugin, session["rank_key"])
    return history, next((item for item in history if isinstance(item, dict)
                          and item.get("unique") == session["unique"]), None)


def _settle_subscription(plugin, session: dict, status: str) -> None:
    """订阅结果按精确条目收束，不借用删除观察或标题匹配逻辑。"""
    history, item = _current_item(plugin, session)
    if item is None or fingerprint(item) != session["fingerprint"]:
        raise RuntimeError("Observation changed while subscribing")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    item["observing"] = False
    if status == "existing":
        item.update(existing=True, existing_at=now, existing_reason="subscribe")
    else:
        item.update(subscribed=True, subscribed_at=now)
    storage.save_rank_history(plugin, session["rank_key"], history)
    logs = storage.read_anti_cheat_logs(plugin)
    kept = [entry for entry in logs if not (isinstance(entry, dict)
            and entry.get("unique") == item["unique"] and entry.get("rank_key") == session["rank_key"]
            and entry.get("reason") in ("开始观察", "继续观察"))]
    if kept != logs:
        storage.save_anti_cheat_logs(plugin, kept)


def _execute(plugin, session: dict, item: dict, action: str) -> dict:
    from . import dashboard

    if action == "r":
        return dashboard.api_delete_observation(plugin, unique=item["unique"], rank_key=session["rank_key"])
    result = dashboard.api_subscribe_from_rank(
        plugin, tmdb_id=item.get("tmdbid") or item.get("tmdb_id"), media_type=item["media_type"],
        title=item.get("title") or "", year=item.get("year"),
        media_source=item.get("media_source"), media_id=item.get("media_id"),
        bangumi_id=item.get("bangumiid") or item.get("bangumi_id"), season=item.get("season"),
        rank_key=session["rank_key"], rank_name=item.get("rank_name") or session["rank_key"],
        source_link=item.get("link") or "", with_result=True,
    )
    status = result.get("status")
    if status in ("success", "existing"):
        _settle_subscription(plugin, session, status)
        return {"success": True, "message": "已确认订阅，观察条目已收束" if status == "success" else "订阅已存在，观察条目已收束"}
    return {"success": False, "message": result.get("message") or "订阅未成功，仍保留在观察区"}


def _handle_locked(plugin, data: dict, token: str, action: str) -> bool:
    from . import observation

    sessions = copy.deepcopy(storage.read_dict(plugin, SESSIONS_KEY))
    session = sessions.get(token)
    if not isinstance(session, dict) or session.get("instance") != plugin.__class__.__name__:
        return False
    if str(data.get("userid") or "") != session.get("userid") or data.get("source") != session.get("source"):
        return False
    if notification_adapter.telegram_userid() != session["userid"]:
        return False
    routes = notification_adapter.destinations(rank_notifications.resolve_notification_type(plugin))
    if not any(route["id"] == session.get("source_id") and route["name"] == session["source"]
               and route["type"] == "telegram" for route in routes):
        return False
    if float(session.get("expires_at") or 0) <= time.time():
        _reply(plugin, data, "这条通知已过期，请打开插件观察区处理。")
        return True
    if session.get("state") != "open":
        _reply(plugin, data, session.get("result") or "该操作已受理或结果待核验，不会重复提交；请查看观察区。")
        return True
    history, item = _current_item(plugin, session)
    del history
    if (not getattr(plugin, "_enabled", False) or not getattr(plugin, "_notify", False)
            or not observation.rank_observe_enabled(plugin, session["rank_key"])
            or item is None or not rank_notifications.is_observing(item)
            or fingerprint(item) != session["fingerprint"]):
        _reply(plugin, data, "观察状态或配置已变化，这条旧通知不会执行操作。")
        return True
    # 先认领动作。异常可能发生在宿主写入之后，未知结果不能自动恢复成可重试。
    session["state"] = "processing"
    storage.write_dict(plugin, SESSIONS_KEY, sessions)
    try:
        result = _execute(plugin, session, item, action)
        lifecycle.checkpoint(plugin)
        success = result.get("success") is True
        session["state"] = "done" if success else "open"
        session["result"] = str(result.get("message") or "操作未完成")
    except lifecycle.RunStopped:
        raise
    except Exception as error:
        session.update(state="uncertain", result="处理结果未确认，请在 MoviePilot 检查后再操作，不会自动重复提交。")
        logger.warning(f"豆瓣中心：观察操作结果未确认（{type(error).__name__}）")
    storage.write_dict(plugin, SESSIONS_KEY, sessions)
    _reply(plugin, data, session["result"], token=token if session["state"] == "open" else "")
    return True


@lifecycle.managed
def handle_callback(plugin, event) -> bool:
    """MessageAction 是广播事件，必须先过滤实例和真实 Telegram 回调。"""
    data = getattr(event, "event_data", None)
    if not isinstance(data, dict) or data.get("plugin_id") != plugin.__class__.__name__:
        return False
    channel = data.get("channel")
    if getattr(channel, "value", channel) != NotificationChannel.Telegram.value:
        return False
    match = CALLBACK.fullmatch(str(data.get("text") or ""))
    if not match or not data.get("source") or not data.get("userid"):
        return False
    if not re.fullmatch(r"[1-9][0-9]*", str(data.get("original_message_id") or "")):
        return False
    if not re.fullmatch(r"-?[1-9][0-9]*", str(data.get("original_chat_id") or "")):
        return False
    lock = getattr(plugin, "_rank_lock", lifecycle._FALLBACK_RANK_LOCK)
    if not lock.acquire(blocking=False):
        # 不编辑原卡，保留按钮供刷新结束后再点；忙碌回执不透露观察内容。
        session = storage.read_dict(plugin, SESSIONS_KEY).get(match.group(1))
        if (not isinstance(session, dict) or session.get("instance") != plugin.__class__.__name__
                or str(data["userid"]) != session.get("userid") or data["source"] != session.get("source")):
            return False
        try:
            if notification_adapter.telegram_userid() != session["userid"]:
                return False
        except Exception:
            return False
        _reply(plugin, data, "榜单正在处理，请稍后再点原通知按钮。", edit=False)
        return True
    try:
        return _handle_locked(plugin, data, *match.groups())
    except lifecycle.RunStopped:
        raise
    except Exception as error:
        logger.warning(f"豆瓣中心：无法核验观察操作（{type(error).__name__}），未重试")
        return False
    finally:
        lock.release()
