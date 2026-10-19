"""想看调度独立启停；真实插件入口配合隔离的迁移、存储和执行回调。"""

from types import SimpleNamespace

import pytest
from apscheduler.triggers.cron import CronTrigger
from app.plugins.doubancenter import DoubanCenter, feed, folio, migration
from app.plugins.doubancenter.service import lifecycle, scheduler, webhook


@pytest.fixture
def scheduler_lab(monkeypatch):
    """保留初始化和代次绑定行为，但不运行网络、数据库或真实订阅。"""
    events = []
    plugin = object.__new__(DoubanCenter)
    plugin._scheduler = None
    plugin.update_config = lambda config: None
    monkeypatch.setattr(migration, "migrate_plugin_media_identity", lambda *a, **kw: None)
    monkeypatch.setattr(migration, "normalize_legacy_subscribe_usernames", lambda: None)
    monkeypatch.setattr(feed, "run_scheduled", lambda current: events.append("rank"))
    monkeypatch.setattr(folio, "run_wish_scheduled", lambda current: events.append("wish"))
    config = {
        "enabled": True,
        "folio_enabled": False,
        "wish_enabled": True,
        "cron": "0 3 * * *",
        "wish_cron": "5 * * * *",
    }
    plugin.init_plugin(config)
    return SimpleNamespace(plugin=plugin, events=events, config=config)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("folio_enabled", [False, True])
@pytest.mark.parametrize("wish_enabled", [False, True])
def test_wish_registration_uses_its_own_switch(
    scheduler_lab, enabled, folio_enabled, wish_enabled,
):
    """豆瓣时间开关不参与想看注册，总开关和想看开关仍然有效。"""
    plugin = scheduler_lab.plugin
    plugin.init_plugin({
        **scheduler_lab.config,
        "enabled": enabled,
        "folio_enabled": folio_enabled,
        "wish_enabled": wish_enabled,
    })

    ids = [service["id"] for service in plugin.get_service()]

    assert ("DoubanCenterWish" in ids) is (enabled and wish_enabled)
    assert ("DoubanCenter" in ids) is enabled
    assert len(ids) == len(set(ids))
    assert scheduler_lab.events == []


def test_wish_uses_independent_timer_and_callback(scheduler_lab):
    """榜单周期为空、豆瓣时间关闭时，想看仍按自己的周期和回调运行。"""
    plugin = scheduler_lab.plugin
    plugin._cron = ""
    services = plugin.get_service()

    assert [service["id"] for service in services] == ["DoubanCenterWish"]
    assert str(services[0]["trigger"]) == str(CronTrigger.from_crontab(plugin._wish_cron))
    services[0]["func"](**services[0]["kwargs"])
    assert scheduler_lab.events == ["wish"]


@pytest.mark.parametrize("missing", ["cron", "callback"])
def test_wish_requires_a_timer_and_callback(scheduler_lab, missing):
    """解除豆瓣时间耦合不放宽缺少周期或执行回调时的注册限制。"""
    plugin = scheduler_lab.plugin
    if missing == "cron":
        plugin._wish_cron = ""
    callback = None if missing == "callback" else lambda: None

    services = scheduler.get_services(plugin, lambda: None, callback)

    assert [service["id"] for service in services] == ["DoubanCenter"]


def test_reload_disable_and_stop_invalidate_old_wish_callbacks(scheduler_lab):
    """重载只保留当前代次，停用想看和停止插件后旧回调不能继续执行。"""
    plugin = scheduler_lab.plugin

    def wish_job():
        jobs = [service for service in plugin.get_service() if service["id"] == "DoubanCenterWish"]
        assert len(jobs) == 1
        return jobs[0]["func"]

    old_callback = wish_job()
    plugin.init_plugin(scheduler_lab.config)
    current_callback = wish_job()
    old_callback()
    assert scheduler_lab.events == []
    current_callback()
    assert scheduler_lab.events == ["wish"]

    plugin.init_plugin({**scheduler_lab.config, "wish_enabled": False})
    assert [service["id"] for service in plugin.get_service()] == ["DoubanCenter"]
    current_callback()
    assert scheduler_lab.events == ["wish"]

    plugin.init_plugin(scheduler_lab.config)
    stopped_callback = wish_job()
    plugin.stop_service()
    stopped_callback()
    assert scheduler_lab.events == ["wish"]


@pytest.mark.parametrize("played", [False, True])
def test_wish_only_does_not_enable_viewing_sync(scheduler_lab, monkeypatch, played):
    """只开想看时，播放和已看事件仍被豆瓣时间开关拦截。"""
    def unexpected(*args, **kwargs):
        pytest.fail("viewing sync must remain disabled")

    monkeypatch.setattr(webhook.folio, "check_cookie_periodically", unexpected)
    monkeypatch.setattr(webhook.folio, "sync_log_handler", unexpected)
    event = SimpleNamespace(event_data=object())

    webhook.handle_sync_log(scheduler_lab.plugin, event, played=played)
    webhook.handle_sync_played(scheduler_lab.plugin, event, sync_log=unexpected)
    lifecycle.checkpoint(scheduler_lab.plugin)
