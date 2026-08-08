"""下载速度告警的 Telegram 关闭与二次删除动作。"""

from __future__ import annotations

import time
from typing import Any

from ..utils.torrent_adapter import delete_torrent_with_files
from .speed_notification import (
    build_speed_monitor_callback,
    original_message_kwargs,
    parse_speed_monitor_callback,
    resolve_notification_type,
    validate_speed_monitor_callback,
)


def _find_alert_by_token(runtime: Any, token: str) -> dict | None:
    """按短 token 查找当前持久化告警。"""
    for alert in runtime.alerts.values():
        if (
            isinstance(alert, dict)
            and str(alert.get("token") or "") == str(token or "")
        ):
            return alert
    return None


def _action_buttons(plugin_id: str, token: str, confirming: bool) -> list[list[dict]]:
    """按普通或二次确认状态生成 Telegram 按钮。"""
    if confirming:
        return [[
            {
                "text": "确认删除全部数据",
                "callback_data": build_speed_monitor_callback(
                    plugin_id, token, "confirm"
                ),
            },
            {
                "text": "取消",
                "callback_data": build_speed_monitor_callback(
                    plugin_id, token, "cancel"
                ),
            },
        ]]
    return [[
        {
            "text": "关闭",
            "callback_data": build_speed_monitor_callback(
                plugin_id, token, "close"
            ),
        },
        {
            "text": "删除种子及全部数据",
            "callback_data": build_speed_monitor_callback(
                plugin_id, token, "delete"
            ),
        },
    ]]


def _post_action_card(
    plugin: Any,
    event_data: dict,
    *,
    title: str,
    text: str,
    buttons: list[list[dict]] | None,
    telegram_userid: str,
    notification_type: Any = None,
) -> None:
    """通过原消息字段编辑 Telegram 卡片并保持目标用户不变。"""
    kwargs = {
        "mtype": resolve_notification_type(
            getattr(plugin, "_speed_monitor_notification_type", "Plugin"),
            notification_type,
        ),
        "title": title,
        "text": text,
        "buttons": buttons,
        "targets": {"telegram_userid": str(telegram_userid or "")},
        "save_history": False,
        **original_message_kwargs(event_data),
    }
    try:
        from app.schemas.types import MessageChannel

        kwargs["channel"] = MessageChannel.Telegram
    except Exception:
        pass
    plugin.post_message(**kwargs)


def _rejection_text(reason: str) -> str:
    """把回调拒绝原因转换为不泄露内部状态的用户文本。"""
    return {
        "unauthorized_user": "这不是发送给你的速度告警，无法操作。",
        "expired": "该速度告警操作已过期。",
        "token_mismatch": "该速度告警已失效。",
        "foreign_plugin": "该操作不属于当前插件。",
        "non_telegram": "该操作只能从 Telegram 发起。",
        "foreign_callback": "无法识别该速度告警操作。",
    }.get(reason, "该速度告警已失效或无法处理。")


def _mark_alert(
    alert: dict,
    *,
    status: str,
    action: str,
    now: float,
) -> None:
    """更新告警处置状态和时间。"""
    alert["status"] = status
    alert["last_action"] = action
    alert["updated_at"] = now
    if status not in {"notified", "confirming"}:
        alert["handled_at"] = now


def process_speed_message_action(
    plugin: Any,
    event_data: dict,
    *,
    now: float | None = None,
    notification_type: Any = None,
) -> bool:
    """校验并处理关闭、二次确认、取消或确认全量删除动作。"""
    from .speed_monitor import (
        SESSION_ACTIVE,
        _finish_session,
        ensure_speed_monitor_runtime,
        persist_speed_monitor_runtime,
    )

    observed_at = float(time.time() if now is None else now)
    parsed = parse_speed_monitor_callback((event_data or {}).get("text"))
    if not parsed:
        return False
    token, action = parsed
    runtime = ensure_speed_monitor_runtime(plugin)
    alert = _find_alert_by_token(runtime, token)
    if alert is None:
        _post_action_card(
            plugin,
            event_data,
            title="速度告警操作失败",
            text="该速度告警已失效或无法处理。",
            buttons=None,
            telegram_userid=str((event_data or {}).get("userid") or ""),
            notification_type=notification_type,
        )
        return True
    validation = validate_speed_monitor_callback(
        event_data,
        plugin_id=plugin.__class__.__name__,
        telegram_userid=str(alert.get("telegram_userid") or ""),
        token=str(alert.get("token") or ""),
        expires_at=float(alert.get("expires_at") or 0.0),
        now=observed_at,
    )
    if not validation.accepted:
        _post_action_card(
            plugin,
            event_data,
            title="速度告警操作失败",
            text=_rejection_text(validation.reason),
            buttons=None,
            telegram_userid=str((event_data or {}).get("userid") or ""),
            notification_type=notification_type,
        )
        return True

    session_key = f"{alert.get('downloader_id')}:{alert.get('torrent_hash')}"
    title = "下载速度异常"
    text = "该速度告警已处理。"
    buttons = None
    with runtime.session_lock(session_key):
        session = runtime.sessions.get(session_key)
        if session is None or session.status != SESSION_ACTIVE:
            text = "任务已经完成、删除或不再可操作。"
        elif action == "close":
            if alert.get("status") in {"notified", "confirming"}:
                _mark_alert(
                    alert,
                    status="closed",
                    action="close",
                    now=observed_at,
                )
            title = "下载速度告警已关闭"
            text = "仅关闭本次告警；下载任务保持不变。"
        elif action == "delete":
            if alert.get("status") == "notified":
                _mark_alert(
                    alert,
                    status="confirming",
                    action="request_delete",
                    now=observed_at,
                )
            if alert.get("status") == "confirming":
                title = "确认删除种子及全部数据"
                text = "此操作会删除该种子及已经下载的全部数据，且不可恢复。"
                buttons = _action_buttons(
                    plugin.__class__.__name__, token, True
                )
            else:
                text = "该速度告警已经处理，无法再发起删除。"
        elif action == "cancel":
            if alert.get("status") == "confirming":
                _mark_alert(
                    alert,
                    status="notified",
                    action="cancel_delete",
                    now=observed_at,
                )
                title = "已取消删除"
                text = "未调用下载器，任务和全部数据保持不变。"
                buttons = _action_buttons(
                    plugin.__class__.__name__, token, False
                )
            else:
                text = "删除确认已经失效或处理完成。"
        elif action == "confirm":
            if alert.get("status") != "confirming":
                text = "删除确认已经失效或处理完成。"
            else:
                service = plugin.service_info(session.downloader_id)
                instance = getattr(service, "instance", None) if service else None
                try:
                    if instance is None:
                        raise RuntimeError("downloader unavailable")
                    delete_torrent_with_files(
                        instance,
                        session.torrent_hash,
                        delete_file=True,
                    )
                    _finish_session(
                        runtime, session_key, "deleted", observed_at
                    )
                    session.sample_eligible = False
                    alert["deletion_result"] = {
                        "success": True,
                        "delete_file": True,
                        "completed_at": observed_at,
                    }
                    alert["last_action"] = "confirm_delete"
                    title = "种子及全部数据已删除"
                    text = "下载器已执行 delete_file=True，全量删除已完成。"
                except Exception as error:
                    _mark_alert(
                        alert,
                        status="confirming",
                        action="delete_failed",
                        now=observed_at,
                    )
                    alert["deletion_result"] = {
                        "success": False,
                        "delete_file": True,
                        "error": str(error),
                        "failed_at": observed_at,
                    }
                    title = "删除失败"
                    text = "下载器未确认删除成功，可重试或取消。"
                    buttons = _action_buttons(
                        plugin.__class__.__name__, token, True
                    )
        else:
            text = "无法识别该速度告警操作。"
    persist_speed_monitor_runtime(plugin, runtime, observed_at)
    _post_action_card(
        plugin,
        event_data,
        title=title,
        text=text,
        buttons=buttons,
        telegram_userid=str(alert.get("telegram_userid") or ""),
        notification_type=notification_type,
    )
    return True


__all__ = ("process_speed_message_action",)
