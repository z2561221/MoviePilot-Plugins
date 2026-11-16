"""豆瓣想看同步：账号基线、待处理队列、媒体识别及明确订阅回执。"""

import datetime

from app.chain.media import MediaChain
from app.schemas.types import MediaSource, MediaType
from app.sdk.logging import logger
from app.sdk.media import MetaInfo

from ..model.identity import convert_identity, recognize_media
from ..storage import records as storage
from . import lifecycle, wish_accounts
from .folio_account import _create_douban_api, _send_wish_notification

WISH_RECOGNIZE_MAX_RETRIES = 3
WISH_RANK_KEY = "douban_wish"
WISH_RANK_NAME = "豆瓣想看"

@lifecycle.managed
def run_wish_scheduled(self) -> None:
    """执行豆瓣想看同步定时入口。"""
    run_wish_sync(self)
    process_wish_queue(self)



def run_wish_sync(self, api=None, request_get=None) -> None:
    """逐账号读取想看，首次建立各自基线，后续将全局新增条目入队。"""
    state = storage.read_folio_wish_state(self)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        dh = api if api is not None else _create_douban_api(self)
        batch = wish_accounts.read_wish_accounts(
            self, dh, state,
            max_pages=max(1, int(getattr(self, "_wish_max_pages", 1) or 1)),
            days=max(0, int(getattr(self, "_wish_days", 7) or 7)),
            now=now,
            request_get=request_get,
        )
    except lifecycle.RunStopped:
        raise
    except Exception as err:
        state.update({"last_run": now, "last_error": f"读取想看失败：{err}"})
        storage.save_folio_wish_state(self, state)
        logger.warning(f"豆瓣想看读取失败：{err}")
        _send_wish_notification(self, f"读取想看失败：{err}", throttle_key="wish_read_failed")
        return

    read_error = "；".join(batch.errors)
    state.update({"accounts": batch.accounts, "last_run": now, "last_error": read_error})
    if not batch.succeeded:
        storage.save_folio_wish_state(self, state)
        logger.warning(f"豆瓣想看读取失败：{read_error}")
        _send_wish_notification(self, read_error, throttle_key="wish_read_failed")
        return

    seen = storage.read_folio_wish_seen(self)
    queue = storage.read_folio_wish_queue(self)
    processed = storage.read_folio_wish_processed(self)
    failed = storage.read_folio_wish_failed(self)
    seen_ids = {str(r.get("subject_id")) for r in seen if r.get("subject_id")}

    queue_ids = {str(r.get("subject_id")) for r in queue if r.get("subject_id")}
    processed_ids = {str(r.get("subject_id")) for r in processed if r.get("subject_id")}
    retryable_failed = _latest_retryable_wish_failures(failed)
    added = 0
    recovered = 0
    for item in batch.items:
        subject_id = str(item.get("subject_id") or "")
        if not subject_id:
            continue
        if subject_id in seen_ids:
            failed_record = retryable_failed.get(subject_id)
            retry = int((failed_record or {}).get("retry", 0) or 0)
            recognize_title = _wish_recognize_title(item.get("title"))
            failed_recognize_title = str((failed_record or {}).get("recognize_title") or "")
            reset_recognition_retries = (
                bool(failed_record)
                and retry >= WISH_RECOGNIZE_MAX_RETRIES
                and failed_recognize_title != recognize_title
            )
            if (
                failed_record
                and subject_id not in queue_ids
                and subject_id not in processed_ids
                and (retry < WISH_RECOGNIZE_MAX_RETRIES or reset_recognition_retries)
            ):
                queue_ids.add(subject_id)
                if reset_recognition_retries:
                    failed = _clear_wish_failed(failed, subject_id, reason="recognize_failed")
                queue.append(_wish_queue_record(item, now, retry=0 if reset_recognition_retries else retry))
                recovered += 1
            continue
        seen_ids.add(subject_id)
        seen.append(_wish_seen_record(item, now))
        if subject_id not in queue_ids:
            queue_ids.add(subject_id)
            queue.append(_wish_queue_record(item, now))
            added += 1
    # 已初始化账号的新条目先处理，不能被另一个新账号的基线覆盖。
    baselined = 0
    for item in batch.baseline_items:
        subject_id = str(item.get("subject_id") or "")
        if subject_id and subject_id not in seen_ids:
            seen_ids.add(subject_id)
            seen.append(_wish_seen_record(item, now))
            baselined += 1
    state["initialized"] = True
    if not state.get("baseline_at"):
        state["baseline_at"] = now
    storage.save_folio_wish_seen(self, seen)
    storage.save_folio_wish_queue(self, queue)
    storage.save_folio_wish_failed(self, failed)
    storage.save_folio_wish_state(self, state)
    logger.info(
        f"豆瓣想看同步完成，成功读取 {batch.succeeded} 个账号，"
        f"建立基线 {baselined} 条，新增入队 {added} 条，恢复重试 {recovered} 条"
    )
    if read_error:
        logger.warning(f"豆瓣想看部分账号读取失败：{read_error}")
        _send_wish_notification(self, read_error, throttle_key="wish_read_failed")



def _wish_recognize_title(title):
    """提取豆瓣 feed 别名串中的首个主标题用于媒体识别。"""
    value = str(title or "").strip()
    primary = value.split(" / ", 1)[0].strip()
    return primary or value



def _default_wish_recognize(self):
    """返回默认的想看识别函数。"""
    def recognize(title, year, subject_id=None):
        """优先按豆瓣 subject ID 识别想看条目，失败后回退标题识别。"""
        meta = MetaInfo(_wish_recognize_title(title))
        if year:
            meta.year = str(year)
        chain = MediaChain()
        mtype = meta.type if meta.type in (MediaType.MOVIE, MediaType.TV) else None
        if subject_id:
            try:
                source, media_id = convert_identity(
                    chain,
                    target_source=MediaSource.TMDB,
                    media_source=MediaSource.Douban,
                    media_id=subject_id,
                    mtype=mtype,
                    season=getattr(meta, "begin_season", None),
                )
            except Exception as err:
                logger.warning(f"豆瓣想看《{title}》subject ID 转换 TMDB 失败：{err}")
                source, media_id = None, None
            if source and media_id:
                try:
                    mediainfo = recognize_media(
                        chain,
                        meta=meta,
                        mtype=mtype,
                        media_source=source,
                        media_id=media_id,
                    )
                except Exception as err:
                    logger.warning(f"豆瓣想看《{title}》TMDB ID {media_id} 识别失败：{err}")
                    mediainfo = None
                if mediainfo:
                    return mediainfo
        return chain.recognize_by_meta(meta)
    return recognize



@lifecycle.managed
def process_wish_queue(self, recognize=None, subscribe=None) -> None:
    """处理想看待订阅队列，识别后通过现有订阅链创建订阅。"""
    queue = storage.read_folio_wish_queue(self)
    if not queue:
        return
    processed = storage.read_folio_wish_processed(self)
    failed = storage.read_folio_wish_failed(self)
    state = storage.read_folio_wish_state(self)
    uses_default_recognizer = recognize is None
    recognizer = recognize or _default_wish_recognize(self)
    subscriber = subscribe
    if subscriber is None:
        from . import subscription as subscription_service

        def subscriber(*args, **kwargs):
            """读取明确订阅回执，不再用历史条数猜测本次结果。"""
            return subscription_service.add_subscription(*args, **kwargs, with_result=True)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    remaining = []
    for item in queue:
        lifecycle.checkpoint(self)
        subject_id = str(item.get("subject_id") or "")
        title = item.get("title") or ""
        year = item.get("year") or ""
        link = item.get("link") or ""
        mediainfo = None
        try:
            mediainfo = (
                recognizer(title, year, subject_id)
                if uses_default_recognizer
                else recognizer(title, year)
            )
        except Exception as err:
            logger.warning(f"豆瓣想看识别失败：{title} {err}")
            mediainfo = None
        if not mediainfo:
            retry = _record_wish_failed(failed, item, "recognize_failed", now)
            if retry < WISH_RECOGNIZE_MAX_RETRIES:
                remaining.append(_wish_queue_record(item, now, retry=retry))
            continue
        lifecycle.checkpoint(self)
        failed = _clear_wish_failed(failed, subject_id, reason="recognize_failed")
        subscribe_failed = False
        subscribe_reason = ""
        try:
            meta = MetaInfo(_wish_recognize_title(title))
            if year:
                meta.year = str(year)
            result = subscriber(
                self, mediainfo, meta=meta, record_title=title,
                rank_key=WISH_RANK_KEY, rank_name=WISH_RANK_NAME, source_link=link,
            )
        except Exception as err:
            result = None
            subscribe_failed = True
            subscribe_reason = str(err) or "subscribe_failed"
            logger.warning(f"豆瓣想看订阅失败：{title} {err}")
        if not subscribe_failed and _subscribe_result_is_failed(result):
            subscribe_failed = True
            subscribe_reason = _subscribe_failure_reason(result)
        if subscribe_failed:
            retry = _record_wish_failed(failed, item, "subscribe_failed", now, subscribe_reason)
            remaining.append(_wish_queue_record(item, now, retry=retry))
            continue
        failed = _clear_wish_failed(failed, subject_id, reason="subscribe_failed")
        processed.append({"subject_id": subject_id, "title": title, "processed_at": now})

    storage.save_folio_wish_queue(self, remaining)
    storage.save_folio_wish_processed(self, processed)
    storage.save_folio_wish_failed(self, failed)
    state.update({"last_run": now, "last_processed": len(processed), "last_failed": len(failed)})
    storage.save_folio_wish_state(self, state)
    logger.info(f"豆瓣想看队列处理完成，处理 {len(processed)} 条，失败 {len(failed)} 条")



def _record_wish_failed(failed, item, reason, now, message=""):
    """记录想看同步失败条目并返回累计重试次数。"""
    subject_id = str(item.get("subject_id") or "")
    retry = int(item.get("retry", 0) or 0) + 1
    for record in reversed(failed):
        if str(record.get("subject_id") or "") == subject_id and record.get("reason") == reason:
            retry = int(record.get("retry", 0) or 0) + 1
            break
    record = {
        "subject_id": subject_id,
        "title": item.get("title") or "",
        "reason": reason,
        "message": message or reason,
        "retry": retry,
        "failed_at": now,
    }
    if reason == "recognize_failed":
        record["recognize_title"] = _wish_recognize_title(item.get("title"))
    failed.append(record)
    return retry



def _latest_retryable_wish_failures(failed):
    """按条目返回仍可恢复的最新识别失败记录。"""
    latest = {}
    for record in failed or []:
        if not isinstance(record, dict):
            continue
        subject_id = str(record.get("subject_id") or "")
        if not subject_id:
            continue
        latest[subject_id] = record
    return {
        subject_id: record for subject_id, record in latest.items()
        if record.get("reason") == "recognize_failed"
    }



def _clear_wish_failed(failed, subject_id, reason=""):
    """清理指定条目已经恢复成功的失败记录。"""
    target_id = str(subject_id or "")
    return [
        record for record in (failed or [])
        if not (
            isinstance(record, dict)
            and str(record.get("subject_id") or "") == target_id
            and (not reason or record.get("reason") == reason)
        )
    ]



def _subscribe_result_is_failed(result) -> bool:
    """仅明确成功或已存在可出队；空回执和布尔失败均保留重试。"""
    from .subscription import SubscriptionResult

    if isinstance(result, SubscriptionResult):
        return result.status not in {"success", "existing"}
    if isinstance(result, dict):
        status = str(result.get("status") or result.get("result") or "").lower()
        if status in {"failed", "failure", "error", "cancelled"}:
            return True
        return not (result.get("existing") is True or status in {"success", "existing"}
                    or result.get("ok") is True or result.get("success") is True)
    return result is not True



def _subscribe_failure_reason(result) -> str:
    """从订阅调用结果中提取失败原因。"""
    from .subscription import SubscriptionResult

    if isinstance(result, SubscriptionResult):
        return result.reason or "subscribe_failed"
    if not isinstance(result, dict):
        return "subscribe_failed"
    return str(result.get("reason") or result.get("message") or "subscribe_failed")



def _wish_seen_record(item, now):
    """构造已见想看条目的最小记录。"""
    return {"subject_id": str(item.get("subject_id") or ""), "title": item.get("title", ""), "seen_at": now}



def _wish_queue_record(item, now, retry=None):
    """构造待处理想看条目的队列记录。"""
    retry_count = int(item.get("retry", 0) or 0) if retry is None else int(retry or 0)
    return {
        "subject_id": str(item.get("subject_id") or ""),
        "title": item.get("title", ""),
        "year": item.get("year", ""),
        "link": item.get("link", ""),
        "poster": item.get("poster", ""),
        "wish_time": item.get("wish_time", ""),
        "enqueued_at": now,
        "retry": retry_count,
    }
