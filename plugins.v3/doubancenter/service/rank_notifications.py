"""榜单观察通知及其宿主通知分类。"""

import datetime
import secrets
import time

from app.schemas.types import MessageType, NotificationChannel
from app.sdk.logging import logger

from ..adapter import notification as notification_adapter
from ..model.identity import identity_payload
from ..storage import records as storage
from . import lifecycle

NOTICE_TTL = 7 * 86400


def notification_type_options() -> list[dict[str, str]]:
    """仅展示当前宿主实际支持的通知分类。"""
    return [{"title": item.value, "value": item.name} for item in MessageType]


def normalize_notification_type(value) -> str:
    """旧配置和无效分类安全回退到插件通知。"""
    name = str(value or "Plugin").strip()
    return name if name in MessageType.__members__ else "Plugin"


def resolve_notification_type(plugin):
    """把已保存的分类名转成宿主枚举。"""
    return MessageType[normalize_notification_type(getattr(plugin, "_notification_type", "Plugin"))]


def started(plugin, item: dict) -> None:
    """只由真实入观察迁移调用；不能把升级存量当成待发消息。"""
    if getattr(plugin, "_notify", False):
        item["observation_notice"] = {
            "cycle": secrets.token_hex(12), "state": "pending", "created_at": time.time(), "attempted": [],
        }


def enrich_observation(history, unique, rank, raw, mediainfo, meta, *, year, air_date, media_type):
    """保留本轮已识别的身份与季号，消息动作不再按标题猜对象。"""
    for item in history:
        if item.get("unique") != unique or not item.get("observing") or item.get("observe_deleted"):
            continue
        item.update(identity_payload(mediainfo))
        item.update({
            "year": year, "air_date": air_date, "media_type": media_type,
            "rank_key": rank["key"], "rank_name": rank.get("name") or rank["key"],
            "season": getattr(meta, "begin_season", None),
        })
        if raw.get("link"):
            item["link"] = raw["link"]
        for key in ("bangumiid", "bangumi_id", "doubanid", "douban_id"):
            if raw.get(key) not in (None, ""):
                item[key] = raw[key]
        return


def is_observing(item: dict) -> bool:
    """只允许当前仍在观察的条目产生消息或动作。"""
    return bool(item.get("observing") and not any(item.get(key) for key in (
        "observe_deleted", "observe_dropped_at", "observe_dropped_reason", "subscribed", "subscribed_at", "existing",
    )))


def message_text(item: dict, rank: dict, days: int) -> str:
    """通知明确指出尚未订阅，并展示观察期限。"""
    title = str(item.get("title") or "未命名条目")[:160]
    season = item.get("season")
    season_text = f" · 第 {season} 季" if season is not None else ""
    try:
        start = datetime.datetime.strptime(item["first_seen"], "%Y-%m-%d %H:%M:%S")
        deadline = (start + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    except (KeyError, TypeError, ValueError):
        deadline = "以观察区显示为准"
    return (
        f"{title}{season_text}\n榜单：{str(rank.get('name') or rank['key'])[:100]}\n"
        f"观察期：{days} 天，预计到期 {deadline}\n"
        "当前尚未订阅。可立即订阅，或移除以忽略该榜单条目；也可打开插件观察区处理。"
    )


@lifecycle.rank_locked
def send_pending(plugin, rank: dict) -> None:
    """观察已落盘后才尝试发送；一次周期/渠道至多认领一次，不冒充送达回执。"""
    if not getattr(plugin, "_notify", False):
        return
    try:
        _send_pending(plugin, rank)
    except lifecycle.RunStopped:
        raise
    except Exception as error:
        logger.warning(f"豆瓣中心：观察通知未完成（{type(error).__name__}），不影响榜单处理")


def _send_pending(plugin, rank: dict) -> None:
    from . import observation_actions

    history = storage.read_rank_history(plugin, rank["key"])
    pending = [item for item in history if isinstance(item, dict) and is_observing(item)
               and (item.get("observation_notice") or {}).get("state") == "pending"]
    if not pending:
        return
    mtype = resolve_notification_type(plugin)
    routes = notification_adapter.destinations(mtype)
    try:
        actor = notification_adapter.telegram_userid() if any(route["type"] == "telegram" for route in routes) else ""
    except Exception:
        actor = ""
    link = notification_adapter.detail_link(plugin)
    for item in pending:
        notice = item["observation_notice"]
        if time.time() - float(notice.get("created_at") or 0) >= NOTICE_TTL:
            notice["state"] = "expired"
            storage.save_rank_history(plugin, rank["key"], history)
            continue
        failed = False
        for route in routes:
            route_key = f"{route['id']}:{route['name']}"
            if route_key in notice["attempted"]:
                continue
            payload = {
                "source": route["name"], "mtype": mtype, "title": "豆瓣中心 · 进入观察区",
                "text": message_text(item, rank, int(getattr(plugin, "_observe_days", 0))),
                "link": link, "parse_mode": "plain",
            }
            if route["type"] == "telegram" and actor and route["id"]:
                buttons = observation_actions.prepare_buttons(plugin, item, route, actor)
                if buttons:
                    payload.update(channel=NotificationChannel.Telegram, userid=actor,
                                   targets={"telegram_userid": actor}, buttons=buttons)
            # 先认领再投递，进程中断或通道回执不明时不自动重复群发。
            notice["attempted"].append(route_key)
            storage.save_rank_history(plugin, rank["key"], history)
            lifecycle.checkpoint(plugin)
            try:
                plugin.post_message(**payload)
            except Exception as error:
                failed = True
                logger.warning(f"豆瓣中心：观察通知提交失败（{type(error).__name__}），请检查通知渠道")
        notice["state"] = "failed" if failed else ("submitted" if routes else "unconfigured")
        storage.save_rank_history(plugin, rank["key"], history)
