"""限速分配的批量执行边界，接收计算结果并保留逐任务恢复状态。"""

import logging
from collections import defaultdict

from ..adapter.upload_limit import (
    expected_torrent_upload_settings,
    settings_from_dict,
    settings_to_dict,
    torrent_settings_equal,
    write_torrent_upload_limits,
)

logger = logging.getLogger(__name__)
UPLOAD_WRITE_BATCH_SIZE = 100


def matches_managed_settings(record, current):
    """失败块可能部分生效，两种已记录意图都保留接管前原值。"""
    return any(isinstance(value, dict) and torrent_settings_equal(current, settings_from_dict(value))
               for value in (record.get("last_written_settings"), record.get("pending_write_settings")))


def _applied(record, expected, desired_kib, timestamp):
    """只在已相同或接口确认后记录成功，并清除待确认意图。"""
    record.update(last_allocation_kib=desired_kib, last_written_settings=settings_to_dict(expected),
                  last_applied_at=timestamp)
    record.pop("pending_write_settings", None)


def apply_torrent_limits(tasks, contexts, records, desired_limits, timestamp, checkpoint, errors):
    """按下载器与额度合并请求，分块失败归属每项且不盲目重发。"""
    groups = defaultdict(list)
    for key, snapshot in tasks.items():
        if snapshot.downloader_id not in contexts:
            continue
        desired = max(0, int(desired_limits.get(key, 0)))
        expected = expected_torrent_upload_settings(snapshot.downloader_type, desired)
        if torrent_settings_equal(snapshot.upload_settings, expected):
            _applied(records[key], expected, desired, timestamp)
        else:
            groups[(snapshot.downloader_id, snapshot.downloader_type, desired)].append((key, snapshot))
    for (downloader_id, kind, desired), members in groups.items():
        expected = expected_torrent_upload_settings(kind, desired)
        for offset in range(0, len(members), UPLOAD_WRITE_BATCH_SIZE):
            checkpoint()
            batch = members[offset:offset + UPLOAD_WRITE_BATCH_SIZE]
            for key, _ in batch:
                records[key]["pending_write_settings"] = settings_to_dict(expected)
            try:
                applied = write_torrent_upload_limits(contexts[downloader_id].service.instance, kind,
                                                     [snapshot.torrent_hash for _, snapshot in batch], desired)
            except Exception as error:
                checkpoint()
                for _, snapshot in batch:
                    errors[downloader_id].append(f"{snapshot.torrent_hash}: {error}")
                logger.exception("上传限速批量写入下载器 %s 失败，涉及 %s 个任务", downloader_id, len(batch))
                continue
            for key, _ in batch:
                _applied(records[key], applied, desired, timestamp)
            checkpoint()
