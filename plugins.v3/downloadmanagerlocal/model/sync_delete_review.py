"""同步删除人工处理条件；只判断已有快照，不访问下载器或文件。"""

import hashlib
import json

from .sync_delete import PLAN_VERSION, TERMINAL_STATES, fingerprint


def review_revision(job):
    """确认按钮绑定用户实际看到的完整记录，状态变化后要求重新查看。"""
    value = json.dumps(job, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def retry_rejection(job, config):
    """与执行队列共用的重试准入原因，不把旧错误正文当作当前事实。"""
    if not job or job["state"] in {"queued", "running"} | TERMINAL_STATES:
        return "该记录不能重试"
    plan = job.get("plan")
    if plan and plan.get("version") != PLAN_VERSION:
        return "旧版本删除计划需人工核验，不能直接重试"
    if plan and plan.get("config_fingerprint") != fingerprint(config):
        return "配置已变化，旧任务不能直接重试"
    if not plan and (job["event"].get("plan_version") != PLAN_VERSION
                     or job["event"].get("config_fingerprint") != fingerprint(config)):
        return "旧事件缺少当前版本或配置快照，不能直接重试"
    return ""


def dismissal_rejection(job, blocks):
    """只允许忽略尚未形成执行计划且无保护引用的失败记录。"""
    if not job or job.get("state") != "failed":
        return "只有待处理的失败记录可以忽略"
    if job.get("plan") is not None or any(job.get(key) for key in (
            "records_done", "sources_marked", "download_records_done", "entities_complete")):
        return "已有执行计划或操作记录，请先核验执行明细，不能直接忽略"
    if not isinstance(blocks, dict) or any(not isinstance(value, dict) for value in blocks.values()):
        return "保护记录无法核验，暂不能忽略"
    if any(value.get("job_id") == job["id"] for value in blocks.values()):
        return "此记录仍有任务保护，请先核验保护对象，不能直接忽略"
    return ""
