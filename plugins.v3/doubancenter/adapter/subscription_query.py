"""订阅去重的 SDK 查询入口及旧宿主兼容边界。"""

from app.sdk.logging import logger
from sqlalchemy.exc import SQLAlchemyError


def _sdk_queries():
    """只有旧镜像确实缺少该模块时才回退，查询故障不能降级为空。"""
    try:
        import app.sdk.queries
    except ModuleNotFoundError as err:
        if err.name != "app.sdk.queries":
            raise
        return None
    return app.sdk.queries


def _legacy_active(params):
    """兼容 2fe39d85 等没有 queries SDK 的 V3 镜像。"""
    from app.db.oper.subscribe import SubscribeOper

    return SubscribeOper().exists(**params)


def _legacy_history(params):
    """完成历史属于独立 Oper，不在 SubscribeOper 上猜测方法。"""
    from app.db.oper.subscribehistory import SubscribeHistoryOper

    return SubscribeHistoryOper().exists(**params)


def _sdk_exists(query, params):
    """服务端精确过滤后只需一个命中；不扫描未过滤的首屏。"""
    page = query(filters=params, page={"page": 1, "count": 1})
    if page.items:
        return True
    if page.total == 0:
        return False
    raise ValueError("订阅查询返回非零总数但没有条目")


def exists(params, *, subscribe_oper_cls=None):
    """命中优先；任一必要查询失败或缺失时保留未知状态。"""
    try:
        if subscribe_oper_cls is not None:
            # 保留已有调用者的显式注入接口，缺失方法仍按查询失败处理。
            oper = subscribe_oper_cls()
            lookups = (
                lambda: oper.exists(**params),
                lambda: oper.exist_history(**params),
            )
        else:
            queries = _sdk_queries()
            lookups = (
                (lambda: _sdk_exists(queries.list_subscriptions, params)) if queries
                else (lambda: _legacy_active(params)),
                (lambda: _sdk_exists(queries.list_subscription_history, params)) if queries
                else (lambda: _legacy_history(params)),
            )
    except (ImportError, AttributeError, RuntimeError, ValueError, TypeError, OSError, LookupError, SQLAlchemyError) as err:
        logger.warning(f"豆瓣中心：初始化订阅查询失败：{type(err).__name__}")
        return None
    failed = False
    for lookup in lookups:
        try:
            result = lookup()
            if result is None:
                failed = True
            elif result:
                return True
        except (ImportError, AttributeError, RuntimeError, ValueError, TypeError, OSError, LookupError, SQLAlchemyError) as err:
            failed = True
            logger.warning(f"豆瓣中心：订阅查询失败：{type(err).__name__}")
    return None if failed else False
