"""本实例模块操作的瞬时计数，退出或异常后自动释放。"""

from functools import wraps
from threading import RLock

_INIT_LOCK = RLock()


def activity_lock(plugin):
    """计数只属于当前插件实例，不产生持久化或外部调用。"""
    with _INIT_LOCK:
        if not hasattr(plugin, "_module_activity_lock"):
            plugin._module_activity_lock = RLock()
            plugin._module_activity = {}
        return plugin._module_activity_lock


def observed(name, *, runtime=False):
    """保留原函数合同，仅观察确实进入和退出的业务执行。"""
    def decorate(function):
        """包装入口不改变返回值或异常类型。"""
        @wraps(function)
        def wrapped(subject, *args, **kwargs):
            """嵌套或并发操作计数独立，异常仍会解除运行标记。"""
            plugin = subject.plugin if runtime else subject
            lock = activity_lock(plugin)
            with lock:
                plugin._module_activity[name] = plugin._module_activity.get(name, 0) + 1
            try:
                return function(subject, *args, **kwargs)
            finally:
                with lock:
                    remaining = plugin._module_activity.get(name, 1) - 1
                    if remaining:
                        plugin._module_activity[name] = remaining
                    else:
                        plugin._module_activity.pop(name, None)
        return wrapped
    return decorate


def activity_snapshot(plugin):
    """在短锁内投影真实进行中的模块，无网络/数据库查询。"""
    with activity_lock(plugin):
        return dict(plugin._module_activity)
