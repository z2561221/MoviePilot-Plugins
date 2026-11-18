"""纯规则判断，保存暂停前的实际值而不是操作后的零速度。"""

import regex

from ..model.auto_delete import REGEX_FIELDS, MatchResult, Rule, Snapshot


def match_rule(rule: Rule, torrent: Snapshot, now: float, *, compiled=None, basic=False) -> MatchResult:
    """同规则 AND、排除优先；任何指定字段缺失均为无法判断。"""
    reasons = []
    def result(status, reason=""):
        """在同一返回模型中保留本次判定的每个依据。"""
        return MatchResult(rule_id=rule.id, rule_name=rule.name, revision=rule.revision,
                           status=status, reasons=reasons + ([reason] if reason else []))
    if torrent.downloader not in rule.downloaders or not torrent.completed:
        return result("no_match", "下载器不在范围内或任务尚未完成/正在校验移动")
    if not torrent.valid_hash or not torrent.added_at or torrent.added_at <= 0 or torrent.added_at > now or not torrent.save_path:
        return result("unknown", "任务缺少 hash、添加时间或保存路径")
    patterns = compiled if compiled is not None else compile_rule(rule)

    def matches(field_name, value):
        """为每次正则执行设置超时，不能拖住整个扫描。"""
        return bool(patterns[field_name].search(str(value), timeout=0.025))

    try:
        for prefix, values in (("name", [torrent.name]), ("path", [torrent.save_path]),
                               ("tag", torrent.tags)):
            for suffix in ("exclude", "include"):
                field_name = prefix + "_" + suffix
                if field_name not in patterns:
                    continue
                if values is None:
                    return result("unknown", f"{prefix} 字段不可用")
                found = any(matches(field_name, value) for value in values)
                if (suffix == "exclude" and found) or (suffix == "include" and not found):
                    return result("no_match", f"{field_name} 条件未通过")
                labels = {"name": "种子名称", "path": "保存路径", "tag": "标签"}
                values_text = "、".join(str(value) for value in values)[:2048]
                reasons.append(f"{labels[prefix]}{'排除' if suffix == 'exclude' else '包含'}正则通过；实际值 {values_text}")
        if "category" in patterns:
            if torrent.category is None:
                return result("unknown", "下载器不提供分类/group 字段")
            if not matches("category", torrent.category):
                return result("no_match", "分类未命中")
            reasons.append(f"分类 {torrent.category} 命中")
        if not basic and any(field_name in patterns for field_name in ("tracker_include", "tracker_exclude", "tracker_error")):
            if torrent.trackers is None or not torrent.trackers:
                return result("unknown", "Tracker 明细不可用或没有有效 announce")
            if "tracker_exclude" in patterns and any(matches("tracker_exclude", tracker.url) for tracker in torrent.trackers):
                return result("no_match", "命中 Tracker 排除条件")
            selected = [tracker for tracker in torrent.trackers if "tracker_include" not in patterns
                        or matches("tracker_include", tracker.url)]
            if not selected:
                return result("no_match", "没有 Tracker 命中包含范围")
            if "tracker_error" in patterns:
                if any(tracker.status == "unknown" for tracker in selected):
                    return result("unknown", "范围内 Tracker 状态未知")
                if any(tracker.status != "error" or not matches(
                    "tracker_error", tracker.status + " " + tracker.message,
                ) for tracker in selected):
                    return result("no_match", "范围内仍有正常 Tracker 或报错条件不一致")
            reasons.append(f"Tracker 条件通过，范围内 {len(selected)} 条 announce；状态 "
                           + "、".join(tracker.status for tracker in selected))
    except TimeoutError:
        return result("unknown", "正则匹配超时，停止该任务判定")

    conditions = rule.conditions
    values = (
        ("ratio", float("inf") if torrent.ratio_state == "infinite" else torrent.ratio,
         conditions.ratio_min, conditions.ratio_max, "分享率"),
        ("seed", None if torrent.seed_seconds is None else torrent.seed_seconds / 3600,
         None if basic else conditions.seed_hours_min, None, "累计做种小时"),
        ("added", None if torrent.added_at is None else (now - torrent.added_at) / 3600,
         conditions.added_hours_min, None, "添加小时"),
        ("size", None if torrent.total_bytes is None else torrent.total_bytes / 1024 ** 3,
         conditions.size_gib_min, conditions.size_gib_max, "体积 GiB"),
        ("upload", None if torrent.upload_bps is None else torrent.upload_bps / 1024,
         None, conditions.upload_kib_max, "当前上传 KiB/s"),
    )
    for _, value, minimum, maximum, label in values:
        if minimum is None and maximum is None:
            continue
        if value is None or value < 0:
            return result("unknown", label + "不可用")
        if minimum is not None and value < minimum or maximum is not None and value > maximum:
            return result("no_match", f"{label} {value:.4g} 未达阈值")
        reasons.append(f"{label} {value:.4g}，范围 [{minimum if minimum is not None else '不限'}, {maximum if maximum is not None else '不限'}]")
    return result("match")


def compile_rule(rule: Rule) -> dict:
    """每条规则每轮编译一次，所有下载器任务共享编译结果。"""
    flags = regex.IGNORECASE if rule.ignore_case else 0
    return {field_name: regex.compile(getattr(rule.conditions, field_name), flags)
            for field_name in REGEX_FIELDS if getattr(rule.conditions, field_name)}
