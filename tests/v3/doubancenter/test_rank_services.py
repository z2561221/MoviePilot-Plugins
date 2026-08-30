"""豆瓣中心榜单服务边界测试。"""

from types import SimpleNamespace

from app.schemas.types import MediaType

from app.plugins.doubancenter.service import rank_recognition
from app.plugins.doubancenter.service import rank_refresh
from app.plugins.doubancenter.service import rank_snapshot
from app.plugins.doubancenter.service import rank_subscription


def test_rank_snapshot_preserves_observation_state(monkeypatch):
    """刷新同一条目时必须保留观察中和已删除观察状态。"""
    existing = {
        "title": "旧标题",
        "unique": "dc2_rank:https://example.test/item",
        "observing": True,
        "first_seen": "2026-08-01 00:00:00",
        "observe_deleted": True,
        "observe_deleted_at": "2026-08-02 00:00:00",
        "tmdbid": "123",
    }
    saved = {}
    monkeypatch.setattr(rank_snapshot.storage, "read_rank_history", lambda *_: [dict(existing)])

    def save_history(_plugin, rank_key, history):
        saved.update(rank_key=rank_key, history=history)
        return history

    monkeypatch.setattr(rank_snapshot.storage, "save_rank_history", save_history)

    def recognize(_plugin, _rank_key, _item, entry, _rank, _existing):
        entry["title"] = "新标题"
        return SimpleNamespace(tmdb_id=123)

    def preserve(entry, previous):
        entry["tmdbid"] = previous.get("tmdbid")

    history, snapshots = rank_snapshot.merge_rank_items(
        object(),
        "hot",
        [{"title": "RSS 标题", "link": "https://example.test/item"}],
        {"key": "hot", "name": "热门", "route": "/hot"},
        infer_media_type=lambda *_: "movie",
        recognize_item=recognize,
        preserve_existing_identity=preserve,
        return_snapshot=True,
    )

    assert saved["rank_key"] == "hot"
    assert history[0]["title"] == "新标题"
    assert history[0]["tmdbid"] == "123"
    assert history[0]["observing"] is True
    assert history[0]["first_seen"] == "2026-08-01 00:00:00"
    assert history[0]["observe_deleted"] is True
    assert history[0]["observe_deleted_at"] == "2026-08-02 00:00:00"
    assert snapshots[0]["entry"]["rank_order"] == 1


def test_rank_refresh_invalid_limit_falls_back_to_five(monkeypatch):
    """运行周期拉取上限非法时必须回退为仪表盘默认 5 条。"""
    observed = {}
    monkeypatch.setattr(rank_refresh.time, "sleep", lambda *_: None)
    monkeypatch.setattr(rank_refresh.utils, "normalize_rss_domain", lambda value: value.rstrip("/"))

    def build_url(domain, route, limit):
        observed.update(domain=domain, route=route, limit=limit)
        return f"{domain}{route}?limit={limit}"

    monkeypatch.setattr(rank_refresh.rss_adapter, "build_rsshub_url", build_url)

    def merge_items(_plugin, _key, _items, _rank, return_snapshot=False):
        return ([], [{"entry": {"title": "条目"}}]) if return_snapshot else []

    result, snapshots = rank_refresh.refresh_rank_data(
        SimpleNamespace(_rsshub_domain="https://rsshub.test/"),
        ranks=[{"key": "hot", "name": "热门", "route": "/hot", "coming": False}],
        rank_enabled=lambda *_: True,
        fetch_coming=lambda *_: [],
        fetch_general=lambda *_: [{"title": "条目"}],
        merge_items=merge_items,
        dashboard_items=lambda *_args, **_kwargs: [{"title": "条目"}],
        limit_by_rank={"hot": "invalid"},
        with_snapshots=True,
    )

    assert observed == {"domain": "https://rsshub.test", "route": "/hot", "limit": 5}
    assert result["hot"][0]["title"] == "条目"
    assert snapshots["hot"]["items"][0]["entry"]["title"] == "条目"


def test_snapshot_subscription_stops_without_safety_filter():
    """未配置安全筛选时不得进入任何榜单订阅处理器。"""
    calls = []
    rank_subscription.subscribe_rank_snapshots(
        object(),
        {"hot": {"items": [{"entry": {"title": "条目"}}]}},
        ranks=[{"key": "hot", "name": "热门", "coming": False}],
        safety_filter=lambda *_: False,
        rank_enabled_callback=lambda *_: True,
        rank_count_callback=lambda *_: 1,
        rank_config_callback=lambda *_: {},
        blacklist_enabled=lambda *_: False,
        observe_enabled=lambda *_: False,
        process_coming=lambda *_args, **_kwargs: calls.append("coming"),
        process_general=lambda *_args, **_kwargs: calls.append("general"),
        emit_summary=lambda *_: calls.append("summary"),
    )

    assert calls == []


def test_snapshot_subscription_applies_count_limit(monkeypatch):
    """快照订阅只处理榜单配置允许的前 N 个候选。"""
    processed = []
    summaries = []
    monkeypatch.setattr(rank_subscription.time, "sleep", lambda *_: None)

    def process(_plugin, items, _rank, result_lines=None):
        processed.extend(items)
        result_lines.append("- 已处理")

    rank_subscription.subscribe_rank_snapshots(
        object(),
        {"hot": {"items": [{"entry": {"title": "一"}}, {"entry": {"title": "二"}}]}},
        ranks=[{"key": "hot", "name": "热门", "coming": False}],
        safety_filter=lambda *_: True,
        rank_enabled_callback=lambda *_: True,
        rank_count_callback=lambda *_: 1,
        rank_config_callback=lambda *_: {"count": 1},
        blacklist_enabled=lambda *_: False,
        observe_enabled=lambda *_: False,
        process_coming=process,
        process_general=process,
        emit_summary=lambda rank, description, lines: summaries.append((rank, description, lines)),
    )

    assert len(processed) == 1
    assert processed[0]["entry"]["title"] == "一"
    assert "候选 1 条" in summaries[0][1]
    assert summaries[0][2] == ["- 已处理"]


def test_rank_recognition_uses_bangumi_context(monkeypatch):
    """Bangumi 榜单必须把 subject 标题和季号写回 RSS 识别上下文。"""
    mediainfo = SimpleNamespace(title="TMDB 标题")
    monkeypatch.setattr(
        rank_recognition.bangumi_tmdb_service,
        "recognize_bangumi_tmdb",
        lambda *_args, **_kwargs: {
            "mediainfo": mediainfo,
            "title": "中文母剧",
            "season": 2,
        },
    )
    item = {"title": "Original 2nd Season", "bangumi_id": "42"}
    meta, resolved, media_type = rank_recognition.recognize_rss_item(
        SimpleNamespace(chain=object()),
        item,
        {"key": "bangumi"},
        infer_media_type=lambda *_: "tv",
        resolved_media_type=lambda *_: "tv",
        extract_bangumi_id=lambda value: value["bangumi_id"],
        fetch_bangumi_subject=lambda *_: {},
        bangumi_subject_title=lambda *_args, **_kwargs: "中文母剧",
        bangumi_subject_year=lambda *_args, **_kwargs: "2026",
    )

    assert resolved is mediainfo
    assert media_type == "tv"
    assert meta.type == MediaType.TV
    assert meta.begin_season == 2
    assert item["display_title"] == "中文母剧"


def test_rank_recognition_retries_unknown_type_with_tv():
    """旧宿主拒绝省略 mtype 时应使用 TV 兼容回退。"""
    calls = []

    class Chain:
        def recognize_media(self, **kwargs):
            calls.append(kwargs)
            if "mtype" not in kwargs:
                raise TypeError("mtype required")
            return SimpleNamespace(type=MediaType.TV)

    _, mediainfo, media_type = rank_recognition.recognize_rss_item(
        SimpleNamespace(chain=Chain()),
        {"title": "未知类型"},
        {"key": "custom"},
        infer_media_type=lambda *_: "unknown",
        resolved_media_type=lambda *_: "tv",
        extract_bangumi_id=lambda *_: None,
        fetch_bangumi_subject=lambda *_: None,
        bangumi_subject_title=lambda *_args, **_kwargs: "",
        bangumi_subject_year=lambda *_args, **_kwargs: "",
    )

    assert mediainfo is not None
    assert media_type == "tv"
    assert len(calls) == 2
    assert calls[1]["mtype"] == MediaType.TV


def test_rank_recognition_selects_snapshot_handler():
    """快照识别必须按榜单类型选择 Bangumi 或通用处理器。"""
    calls = []

    def apply_bangumi(*_args):
        calls.append("bangumi")
        return "bgm"

    def apply_display(*_args, **kwargs):
        calls.append(("display", kwargs["existing"]))
        return "display"

    common = {
        "apply_bangumi": apply_bangumi,
        "apply_display": apply_display,
        "douban_original_title_fetcher": lambda *_: [],
    }
    assert rank_recognition.recognize_snapshot_item(
        object(), "bangumi", {}, {}, {}, {}, **common
    ) == "bgm"
    assert rank_recognition.recognize_snapshot_item(
        object(), "hot", {}, {}, {}, {"tmdbid": "1"}, **common
    ) == "display"
    assert calls == ["bangumi", ("display", {"tmdbid": "1"})]


def test_subscribe_ranks_unsafe_refreshes_only():
    """传统订阅入口在无安全筛选时只能刷新历史。"""
    calls = []
    rank_subscription.subscribe_ranks(
        object(),
        ranks=[],
        safety_filter=lambda *_: False,
        rank_enabled_callback=lambda *_: True,
        rank_count_callback=lambda *_: 0,
        process_coming=lambda *_: calls.append("coming"),
        process_general=lambda *_: calls.append("general"),
        refresh_rank_data=lambda *_: calls.append("refresh"),
        unlimited_limit=50,
    )

    assert calls == ["refresh"]


def test_refresh_then_subscribe_passes_recognized_snapshots():
    """运行编排必须把同一轮刷新生成的快照交给订阅阶段。"""
    observed = {}

    def refresh(_plugin, *, limit_by_rank, with_snapshots):
        observed.update(limit_by_rank=limit_by_rank, with_snapshots=with_snapshots)
        return {}, {"hot": {"items": [{"entry": {"title": "条目"}}]}}

    def subscribe(_plugin, snapshots):
        observed["snapshots"] = snapshots

    rank_subscription.refresh_then_subscribe(
        object(),
        "运行",
        limit_by_rank=lambda *_: {"hot": 5},
        refresh_rank_data=refresh,
        subscribe_snapshots=subscribe,
    )

    assert observed["limit_by_rank"] == {"hot": 5}
    assert observed["with_snapshots"] is True
    assert observed["snapshots"]["hot"]["items"][0]["entry"]["title"] == "条目"
