"""观察通知与按钮的无外部副作用回归。"""

import copy
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from types import SimpleNamespace

import pytest
from app.schemas.types import MediaSource, MediaType, MessageType, NotificationChannel

from app.plugins.doubancenter.adapter import notification as adapter
from app.plugins.doubancenter.model.config import default_config
from app.plugins.doubancenter.service import dashboard, lifecycle, observation, rank_pipeline
from app.plugins.doubancenter.service import observation_actions as actions
from app.plugins.doubancenter.service import rank_notifications as notices
from app.plugins.doubancenter.storage import records as storage

RANK = {"key": "coming", "name": "即将上映", "coming": True}
ROUTE = {"id": "route-1", "name": "telegram-main", "type": "telegram"}


class NoticePlugin:
    def __init__(self):
        self._enabled = self._notify = True
        self._notification_type = "Plugin"
        self._observe_days = 3
        self._observe_rank_keys = ["coming", "tv_global"]
        self._custom_ranks = []
        self._rank_lock = threading.RLock()
        self.data, self.messages, self.edits, self.writes = {}, [], [], []
        self.chain = SimpleNamespace(run_module=self.edit_message)
        lifecycle.start(self)

    def get_data(self, key, **_kwargs):
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key, value):
        self.writes.append(key)
        self.data[key] = copy.deepcopy(value)

    def post_message(self, **message):
        self.messages.append(message)

    def edit_message(self, name, **message):
        assert name == "edit_message"
        self.edits.append(message)
        return True


@pytest.fixture
def plugin(monkeypatch):
    instance = NoticePlugin()
    monkeypatch.setattr(adapter, "destinations", lambda _mtype: [dict(ROUTE)])
    monkeypatch.setattr(adapter, "telegram_userid", lambda: "123456")
    monkeypatch.setattr(adapter, "detail_link", lambda _plugin: "https://mp.test/#/plugins?id=NoticePlugin")
    return instance


def create_observation(plugin, *, season=2, unique="dc2_coming:https://example.test/42", rank=RANK):
    history = storage.read_rank_history(plugin, rank["key"])
    assert observation.check_observe(plugin, unique, history, title="同名剧集", rank_key=rank["key"])
    item = next(item for item in history if item["unique"] == unique)
    item.update(media_source=MediaSource.TMDB.value, media_id="42", media_type="tv", year="2026",
                season=season, rank_name=rank["name"], link="https://example.test/42")
    storage.save_rank_history(plugin, rank["key"], history)
    return item


def send_notice(plugin, **kwargs):
    item = create_observation(plugin, **kwargs)
    notices.send_pending(plugin, kwargs.get("rank", RANK))
    return item


def callback(plugin, action="s", **changes):
    button = next(message["buttons"][0][0] for message in reversed(plugin.messages) if message.get("buttons"))
    text = button["callback_data"].split("|", 1)[1][:-1] + action
    data = {"plugin_id": plugin.__class__.__name__, "channel": NotificationChannel.Telegram,
            "source": ROUTE["name"], "userid": "123456", "text": text,
            "original_message_id": 99, "original_chat_id": "-1005678"}
    data.update(changes)
    return SimpleNamespace(event_data=data)


def session_for(plugin, event):
    token = event.event_data["text"].split(":")[1]
    return plugin.data[actions.SESSIONS_KEY][token]


def test_notification_defaults_and_dynamic_host_types():
    assert default_config()["notify"] is False
    assert default_config()["notification_type"] == "Plugin"
    assert notices.normalize_notification_type("invalid") == "Plugin"
    assert notices.normalize_notification_type("Subscribe") == "Subscribe"
    assert notices.notification_type_options() == [{"title": item.value, "value": item.name} for item in MessageType]


def test_first_entry_sends_once_after_storage_and_reentry_has_new_cycle(plugin):
    item = create_observation(plugin)
    assert plugin.messages == []
    notices.send_pending(plugin, RANK)
    first_cycle = item["observation_notice"]["cycle"]
    assert len(plugin.messages) == 1
    message = plugin.messages[0]
    assert message["mtype"] is MessageType.Plugin and message["parse_mode"] == "plain"
    assert "尚未订阅" in message["text"] and "第 2 季" in message["text"] and "预计到期" in message["text"]
    assert message["userid"] == "123456" and message["source"] == ROUTE["name"]
    assert all(len(button["callback_data"].encode()) <= 64 for button in message["buttons"][0])
    create_observation(plugin)
    notices.send_pending(plugin, RANK)
    assert len(plugin.messages) == 1
    history = storage.read_rank_history(plugin, RANK["key"])
    history[0].update(observing=False, observe_dropped_at="2026-01-01 00:00:00")
    storage.save_rank_history(plugin, RANK["key"], history)
    next_item = create_observation(plugin)
    notices.send_pending(plugin, RANK)
    assert len(plugin.messages) == 2
    assert next_item["observation_notice"]["cycle"] != first_cycle


@pytest.mark.parametrize("legacy", [False, True])
def test_disabled_or_legacy_observation_never_backfills(plugin, legacy):
    plugin._notify = False
    create_observation(plugin)
    if legacy:
        plugin.data["coming_history"][0].pop("observation_notice", None)
    plugin._notify = True
    create_observation(plugin)
    notices.send_pending(plugin, RANK)
    assert plugin.messages == []


def test_snapshot_existing_row_first_observation_still_notifies(plugin):
    plugin.data["coming_history"] = [{"unique": "dc2_coming:https://example.test/42", "title": "同名剧集",
                                      "time": "2099-01-01 00:00:00", "rank_key": "coming"}]
    send_notice(plugin)
    assert len(plugin.messages) == 1


def test_channels_are_split_without_duplicate_telegram_and_respect_type(plugin, monkeypatch):
    plugin._notification_type = "Subscribe"
    calls = []
    def destinations(mtype):
        calls.append(mtype)
        return [ROUTE, {"id": "web-1", "name": "web", "type": "webpush"}]
    monkeypatch.setattr(adapter, "destinations", destinations)
    send_notice(plugin)
    assert calls == [MessageType.Subscribe]
    assert len(plugin.messages) == 2
    web = plugin.messages[1]
    assert web["source"] == "web" and "userid" not in web and "buttons" not in web
    assert "token=" not in web["link"] and "apikey" not in web["link"]


@pytest.mark.parametrize("mode", ["unbound", "long_instance", "no_identity", "no_source_id"])
def test_unavailable_interaction_falls_back_to_plain_notice(plugin, monkeypatch, mode):
    if mode == "unbound":
        monkeypatch.setattr(adapter, "telegram_userid", lambda: "")
    if mode == "long_instance":
        plugin.__class__ = type("NoticePlugin" + "X" * 70, (NoticePlugin,), {})
    if mode == "no_source_id":
        monkeypatch.setattr(adapter, "destinations", lambda _mtype: [{**ROUTE, "id": ""}])
    create_observation(plugin)
    if mode == "no_identity":
        plugin.data["coming_history"][0]["media_id"] = ""
        plugin.data["coming_history"][0].pop("tmdbid", None)
    notices.send_pending(plugin, RANK)
    assert len(plugin.messages) == 1
    assert "buttons" not in plugin.messages[0] and "userid" not in plugin.messages[0]


def test_notification_failure_is_claimed_once_and_does_not_stop_rank(plugin, monkeypatch):
    calls = []
    def fail(**message):
        calls.append(message)
        raise RuntimeError("transport failed")
    monkeypatch.setattr(plugin, "post_message", fail)
    create_observation(plugin)
    notices.send_pending(plugin, RANK)
    notices.send_pending(plugin, RANK)
    assert len(calls) == 1
    assert plugin.data["coming_history"][0]["observation_notice"]["state"] == "failed"


@pytest.mark.parametrize("field,value", [
    ("plugin_id", "OtherClone"), ("channel", "微信"), ("userid", "777"), ("source", "other-source"),
    ("text", "dco:bad:s"), ("text", "dco:abcdefghijklmnop:x"), ("original_message_id", ""),
    ("original_chat_id", ""),
])
def test_invalid_or_foreign_callback_never_writes_or_replies(plugin, monkeypatch, field, value):
    send_notice(plugin)
    before = copy.deepcopy(plugin.data)
    monkeypatch.setattr(actions, "_execute", lambda *_: pytest.fail("must not execute"))
    event = callback(plugin, **{field: value})
    assert actions.handle_callback(plugin, event) is False
    assert plugin.data == before and plugin.edits == [] and len(plugin.messages) == 1


@pytest.mark.parametrize("changed", ["actor", "source_id", "expired", "season", "identity", "cycle", "deleted", "subscribed", "dropped", "disabled"])
def test_old_cards_cannot_act_on_changed_state(plugin, monkeypatch, changed):
    send_notice(plugin)
    event = callback(plugin)
    row = plugin.data["coming_history"][0]
    if changed == "actor":
        monkeypatch.setattr(adapter, "telegram_userid", lambda: "987")
    elif changed == "source_id":
        monkeypatch.setattr(adapter, "destinations", lambda _mtype: [{**ROUTE, "id": "new"}])
    elif changed == "expired":
        session_for(plugin, event)["expires_at"] = 0
    elif changed == "season":
        row["season"] = 3
    elif changed == "identity":
        row["media_id"] = "99"
    elif changed == "cycle":
        row["observation_notice"]["cycle"] = "next-cycle"
    elif changed == "disabled":
        plugin._enabled = False
    else:
        row[{"deleted": "observe_deleted", "subscribed": "subscribed", "dropped": "observe_dropped_at"}[changed]] = True
    before = copy.deepcopy(plugin.data)
    monkeypatch.setattr(actions, "_execute", lambda *_: pytest.fail("old card executed"))
    actions.handle_callback(plugin, event)
    assert plugin.data == before
    if changed not in ("actor", "source_id"):
        assert plugin.edits[-1]["buttons"] is None


@pytest.mark.parametrize("season,status", [(0, "success"), (2, "success"), (2, "existing")])
def test_subscribe_reuses_safe_chain_and_closes_only_exact_observation(plugin, monkeypatch, season, status):
    send_notice(plugin, season=season)
    other = copy.deepcopy(plugin.data["coming_history"][0])
    other.update(unique="other-season", season=season + 1)
    plugin.data["coming_history"].append(other)
    received = []
    def subscribe(_plugin, **kwargs):
        received.append(kwargs)
        return {"success": status == "success", "status": status, "message": "done"}
    monkeypatch.setattr(dashboard, "api_subscribe_from_rank", subscribe)
    event = callback(plugin)
    assert actions.handle_callback(plugin, event)
    assert received[0]["season"] == season and received[0]["with_result"] is True
    assert received[0]["media_source"] == MediaSource.TMDB.value and received[0]["media_id"] == "42"
    first, second = plugin.data["coming_history"]
    assert first["observing"] is False and second["observing"] is True
    assert first.get("existing") is True if status == "existing" else first.get("subscribed") is True
    assert session_for(plugin, event)["state"] == "done"
    actions.handle_callback(plugin, event)
    assert len(received) == 1
    assert plugin.edits[-1]["buttons"] is None and len(plugin.messages) == 1
    assert plugin.edits[-1]["chat_id"] == "-1005678" and plugin.edits[-1]["message_id"] == 99


def test_remove_archives_only_target_and_is_idempotent(plugin):
    send_notice(plugin)
    event = callback(plugin, "r")
    assert actions.handle_callback(plugin, event)
    assert plugin.data["coming_history"][0]["observe_deleted"] is True
    assert plugin.data["coming_history"][0]["observing"] is False
    assert len(plugin.data["archive_records"]) == 1
    actions.handle_callback(plugin, event)
    assert len(plugin.data["archive_records"]) == 1
    assert "subscribe_records" not in plugin.data


def test_business_failure_keeps_original_buttons_but_uncertain_exception_never_retries(plugin, monkeypatch):
    send_notice(plugin)
    event = callback(plugin)
    monkeypatch.setattr(actions, "_execute", lambda *_: {"success": False, "message": "状态未知，未提交"})
    actions.handle_callback(plugin, event)
    assert session_for(plugin, event)["state"] == "open"
    assert plugin.edits[-1]["buttons"] and plugin.data["coming_history"][0]["observing"]
    attempts = []
    def uncertain(*_args):
        attempts.append(1)
        raise RuntimeError("failed after external write")
    monkeypatch.setattr(actions, "_execute", uncertain)
    actions.handle_callback(plugin, event)
    actions.handle_callback(plugin, event)
    assert attempts == [1] and session_for(plugin, event)["state"] == "uncertain"
    assert plugin.edits[-1]["buttons"] is None


def test_edit_failure_posts_noninteractive_receipt_without_new_token(plugin, monkeypatch):
    send_notice(plugin)
    event = callback(plugin, "r")
    monkeypatch.setattr(plugin.chain, "run_module", lambda *_args, **_kwargs: False)
    actions.handle_callback(plugin, event)
    assert len(plugin.messages) == 2 and plugin.messages[-1]["buttons"] is None
    assert session_for(plugin, event)["state"] == "done" and len(plugin.data[actions.SESSIONS_KEY]) == 1


def test_lifecycle_stop_during_action_keeps_claim_and_prevents_replay(plugin, monkeypatch):
    send_notice(plugin)
    event = callback(plugin)
    calls = []
    def stop(*_args):
        calls.append(1)
        lifecycle.stop(plugin)
        return {"success": True}
    monkeypatch.setattr(actions, "_execute", stop)
    actions.handle_callback(plugin, event)
    assert session_for(plugin, event)["state"] == "processing" and plugin.edits == []
    lifecycle.start(plugin)
    actions.handle_callback(plugin, event)
    assert calls == [1]


def pipeline_input(plugin, monkeypatch, name):
    rank = RANK if "coming" in name else {"key": "tv_global", "name": "全球口碑", "coming": False}
    raw = {"title": "测试 第二季", "link": "https://example.test/42", "year": "2026", "media_type": "tv"}
    meta = SimpleNamespace(begin_season=2)
    media = SimpleNamespace(media_source=MediaSource.TMDB, media_id="42", tmdb_id=42, title="测试", year="2026", type=MediaType.TV)
    monkeypatch.setattr(rank_pipeline, "_rc", lambda *_: {})
    monkeypatch.setattr(rank_pipeline, "_check_blacklist", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(rank_pipeline, "_check_rank_region", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(rank_pipeline, "_is_existing_media", lambda *_: False)
    monkeypatch.setattr(rank_pipeline, "_snapshot_meta", lambda *_: meta)
    monkeypatch.setattr(rank_pipeline, "_fetch_coming_rss", lambda *_: [dict(raw)])
    monkeypatch.setattr(rank_pipeline, "_fetch_rss", lambda *_: [dict(raw)])
    monkeypatch.setattr(rank_pipeline, "_recognize_rss_item", lambda *_: (meta, media, "tv"))
    monkeypatch.setattr(rank_pipeline.utils, "get_tmdb_air_date", lambda *_args, **_kwargs: "2026-12-01")
    monkeypatch.setattr(rank_pipeline.rank_timing, "resolve_release", lambda *_args, **_kwargs: ("2026", "2026-12-01"))
    monkeypatch.setattr(rank_pipeline, "_add_sub", lambda *_args, **_kwargs: pytest.fail("observed item must not subscribe"))
    plugin.chain.recognize_media = lambda **_kwargs: media
    argument = [{"raw": raw, "entry": dict(raw), "mediainfo": media}] if name.endswith("snapshots") else "https://rss.test/feed"
    return rank, argument


@pytest.mark.parametrize("name", ["_process_coming_snapshots", "_process_general_snapshots", "_process_coming", "_process_general"])
def test_all_four_paths_notify_after_save_and_respect_removed_without_observation(plugin, monkeypatch, name):
    rank, argument = pipeline_input(plugin, monkeypatch, name)
    processor = getattr(rank_pipeline, name)
    processor(plugin, argument, rank)
    processor(plugin, argument, rank)
    assert len(plugin.messages) == 1 and "第 2 季" in plugin.messages[0]["text"]
    row = plugin.data[storage.rank_history_key(rank["key"])][0]
    row.update(observe_deleted=True, observing=False)
    plugin._observe_days = 0
    processor(plugin, argument, rank)
    assert row["observe_deleted"] is True and len(plugin.messages) == 1


def test_failed_rank_save_never_sends_notification(plugin, monkeypatch):
    rank, argument = pipeline_input(plugin, monkeypatch, "_process_coming_snapshots")
    original = plugin.save_data
    def fail(key, value):
        if key == "coming_history":
            raise RuntimeError("storage unavailable")
        original(key, value)
    monkeypatch.setattr(plugin, "save_data", fail)
    with pytest.raises(RuntimeError, match="storage unavailable"):
        rank_pipeline._process_coming_snapshots(plugin, argument, rank)
    assert plugin.messages == []


@pytest.mark.parametrize("name", ["_process_coming_snapshots", "_process_general_snapshots", "_process_coming", "_process_general"])
def test_refresh_serializes_remove_and_busy_callback_does_not_consume_card(plugin, monkeypatch, name):
    rank, argument = pipeline_input(plugin, monkeypatch, name)
    send_notice(plugin, rank=rank, unique=("dc2_coming:" if rank["coming"] else "dc2_rank:") + "https://example.test/42")
    event = callback(plugin, "r")
    entered, release, removing = threading.Event(), threading.Event(), threading.Event()
    original = rank_pipeline._check_observe

    def pause(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)

    def remove():
        removing.set()
        return dashboard.api_delete_observation(plugin, unique=session_for(plugin, event)["unique"], rank_key=rank["key"])

    monkeypatch.setattr(rank_pipeline, "_check_observe", pause)
    with ThreadPoolExecutor(max_workers=2) as pool:
        refresh = pool.submit(getattr(rank_pipeline, name), plugin, argument, rank)
        try:
            assert entered.wait(3)
            assert actions.handle_callback(plugin, event)
            assert session_for(plugin, event)["state"] == "open" and not plugin.edits
            assert plugin.messages[-1]["buttons"] is None
            deletion = pool.submit(remove)
            assert removing.wait(3)
            with pytest.raises(FutureTimeout):
                deletion.result(timeout=0.05)
        finally:
            release.set()
        refresh.result(timeout=3)
        assert deletion.result(timeout=3)["success"] is True
    row = storage.read_rank_history(plugin, rank["key"])[0]
    assert row["observe_deleted"] is True and row["observing"] is False


def test_notice_claim_storage_failure_never_reaches_transport(plugin, monkeypatch):
    create_observation(plugin)
    original = plugin.save_data

    def fail_claim(key, value):
        if key == "coming_history" and value[0]["observation_notice"]["attempted"]:
            raise RuntimeError("claim not persisted")
        original(key, value)

    monkeypatch.setattr(plugin, "save_data", fail_claim)
    notices.send_pending(plugin, RANK)
    assert not plugin.messages
    assert not plugin.data["coming_history"][0]["observation_notice"]["attempted"]


def test_route_filter_uses_enabled_and_current_category(monkeypatch):
    from app.sdk.services import ServiceConfigHelper

    def route(name, *, enabled=True, switchs=None):
        return SimpleNamespace(id=name, name=name, type="Telegram", enabled=enabled,
                               switchs=[MessageType.Subscribe.value] if switchs is None else switchs)

    monkeypatch.setattr(ServiceConfigHelper, "get_notification_configs", lambda: [
        route("allowed"), route("disabled", enabled=False), route("other", switchs=[MessageType.Plugin.value]),
        route("empty", switchs=[]),
    ])
    assert adapter.destinations(MessageType.Subscribe) == [{"id": "allowed", "name": "allowed", "type": "telegram"}]


@pytest.mark.parametrize("active,admin,userid,expected", [
    (True, True, "123456", "123456"), (False, True, "123456", ""), (True, False, "123456", ""),
    (True, True, "-1005678", ""), (True, True, "", ""), (True, True, "not-an-id", ""),
])
def test_actor_lookup_requires_active_superuser_personal_binding(monkeypatch, active, admin, userid, expected):
    from app.db.oper.user import UserOper

    user = SimpleNamespace(is_active=active, is_superuser=admin, settings={"telegram_userid": userid})
    monkeypatch.setattr(UserOper, "get_by_name", lambda *_args, **_kwargs: user)
    assert adapter.telegram_userid() == expected
