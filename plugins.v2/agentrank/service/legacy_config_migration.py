"""旧版筛选配置向可撤销画像证据迁移。"""

from typing import Any, Dict, Iterable, List, Mapping, Tuple

from ..model.config import WEIGHT_DEFAULTS, configured_identities


MEDIA_TYPE_LABELS: Tuple[Tuple[str, str], ...] = (
    ("movie", "电影"),
    ("tv", "剧集"),
    ("anime", "动漫"),
)


def _unique_strings(values: Any) -> List[str]:
    """返回旧配置中保持顺序的唯一非空字符串。"""
    if not isinstance(values, (list, tuple, set)):
        return []
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _evidence(kind: str, tag: str) -> Dict[str, str]:
    """构造来源固定的旧配置画像证据。"""
    return {"kind": kind, "tag": tag, "source": "legacy_config"}


def _append_preference(preferences: Any, kind: str, tag: str) -> None:
    """追加不覆盖用户现有相反选择的可撤销迁移标签。"""
    if kind == "positive":
        current = preferences.custom_tags
        opposite = preferences.custom_negative_tags
        archived = preferences.archived_tags
    else:
        current = preferences.custom_negative_tags
        opposite = preferences.custom_tags
        archived = preferences.archived_negative_tags
    if tag in opposite or tag in archived:
        return
    if tag not in current:
        current.append(tag)
    item = _evidence(kind, tag)
    if item not in preferences.legacy_config_evidence:
        preferences.legacy_config_evidence.append(item)


def _migration_items(config: Mapping[str, Any]) -> List[Tuple[str, str]]:
    """把有信息量的旧媒体子集和排除词转换为画像标签。"""
    items: List[Tuple[str, str]] = []
    if "media_types" in config:
        selected = _unique_strings(config.get("media_types"))
        allowed = [key for key, _ in MEDIA_TYPE_LABELS]
        if selected and set(selected) < set(allowed):
            selected_set = set(selected)
            items.extend(
                (
                    "positive" if key in selected_set else "negative",
                    label,
                )
                for key, label in MEDIA_TYPE_LABELS
            )
    if "exclude_keywords" in config:
        items.extend(
            ("negative", keyword)
            for keyword in _unique_strings(config.get("exclude_keywords"))
        )
    return items


def migrate_legacy_profile_config(
    plugin: Any,
    raw_config: Mapping[str, Any],
    normalized_config: Mapping[str, Any],
) -> Dict[str, Any]:
    """原子迁移旧筛选语义；配置持久化失败时恢复全部画像原值。"""
    legacy_keys = {
        key
        for key in (
            "media_types",
            "exclude_keywords",
            "discovery_sources",
            "weights",
            *WEIGHT_DEFAULTS,
        )
        if key in raw_config
    }
    if not legacy_keys:
        return {"status": "not_needed", "profile_count": 0, "evidence_count": 0}
    repository = getattr(plugin, "_repository", None)
    if repository is None:
        return {"status": "failed", "profile_count": 0, "evidence_count": 0}

    items = _migration_items(raw_config)
    snapshots: Dict[str, Any] = {}
    identities = configured_identities(normalized_config)
    evidence_count = 0
    try:
        for identity in identities:
            key = repository._profile_key("profile_preferences", identity.profile_id)
            snapshots[key] = plugin.get_data(key=key)
            preferences = repository.load_profile_preferences(identity.profile_id)
            if not preferences.username:
                preferences.username = identity.username
            before = len(preferences.legacy_config_evidence)
            for kind, tag in items:
                _append_preference(preferences, kind, tag)
            evidence_count += len(preferences.legacy_config_evidence) - before
            if preferences.to_dict() != (snapshots[key] or {}):
                repository.save_profile_preferences(preferences)

        persisted = {
            key: value
            for key, value in dict(normalized_config).items()
            if key != "_validation_errors"
        }
        plugin.update_config(config=persisted)
    except Exception:
        for key, value in snapshots.items():
            try:
                if value is None:
                    plugin.del_data(key=key)
                else:
                    plugin.save_data(key=key, value=value)
            except Exception:
                pass
        return {
            "status": "failed",
            "profile_count": len(identities),
            "evidence_count": 0,
        }
    return {
        "status": "ready",
        "profile_count": len(identities),
        "evidence_count": evidence_count,
    }
