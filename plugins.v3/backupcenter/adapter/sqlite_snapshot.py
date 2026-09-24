"""使用 SQLite 在线备份接口读取一致快照，不复制活动日志文件。"""

import sqlite3
import time
from contextlib import closing
from pathlib import Path


def is_sqlite_database(path: Path) -> bool:
    """按文件头识别 SQLite，避免把普通同名文件误判为数据库。"""
    with path.open("rb") as stream:
        return stream.read(16) == b"SQLite format 3\x00"


def create_sqlite_snapshot(source: Path, destination: Path) -> None:
    """只读打开源库并合并已提交 WAL，繁忙超时或校验失败时拒绝备份。"""
    deadline = time.monotonic() + 30

    def check_deadline(status: int, _remaining: int, _total: int) -> None:
        """限制持续写入或锁占用导致的快照重试时间。"""
        if status != sqlite3.SQLITE_DONE and time.monotonic() >= deadline:
            raise TimeoutError("SQLite 一致性快照超时")

    uri = source.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as origin:
        with closing(sqlite3.connect(destination)) as snapshot:
            origin.backup(snapshot, pages=256, progress=check_deadline, sleep=0.05)
            # 导出独立数据库文件，恢复时不依赖源库的 WAL 或 SHM。
            snapshot.execute("PRAGMA journal_mode=DELETE")
            if snapshot.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise sqlite3.DatabaseError("SQLite 一致性快照校验失败")
