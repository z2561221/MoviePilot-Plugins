"""下载速度告警的 Telegram 关闭与二次删除动作。"""

from __future__ import annotations

import html
import time
from typing import Any

from contextlib import nullcontext

from ..adapter.auto_delete import binding_of
from ..utils.torrent_adapter import TORRENT_ACTIVE, delete_torrent_with_files, normalize_torrent
from .coordination import operation_lock, operation_stopped, task_blocked
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
    original = original_message_kwargs(event_data)
    channel = (event_data or {}).get("channel")
    try:
        from app.schemas.types import NotificationChannel

        channel = NotificationChannel.Telegram
    except ImportError:
        pass
    kwargs = {
        "mtype": resolve_notification_type(
            getattr(plugin, "_speed_monitor_notification_type", "Plugin"),
            notification_type,
        ),
        "title": title,
        "text": html.escape(text),
        "parse_mode": "HTML",
        "buttons": buttons,
        "targets": {"telegram_userid": str(telegram_userid or "")},
        "save_history": False,
        **original,
    }
    if channel is not None:
        kwargs["channel"] = channel
    edit_kwargs = {
        "channel": channel,
        "source": original.get("source"),
        "message_id": original.get("original_message_id"),
        "chat_id": original.get("original_chat_id"),
        "title": title,
        "text": kwargs["text"],
        "parse_mode": "HTML",
        "buttons": buttons,
    }
    if _edit_action_card(plugin, edit_kwargs):
        return
    plugin.post_message(**kwargs)


def _edit_action_card(
    plugin: Any,
    edit_kwargs: dict[str, Any],
) -> bool:
    """通过插件处理链直接编辑原消息，确保无按钮终态也能原地收束。"""
    if not all(
        edit_kwargs.get(field)
        for field in ("channel", "message_id", "chat_id")
    ):
        return False
    chain = getattr(plugin, "chain", None)
    run_module = getattr(chain, "run_module", None)
    if not callable(run_module):
        return False
    try:
        # Chain.edit_message 不透传 parse_mode，直接使用宿主模块分发入口。
        return bool(run_module("edit_message", **edit_kwargs))
    except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        return False


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


class StaleSpeedAlert(ValueError):
    """告警对应的下载任务已无法确认。"""


def _current_delete_target(plugin, session, alert):
    """锁内复查原下载器、创建时间、路径、实时下载状态和其他模块的保护。"""
    expected = alert.get("target_identity")
    if not expected or expected != session.target_identity or not session.anomaly_active or alert.get("anomaly_epoch") != session.anomaly_epoch:
        raise StaleSpeedAlert("这张告警缺少有效的原任务记录，已停止删除。")
    service = plugin.service_info(session.downloader_id)
    if not service or not service.instance:
        raise RuntimeError("下载器连接不可用")
    if binding_of(service) != expected[0]:
        raise StaleSpeedAlert("下载器配置已变化，请查看当前下载任务。")
    response = service.instance.get_torrents(ids=[session.torrent_hash])
    rows, error = response if isinstance(response, tuple) else (response, None)
    if error or rows is None:
        raise RuntimeError("下载器未确认任务状态")
    if len(rows) != 1:
        raise StaleSpeedAlert("原下载任务已不存在或无法唯一确认。")
    raw = rows[0]
    current = normalize_torrent(raw, session.downloader_id, session.downloader_type)
    active_states = {"downloading", "forceddl", "stalleddl", "metadl", "forcedmetadl", "4"}
    current_state = current.state.lower().replace("_", "").replace(" ", "")
    if (current_state not in active_states or current.torrent_hash != session.torrent_hash or [expected[0], current.added_at, current.save_path] != expected
            or not current.state or current.state_category != TORRENT_ACTIVE or current.total_bytes <= 0
            or task_blocked(plugin, session.downloader_id, raw, session.downloader_type)):
        raise StaleSpeedAlert("任务身份、运行状态或保护已变化，旧告警已失效。")
    return service.instance


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
    generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0)
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
    guard = operation_lock(plugin) if action == "confirm" else nullcontext()
    with guard, runtime.session_lock(session_key):
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
                try:
                    instance = _current_delete_target(plugin, session, alert)
                    if (operation_stopped(plugin, generation)
                            or getattr(plugin, "_speed_monitor_runtime", runtime) is not runtime):
                        raise StaleSpeedAlert("下载中心已停止或重载，旧删除确认已失效。")
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
                except StaleSpeedAlert as error:
                    _mark_alert(alert, status="expired", action="target_changed", now=observed_at)
                    title = "删除确认已失效"
                    text = str(error)
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
    if (not operation_stopped(plugin, generation)
            and getattr(plugin, "_speed_monitor_runtime", runtime) is runtime):
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
