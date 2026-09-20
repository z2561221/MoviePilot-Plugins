"""按插件数据目录隔离、跨 Python 对象与重载有效的执行锁。"""

import errno
import importlib
import os
from pathlib import Path
from threading import Event, Lock


class CleanupCancelled(Exception):
    """当前模块已停止，取消尚未提交的后续操作。"""


class CleanupExecution:
    """线程锁保护本对象，系统文件锁协调旧/新插件对象与进程。"""

    def __init__(self, directory: Path):
        self.path = Path(directory) / "library_cleanup.lock"
        self._cancelled = Event()
        self._thread_lock = Lock()
        self._stream = None
        self._native = importlib.import_module("msvcrt" if os.name == "nt" else "fcntl")

    @property
    def stopped(self) -> bool:
        """返回模块是否已经收到停止请求。"""
        return self._cancelled.is_set()

    def cancel(self) -> None:
        """唤醒等待者；正在进行的请求由调用者按结果收尾。"""
        self._cancelled.set()

    def check(self) -> None:
        """在下一次网络请求或扫描提交前检查取消。"""
        if self.stopped:
            raise CleanupCancelled()

    def wait(self, seconds: float) -> bool:
        """可中断等待，返回是否收到停止请求。"""
        return self._cancelled.wait(max(0, seconds))

    def _lock_file(self, stream) -> None:
        stream.seek(0)
        if os.name == "nt":
            self._native.locking(stream.fileno(), self._native.LK_NBLCK, 1)
        else:
            self._native.flock(stream.fileno(), self._native.LOCK_EX | self._native.LOCK_NB)

    def _unlock_file(self, stream) -> None:
        stream.seek(0)
        if os.name == "nt":
            self._native.locking(stream.fileno(), self._native.LK_UNLCK, 1)
        else:
            self._native.flock(stream.fileno(), self._native.LOCK_UN)

    def acquire(self, blocking: bool = True) -> bool:
        """按需等待同一实例旧执行者退出，停止时不再取得执行权。"""
        while not self.stopped:
            if self._thread_lock.acquire(blocking=False):
                stream = None
                owns_thread_lock = True
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    stream = self.path.open("a+b", buffering=0)
                    if stream.seek(0, os.SEEK_END) == 0:
                        stream.write(b"\0")
                    try:
                        self._lock_file(stream)
                    except OSError as error:
                        if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                            raise
                    else:
                        self._stream = stream
                        stream = None
                        owns_thread_lock = False
                        if not self.stopped:
                            return True
                        self.release()
                        return False
                finally:
                    if stream is not None:
                        stream.close()
                    if owns_thread_lock:
                        self._thread_lock.release()
            if not blocking or self.wait(0.05):
                return False
        return False

    def release(self) -> None:
        """释放当前句柄，保留锁文件以维持所有对象的同一锁身份。"""
        stream, self._stream = self._stream, None
        if stream is None:
            raise RuntimeError("cleanup execution lock is not held")
        try:
            self._unlock_file(stream)
        finally:
            stream.close()
            self._thread_lock.release()
