"""逐账号读取想看结果，分别维护基线并汇总可处理的新条目。"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from ..adapter.douban_account import normalize_wish_user_ids
from .lifecycle import RunStopped, checkpoint


@dataclass
class WishReadBatch:
    """一次读取中成功账号的条目、首次基线和失败原因。"""

    accounts: dict
    items: list = field(default_factory=list)
    baseline_items: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    succeeded: int = 0


def _merge_items(items: list) -> list:
    """按豆瓣条目 ID 去重，合并其他账号提供的缺失字段。"""
    merged = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        subject_id = str(item.get("subject_id") or "")
        if not subject_id:
            continue
        if subject_id not in merged:
            merged[subject_id] = dict(item, subject_id=subject_id)
            continue
        for key, value in item.items():
            if merged[subject_id].get(key) in (None, "") and value not in (None, ""):
                merged[subject_id][key] = value
    return list(merged.values())


def _account_states(state: dict, configured_ids: list, cookie_user_id: str) -> dict:
    """承接旧单账号基线，已有账号状态和其他历史数据保持原样。"""
    accounts = dict(state.get("accounts") or {}) if isinstance(state.get("accounts"), Mapping) else {}
    if "accounts" not in state and state.get("initialized"):
        # 旧实现始终优先 Cookie；没有 Cookie 时，只有单账号配置能对应旧基线。
        legacy_user_id = cookie_user_id or (configured_ids[0] if len(configured_ids) == 1 else "")
        if legacy_user_id:
            accounts[legacy_user_id] = {
                "initialized": True,
                "baseline_at": state.get("baseline_at", ""),
            }
    return accounts


def read_wish_accounts(plugin, api, state: dict, *, max_pages: int, days: int,
                       now: str, request_get=None) -> WishReadBatch:
    """一个账号读取失败不阻断其他账号，首次成功只产生该账号的基线。"""
    configured_ids = normalize_wish_user_ids(getattr(plugin, "_wish_user", ""))
    cookie_reader = getattr(api, "get_cookie_user_id", None)
    cookie_user_id = str(cookie_reader() or "").strip() if callable(cookie_reader) else ""
    targets = configured_ids or [cookie_user_id]
    batch = WishReadBatch(accounts=_account_states(state, configured_ids, cookie_user_id))
    for user_id in targets:
        checkpoint(plugin)
        previous = batch.accounts.get(user_id)
        account = dict(previous) if isinstance(previous, Mapping) else {}
        batch.accounts[user_id] = account
        try:
            items = api.get_wish_items(
                user_id=user_id, max_pages=max_pages, days=days, request_get=request_get,
            ) or []
        except RunStopped:
            raise
        except (RuntimeError, ValueError, OSError) as error:
            checkpoint(plugin)
            message = f"账号 {user_id or 'Cookie 默认账号'}：{error}"
            account.update({"last_run": now, "last_error": message})
            batch.errors.append(message)
            continue
        checkpoint(plugin)
        batch.succeeded += 1
        account.update({"last_run": now, "last_error": ""})
        if account.get("initialized"):
            batch.items.extend(items)
        else:
            batch.baseline_items.extend(items)
            account.update({"initialized": True, "baseline_at": now})
    batch.items = _merge_items(batch.items)
    batch.baseline_items = _merge_items(batch.baseline_items)
    return batch
