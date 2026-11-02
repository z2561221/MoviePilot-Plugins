"""多账号想看读取与基线回归；使用真实响应对象和隔离的内存存储。"""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from app.plugins.doubancenter.adapter.douban_account import (
    DoubanApi,
    DoubanCookieError,
    normalize_wish_user_ids,
)
from app.plugins.doubancenter.service import folio, lifecycle, wish_accounts
from app.schemas.types import MediaSource, MediaType
from requests import Response
from requests.exceptions import ReadTimeout


def make_response(status=200, text=""):
    """真实 requests 响应在 HTTP 错误时为假，不能由普通假响应替代。"""
    response = Response()
    response.status_code = status
    response._content = text.encode("utf-8")
    response.encoding = "utf-8"
    return response


def make_api(cookie_user_id=""):
    """跳过 CookieCloud 与首页请求，仅提供账号读取所需的内存状态。"""
    api = object.__new__(DoubanApi)
    api.headers = {}
    api.cookies = {"dbcl2": f"{cookie_user_id}:test"} if cookie_user_id else {}
    return api


def feed(*subject_ids):
    """生成没有时间过滤歧义的最小公开想看 feed。"""
    items = "".join(
        f"<item><title>想看 条目 {subject_id}</title>"
        f"<link>https://movie.douban.com/subject/{subject_id}/</link></item>"
        for subject_id in subject_ids
    )
    return make_response(text=f"<rss><channel>{items}</channel></rss>")


def wish_page(subject_id):
    """提供带年份和海报的登录账号想看页。"""
    return make_response(text=(
        f'<div class="item"><a href="/subject/{subject_id}/">条目 {subject_id}</a>'
        '<img src="https://example.com/poster.jpg"><li class="intro">2026</li></div>'
    ))


@pytest.fixture
def wish_lab():
    """生产存储接口由内存实现，通知与订阅均不产生真实外部效果。"""
    saved = {}
    plugin = SimpleNamespace(
        _wish_user="alice,bob", _wish_max_pages=1, _wish_days=7,
        _wish_notify=False, _folio_notify=False, _notify=False,
        get_data=lambda key: deepcopy(saved.get(key)),
        save_data=lambda key, value: saved.__setitem__(key, deepcopy(value)),
    )
    return plugin, saved


@pytest.mark.parametrize("route", ["feed", "pages"])
@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
def test_http_errors_keep_the_real_status(route, status):
    """HTTP 错误响应必须进入状态码分支，保留登录错误分类。"""
    api = make_api("123" if route == "pages" else "")
    response = make_response(status)
    assert not response
    expected_error = DoubanCookieError if status in {401, 403} else RuntimeError

    with pytest.raises(expected_error, match=f"HTTP {status}") as error:
        api.get_wish_items(user_id="123", request_get=lambda _: response)

    assert "无响应" not in str(error.value)


@pytest.mark.parametrize("route", ["feed", "pages"])
def test_no_response_is_a_network_error_not_a_cookie_error(route):
    """没有收到响应时保留无响应提示，不能推断 Cookie 失效。"""
    api = make_api("123" if route == "pages" else "")

    with pytest.raises(RuntimeError, match="无响应") as error:
        api.get_wish_items(user_id="123", request_get=lambda _: None)

    assert not isinstance(error.value, DoubanCookieError)


@pytest.mark.parametrize(("raw", "expected"), [
    (" alice,bob ", ["alice", "bob"]),
    ("alice\nbob\r\nalice", ["alice", "bob"]),
    ("alice，bob,, \n alice ", ["alice", "bob"]),
    ("123", ["123"]),
    (" \n,，", []),
])
def test_account_input_is_split_trimmed_and_deduplicated(raw, expected):
    """兼容单账号、自定义账号 ID 以及重复的逗号和换行输入。"""
    assert normalize_wish_user_ids(raw) == expected


@pytest.mark.parametrize("user_id", ["", "123"])
def test_default_or_matching_account_reads_cookie_pages(user_id):
    """留空和显式匹配登录账号均保留登录想看页与分页参数。"""
    calls = []

    def get(url):
        calls.append(url)
        return wish_page("1") if len(calls) == 1 else make_response()

    items = make_api("123").get_wish_items(user_id=user_id, max_pages=2, request_get=get)

    assert [item["subject_id"] for item in items] == ["1"]
    assert all("/people/123/wish?" in url for url in calls)
    assert "start=15" in calls[1]


def test_explicit_other_account_is_not_replaced_by_cookie():
    """填写另一账号时必须读取该账号 feed，不能悄悄同步 Cookie 账号。"""
    calls = []
    items = make_api("123").get_wish_items(
        user_id="456", request_get=lambda url: calls.append(url) or feed("2"),
    )

    assert calls == ["https://www.douban.com/feed/people/456/interests"]
    assert [item["subject_id"] for item in items] == ["2"]


def test_user_id_is_encoded_as_one_path_segment():
    """异常 ID 不能改变 feed URL 的路径或增加查询参数。"""
    calls = []
    make_api().get_wish_items(
        user_id="alice/../bob?x=1", request_get=lambda url: calls.append(url) or feed(),
    )
    assert calls == ["https://www.douban.com/feed/people/alice%2F..%2Fbob%3Fx%3D1/interests"]


def test_missing_cookie_and_account_has_an_explicit_error():
    """缺少两种账号来源时直接提示，不发送一个空账号 URL。"""
    with pytest.raises(DoubanCookieError, match="未配置豆瓣用户 ID"):
        make_api().get_wish_items(request_get=lambda _: pytest.fail("不应发出请求"))


def test_multiple_accounts_baseline_then_enqueue_unique_new_items(wish_lab):
    """首次仅建各账号基线；后续多个账号的同一新增条目只入队一次。"""
    plugin, saved = wish_lab
    plugin._wish_user = " alice, bob\nalice "
    responses = {"alice": feed("1", "2"), "bob": feed("2", "3")}
    calls = []

    def get(url):
        user_id = url.split("/people/", 1)[1].split("/", 1)[0]
        calls.append(user_id)
        return responses[user_id]

    folio.run_wish_sync(plugin, api=make_api(), request_get=get)

    assert calls == ["alice", "bob"]
    assert saved["folio_wish_queue"] == []
    assert {item["subject_id"] for item in saved["folio_wish_seen"]} == {"1", "2", "3"}
    assert all(account["initialized"] for account in saved["folio_wish_state"]["accounts"].values())

    responses.update(alice=feed("1", "2", "4"), bob=feed("2", "3", "4", "5"))
    folio.run_wish_sync(plugin, api=make_api(), request_get=get)
    folio.run_wish_sync(plugin, api=make_api(), request_get=get)

    assert [item["subject_id"] for item in saved["folio_wish_queue"]] == ["4", "5"]
    assert len(saved["folio_wish_seen"]) == 5


def test_partial_failure_keeps_healthy_updates_and_recovery_baselines(wish_lab):
    """失败账号恢复时先建基线，健康账号的新增条目仍能及时入队。"""
    plugin, saved = wish_lab
    plugin._wish_user = "bob,alice"
    saved["folio_wish_state"] = {
        "initialized": True, "baseline_at": "old",
        "accounts": {"alice": {"initialized": True, "baseline_at": "old"}},
    }
    saved["folio_wish_seen"] = [{"subject_id": "1", "title": "已见"}]
    responses = {"alice": feed("1", "2"), "bob": make_response(404)}

    def get(url):
        return responses[url.split("/people/", 1)[1].split("/", 1)[0]]

    folio.run_wish_sync(plugin, api=make_api(), request_get=get)

    assert [item["subject_id"] for item in saved["folio_wish_queue"]] == ["2"]
    assert "bob" in saved["folio_wish_state"]["last_error"]
    assert "HTTP 404" in saved["folio_wish_state"]["last_error"]
    assert not saved["folio_wish_state"]["accounts"]["bob"].get("initialized")

    responses["bob"] = feed("3")
    folio.run_wish_sync(plugin, api=make_api(), request_get=get)

    assert [item["subject_id"] for item in saved["folio_wish_queue"]] == ["2"]
    assert saved["folio_wish_state"]["last_error"] == ""
    assert saved["folio_wish_state"]["accounts"]["bob"]["initialized"]
    assert saved["folio_wish_state"]["accounts"]["alice"]["baseline_at"] == "old"

    responses["bob"] = feed("3", "4")
    folio.run_wish_sync(plugin, api=make_api(), request_get=get)
    assert [item["subject_id"] for item in saved["folio_wish_queue"]] == ["2", "4"]


def test_new_account_baseline_cannot_swallow_another_accounts_new_item(wish_lab):
    """新账号先返回同一作品，也不能抹掉已初始化账号发现的新增。"""
    plugin, saved = wish_lab
    plugin._wish_user = "bob,alice"
    saved["folio_wish_state"] = {"accounts": {"alice": {"initialized": True}}}

    folio.run_wish_sync(plugin, api=make_api(), request_get=lambda _: feed("7"))

    assert [item["subject_id"] for item in saved["folio_wish_queue"]] == ["7"]
    assert [item["subject_id"] for item in saved["folio_wish_seen"]] == ["7"]


def test_one_account_timeout_does_not_block_other_accounts_baseline(wish_lab):
    """真实 requests 超时异常也按账号隔离，成功账号仍可建立首次基线。"""
    plugin, saved = wish_lab

    def get(url):
        if "/alice/" in url:
            raise ReadTimeout("请求超时")
        return feed("1")

    folio.run_wish_sync(plugin, api=make_api(), request_get=get)

    assert saved["folio_wish_state"]["accounts"]["bob"]["initialized"]
    assert "alice" in saved["folio_wish_state"]["last_error"]
    assert "请求超时" in saved["folio_wish_state"]["last_error"]
    assert saved["folio_wish_queue"] == []


def test_all_accounts_failed_preserves_all_existing_work(wish_lab):
    """所有读取都失败时只更新故障状态，不清空队列、基线或失败记录。"""
    plugin, saved = wish_lab
    protected = {
        "folio_wish_seen": [{"subject_id": "1", "title": "已见"}],
        "folio_wish_queue": [{"subject_id": "2", "title": "待处理", "retry": 2}],
        "folio_wish_processed": [{"subject_id": "3"}],
        "folio_wish_failed": [{"subject_id": "4", "reason": "recognize_failed", "retry": 1}],
    }
    saved.update(deepcopy(protected))
    saved["folio_wish_state"] = {"initialized": True, "baseline_at": "old", "extra": "keep"}

    folio.run_wish_sync(
        plugin, api=make_api(),
        request_get=lambda url: None if "/alice/" in url else make_response(500),
    )

    assert {key: saved[key] for key in protected} == protected
    assert "alice" in saved["folio_wish_state"]["last_error"]
    assert "无响应" in saved["folio_wish_state"]["last_error"]
    assert "bob" in saved["folio_wish_state"]["last_error"]
    assert "HTTP 500" in saved["folio_wish_state"]["last_error"]
    assert saved["folio_wish_state"]["extra"] == "keep"
    assert saved["folio_wish_state"]["baseline_at"] == "old"


def test_legacy_single_account_keeps_its_baseline_and_retry_queue(wish_lab):
    """升级单账号已有状态后仍处理新增，且已在队列中的重试条目不变。"""
    plugin, saved = wish_lab
    plugin._wish_user = "alice"
    saved["folio_wish_state"] = {"initialized": True, "baseline_at": "old", "extra": "keep"}
    saved["folio_wish_seen"] = [{"subject_id": "1", "title": "已见"}]
    saved["folio_wish_queue"] = [{"subject_id": "9", "title": "重试", "retry": 2}]

    folio.run_wish_sync(plugin, api=make_api(), request_get=lambda _: feed("1", "2"))

    assert saved["folio_wish_queue"][0] == {"subject_id": "9", "title": "重试", "retry": 2}
    assert [item["subject_id"] for item in saved["folio_wish_queue"]] == ["9", "2"]
    assert saved["folio_wish_state"]["accounts"]["alice"]["baseline_at"] == "old"
    assert saved["folio_wish_state"]["extra"] == "keep"


def test_legacy_cookie_baseline_is_not_assigned_to_new_configured_account(wish_lab):
    """旧代码实际读取的 Cookie 账号与新指定账号的首次基线分别承接。"""
    plugin, saved = wish_lab
    plugin._wish_user = "456"
    saved["folio_wish_state"] = {"initialized": True, "baseline_at": "old"}
    calls = []

    folio.run_wish_sync(
        plugin, api=make_api("123"),
        request_get=lambda url: calls.append(url) or feed("2"),
    )

    assert calls == ["https://www.douban.com/feed/people/456/interests"]
    assert saved["folio_wish_queue"] == []
    assert saved["folio_wish_state"]["accounts"]["123"]["baseline_at"] == "old"
    assert saved["folio_wish_state"]["accounts"]["456"]["initialized"]


def test_unknown_legacy_multi_account_history_is_preserved_without_bulk_queueing(wish_lab):
    """旧全局状态无法归属账号时保留历史，并安全建立各账号首次基线。"""
    plugin, saved = wish_lab
    saved["folio_wish_state"] = {"initialized": True, "baseline_at": "old"}
    saved["folio_wish_seen"] = [{"subject_id": "9", "title": "历史"}]

    folio.run_wish_sync(plugin, api=make_api(), request_get=lambda _: feed("1"))

    assert saved["folio_wish_queue"] == []
    assert {item["subject_id"] for item in saved["folio_wish_seen"]} == {"9", "1"}


def test_queue_processing_does_not_clear_account_read_failure(wish_lab):
    """旧队列成功处理后仍保留本轮读取错误，下次读取成功才清除。"""
    plugin, saved = wish_lab
    plugin._wish_user = "alice"
    saved["folio_wish_state"] = {"initialized": True}
    saved["folio_wish_queue"] = [{"subject_id": "9", "title": "旧队列", "year": "2026"}]
    folio.run_wish_sync(plugin, api=make_api(), request_get=lambda _: make_response(404))
    read_error = saved["folio_wish_state"]["last_error"]
    media = SimpleNamespace(
        title="旧队列", year="2026", type=MediaType.MOVIE,
        media_source=MediaSource.TMDB, media_id="9", tmdb_id=9,
    )

    folio.process_wish_queue(plugin, recognize=lambda *_: media, subscribe=lambda *a, **kw: True)

    assert saved["folio_wish_queue"] == []
    assert saved["folio_wish_state"]["last_error"] == read_error
    assert "HTTP 404" in read_error

    folio.run_wish_sync(plugin, api=make_api(), request_get=lambda _: feed())
    assert saved["folio_wish_state"]["last_error"] == ""


def test_merged_items_keep_richer_fields_from_cookie_pages(wish_lab):
    """同一作品由多个账号返回时只保留一条，并补齐想看页提供的字段。"""
    plugin, _ = wish_lab
    plugin._wish_user = "alice,123"
    state = {"accounts": {"alice": {"initialized": True}, "123": {"initialized": True}}}

    batch = wish_accounts.read_wish_accounts(
        plugin, make_api("123"), state, max_pages=1, days=7, now="now",
        request_get=lambda url: wish_page("1") if "/123/wish?" in url else feed("1"),
    )

    assert len(batch.items) == 1
    assert batch.items[0]["year"] == "2026"
    assert batch.items[0]["poster"] == "https://example.com/poster.jpg"
    assert batch.succeeded == 2


@pytest.mark.parametrize("restart", [False, True])
def test_stop_during_first_read_prevents_second_account_and_any_storage_write(wish_lab, restart):
    """停止或重载期间的旧多账号任务不能继续请求或覆盖新运行代次的数据。"""
    plugin, saved = wish_lab
    lifecycle.start(plugin)
    calls = []

    def get(url):
        calls.append(url)
        lifecycle.stop(plugin)
        if restart:
            lifecycle.start(plugin)
        return feed("1")

    with lifecycle.scope(plugin), pytest.raises(lifecycle.RunStopped):
        folio.run_wish_sync(plugin, api=make_api(), request_get=get)

    assert len(calls) == 1
    assert saved == {}
