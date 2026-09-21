"""清理计划的手动只读核验，与扫描、清理共享实例执行锁。"""

import time
from datetime import datetime, timezone

from ..model.cleanup_recheck import CleanupReadError
from ..model.library_cleanup import build_cleanup_conditions, candidate_from_plan_item
from .cleanup_execution import CleanupCancelled

RECHECK_LIMIT = 10
RECHECK_SECONDS = 20


def _inspect(module, item, conditions, checked_at):
    """查询当前条目状态，失败始终保留且提供恢复方向。"""
    movie = candidate_from_plan_item(item)
    try:
        state, fresh, reason = module._precheck_candidate(movie, conditions, checked_at, diagnose=True)
    except CleanupReadError as error:
        return "unknown", movie, str(error), error.action, error.code
    hints = {
        "删除前筛选字段不完整": "在媒体服务器检查入库日期、收藏和观看状态后重新核验",
        "删除前条目身份不一致": "在媒体服务器确认该条目，再重新生成计划",
    }
    action = hints.get(reason, "检查媒体服务器连接、用户权限后重新核验")
    return state, fresh, reason.removeprefix("删除前"), action, "state_unknown"


def recheck_plan(module, queue_key=None):
    """最多核验十条异常；单条请求不扩大范围，取消时保留未处理记录。"""
    result = {"operation": "recheck", "results": [], "processed_count": 0,
              "restored_count": 0, "removed_count": 0, "unknown_count": 0,
              "pending_count": 0, "stopped": False}
    if module._run_lock.stopped:
        return {**result, "success": False, "stopped": True, "summary": "插件已停止，请启用后重新核验"}
    if not module._run_lock.acquire(blocking=False):
        return {**result, "success": False, "busy": True, "summary": "已有扫描、清理或核验任务运行，请稍后重试"}
    started = time.monotonic()
    try:
        plan = module._load_plan()
        if queue_key is not None:
            selected = [item for item in plan["items"] if item["queue_key"] == queue_key]
            if not selected:
                return {**result, "success": False, "summary": "该条目已不在计划中，请刷新列表"}
        else:
            selected = sorted((item for item in plan["items"] if item.get("last_error")),
                              key=lambda item: item.get("last_recheck_at") or "")
        conditions = build_cleanup_conditions(module.config)
        removed, recovered = set(), []
        with module.adapter.user_scope(module._run_lock.check):
            for item in selected[:RECHECK_LIMIT]:
                if time.monotonic() - started >= RECHECK_SECONDS:
                    break
                try:
                    module._run_lock.check()
                    checked_at = datetime.now(timezone.utc)
                    state, fresh, reason, action, code = _inspect(module, item, conditions, checked_at)
                    module._run_lock.check()
                except CleanupCancelled:
                    result["stopped"] = True
                    break
                item["last_recheck_at"] = checked_at.isoformat()
                if state in ("absent", "skipped"):
                    removed.add(item["queue_key"])
                    recovered.append(item["queue_key"])
                    result["removed_count"] += 1
                    reason = "条目已不存在，已移出计划" if state == "absent" else f"{reason or '已不符合清理条件'}，已移出计划"
                    action, code = "无需处理", ""
                elif state == "eligible":
                    item.update(fresh.to_dict(checked_at))
                    item.update(last_error="", error_code="", recovery_hint="")
                    recovered.append(item["queue_key"])
                    result["restored_count"] += 1
                    reason, action, code = "状态正常，已恢复待处理", "后续按清理周期处理", ""
                else:
                    item.update(last_error=reason, recovery_hint=action, error_code=code)
                    result["unknown_count"] += 1
                result["results"].append({"queue_key": item["queue_key"], "title": item.get("title") or item.get("movie_id"),
                                          "state": state, "reason": reason, "action": action, "error_code": code})
        result["processed_count"] = len(result["results"])
        result["pending_count"] = len(selected) - result["processed_count"]
        plan["items"] = [item for item in plan["items"] if item["queue_key"] not in removed]
        result["queue_count"] = len(plan["items"])
        if result["processed_count"]:
            module._save_plan(plan)
            module._alerts().resolve_rechecked(recovered)
            if not any(item.get("last_error") for item in plan["items"]) and module.last_error == "本轮清理未全部完成":
                module.last_error = ""
        result["success"] = not result["unknown_count"] and not result["stopped"]
        result["summary"] = (f"已核验 {result['processed_count']} 部：恢复待处理 {result['restored_count']} 部，"
                             f"移出计划 {result['removed_count']} 部，仍需处理 {result['unknown_count']} 部。未执行媒体删除。")
        if result["pending_count"]:
            result["summary"] += f" 另有 {result['pending_count']} 部未核验，可继续核验。"
        if result["stopped"]:
            result["summary"] = "核验已停止。" + result["summary"]
        if result["processed_count"]:
            module.add_history("success" if result["success"] else "failed", result["summary"], time.monotonic() - started)
        return result
    finally:
        module._run_lock.release()
