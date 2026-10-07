"""将运行代次绑定到当前任务，停止后禁止旧任务继续写入。"""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from threading import Event


class RunStopped(RuntimeError):
    """当前任务所属运行代次已经停止。"""


_CURRENT_RUN = ContextVar("doubancenter_run", default=None)


def start(plugin) -> None:
    """建立新代次，旧任务持有的停止信号永不复用。"""
    stop(plugin)
    plugin._run_stop = Event()


def stop(plugin) -> None:
    """发出协作停止信号，不等待不可取消的外部网络请求。"""
    event = getattr(plugin, "_run_stop", None)
    if event is not None:
        event.set()
    # 换掉缓存容器；在途旧查询即使返回，也不能把缓存重新挂回新代次。
    plugin._folio_series_cache = {}


def checkpoint(plugin) -> None:
    """在副作用边界拒绝已停止代次，重启不能使旧任务复活。"""
    current = _CURRENT_RUN.get()
    event = current[1] if current and current[0] is plugin else getattr(plugin, "_run_stop", None)
    if event is not None and event.is_set():
        raise RunStopped("豆瓣中心运行已停止，请在启用后重试")


@contextmanager
def scope(plugin, event=None):
    """嵌套业务共享发起时的代次，跨实例调用各自隔离。"""
    current = _CURRENT_RUN.get()
    if event is None:
        event = current[1] if current and current[0] is plugin else getattr(plugin, "_run_stop", None)
    token = _CURRENT_RUN.set((plugin, event))
    try:
        checkpoint(plugin)
        yield
    finally:
        _CURRENT_RUN.reset(token)


def managed(callback):
    """为定时和事件入口绑定代次，正常结束已取消的后台工作。"""
    @wraps(callback)
    def run(plugin, *args, **kwargs):
        """执行一个受停止信号约束的后台任务。"""
        try:
            with scope(plugin):
                return callback(plugin, *args, **kwargs)
        except RunStopped:
            return None
    return run


def scoped(callback):
    """为同步业务保留运行代次，由上层决定取消回执。"""
    @wraps(callback)
    def run(plugin, *args, **kwargs):
        """在发起时的代次内执行同步业务。"""
        with scope(plugin):
            return callback(plugin, *args, **kwargs)
    return run


@contextmanager
def serialized(plugin, lock):
    """等待串行锁时响应停止，获得锁后再次核验代次。"""
    while True:
        checkpoint(plugin)
        if lock.acquire(timeout=0.1):
            break
    try:
        checkpoint(plugin)
        yield
    finally:
        lock.release()


def bind(plugin, callback):
    """在注册调度时捕获代次，防止旧队列任务在重载后启动。"""
    event = getattr(plugin, "_run_stop", None)

    @wraps(callback)
    def run(*args, **kwargs):
        """只运行所属代次仍有效的调度回调。"""
        try:
            with scope(plugin, event):
                return callback(*args, **kwargs)
        except RunStopped:
            return None
    return run
