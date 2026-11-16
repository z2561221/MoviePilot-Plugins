"""豆瓣账号客户端、登录探测与通知节流；播放和想看服务共享此入口。"""

import datetime

from app.schemas.types import MessageType
from app.sdk.logging import logger

from ..adapter.douban_account import DoubanApi
from . import lifecycle

WISH_NOTIFY_THROTTLE_SECONDS = 6 * 60 * 60

def _create_douban_api(self):
    """统一接入 CK 失败告警，覆盖想看、搜索和观影同步入口。"""
    return DoubanApi(
        user_cookie=getattr(self, "_folio_cookie", ""),
        on_ck_failure=lambda: _send_failure_notification(
            self,
            "豆瓣 CK 请求失败",
            "请求 ck 失败，未取得豆瓣校验令牌。请检查豆瓣登录 Cookie 和网络访问后重试。",
            throttle_key="cookie_invalid",
        ),
    )



def check_cookie_periodically(self) -> None:
    """定期检查明确的登录证据，网络或页面异常不推断 Cookie 失效。"""
    now = datetime.datetime.now().timestamp()
    if now - getattr(self, "_last_cookie_check_time", 0) <= 3600:
        return
    self._last_cookie_check_time = now
    try:
        # 健康检查不挂接业务 CK 失败通知，避免探测异常被当作同步失败。
        status, reason = DoubanApi(user_cookie=getattr(self, "_folio_cookie", "")).get_login_status()
    except lifecycle.RunStopped:
        raise
    except Exception as err:
        # 异常正文可能含请求参数或 Cookie，只记录异常类型。
        logger.warning(f"豆瓣登录状态检查未完成：{type(err).__name__}；未判定 Cookie 失效")
        return
    lifecycle.checkpoint(self)
    if status == "valid":
        logger.info("豆瓣登录状态检查通过")
    elif status == "login_required":
        logger.warning(f"豆瓣登录状态异常：{reason}")
        if getattr(self, "_folio_notify", False):
            _send_failure_notification(
                self, "豆瓣登录状态异常",
                "豆瓣返回登录验证要求，请检查登录状态，必要时更新 Cookie。",
                throttle_key="login_required",
            )
    else:
        logger.warning(f"豆瓣登录状态检查未确认（{status}）：{reason}；未判定 Cookie 失效")



def _send_folio_notification(self, success: bool, message: str):
    if not self._folio_notify:
        return
    t = f"豆瓣观影档案 {'成功' if success else '失败'}"
    msg = message.strip() + f"\n时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        self.post_message(mtype=MessageType.Plugin, title=t, text=msg, parse_mode="plain")
    except Exception as e:
        logger.error(f'{self.plugin_name} 发送通知失败: {e}')



def _send_wish_notification(
    self, message: str, throttle_key: str = "wish",
    throttle_seconds: int = WISH_NOTIFY_THROTTLE_SECONDS,
):
    """通过同步想看通知开关发送普通失败消息，并按类型节流。"""
    if not getattr(self, "_wish_notify", False):
        return
    _send_failure_notification(self, "豆瓣想看同步失败", message, throttle_key, throttle_seconds)



def _send_failure_notification(
    self, title: str, message: str, throttle_key: str,
    throttle_seconds: int = WISH_NOTIFY_THROTTLE_SECONDS,
):
    """发送已经通过业务门禁的故障通知；发送失败不消耗节流窗口。"""
    now_ts = datetime.datetime.now().timestamp()
    last_map = getattr(self, "_wish_notification_last_times", None)
    if not isinstance(last_map, dict):
        last_map = {}
    last_ts = float(last_map.get(throttle_key, 0) or 0)
    if throttle_seconds and now_ts - last_ts < throttle_seconds:
        return
    msg = message.strip() + f"\n时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        self.post_message(mtype=MessageType.Plugin, title=title, text=msg, parse_mode="plain")
        last_map[throttle_key] = now_ts
        self._wish_notification_last_times = last_map
    except Exception as e:
        logger.error(f'{self.plugin_name} 发送同步想看通知失败: {e}')
