"""豆瓣账号适配器的旧路径兼容门面。"""

from .adapter import douban_account as _account


CookieCloudHelper = _account.CookieCloudHelper
RequestUtils = _account.RequestUtils
DoubanCookieError = _account.DoubanCookieError
parse_wish_items = _account.parse_wish_items
parse_interest_feed_items = _account.parse_interest_feed_items


class DoubanApi(_account.DoubanApi):
    """保留旧导入路径及模块级 monkeypatch 行为。"""

    @staticmethod
    def _cookiecloud_helper():
        """使用兼容门面当前绑定的 CookieCloud 辅助器。"""
        return CookieCloudHelper()

    @staticmethod
    def _request_utils(**kwargs):
        """使用兼容门面当前绑定的网络请求封装。"""
        return RequestUtils(**kwargs)


__all__ = [
    "CookieCloudHelper",
    "DoubanApi",
    "DoubanCookieError",
    "RequestUtils",
    "parse_interest_feed_items",
    "parse_wish_items",
]
