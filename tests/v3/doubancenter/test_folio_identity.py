"""豆瓣中心 V3 追影时间线媒体身份回归测试。"""

from types import SimpleNamespace

from app.schemas.types import MediaSource, MediaType

from doubancenter import folio


class FakeDoubanApi:
    """模拟豆瓣标题搜索和观看状态写入。"""

    search_result = (None, None)
    status_result = True
    search_calls = []
    status_calls = []

    def __init__(self, user_cookie=None):
        """保留 Cookie 参数但不访问网络。"""
        self.user_cookie = user_cookie

    @classmethod
    def reset(cls):
        """重置所有调用记录。"""
        cls.search_result = (None, None)
        cls.status_result = True
        cls.search_calls = []
        cls.status_calls = []

    def get_subject_id(self, title=None, meta=None):
        """返回预设豆瓣搜索结果。"""
        self.search_calls.append(title or getattr(meta, "title", ""))
        return self.search_result

    def set_watching_status(self, subject_id, status="do", private=True):
        """记录观看状态并模拟成功。"""
        self.status_calls.append((str(subject_id), status, private))
        return self.status_result


class FakeMediaChain:
    """模拟 V3 跨源身份转换。"""

    def __init__(self, converted=None):
        """保存预设转换结果。"""
        self.converted = converted
        self.convert_calls = []

    def convert_media_identity(self, **kwargs):
        """记录转换参数并返回预设豆瓣详情。"""
        self.convert_calls.append(kwargs)
        return self.converted


class SeasonFallbackMediaChain(FakeMediaChain):
    """模拟分季转换失败但整剧身份可转换的媒体链。"""

    def convert_media_identity(self, **kwargs):
        """仅在不限定季号时返回死神整剧豆瓣身份。"""
        self.convert_calls.append(dict(kwargs))
        if kwargs.get("season") is not None:
            return None
        return self.converted


class SearchMediaChain(FakeMediaChain):
    """模拟标题候选搜索。"""

    def __init__(self, candidates):
        """保存候选媒体。"""
        super().__init__()
        self.candidates = candidates

    def search_medias(self, meta, media_source=None):
        """返回预设标题候选。"""
        return self.candidates


def _plugin(wait=None):
    """构造具备豆瓣时间持久化能力的最小插件对象。"""
    saved = {}
    plugin = SimpleNamespace(
        _folio_cookie="cookie",
        _folio_private=True,
        _folio_notify=False,
        _wait_process=dict(wait or {}),
        save_data=lambda key, value: saved.__setitem__(key, value),
    )
    plugin.saved = saved
    return plugin


def test_event_identity_prefers_v3_then_provider_ids_and_path():
    """播放事件依次复用统一身份、ProviderIds 和路径 TMDB 标签。"""
    direct = SimpleNamespace(
        media_source=MediaSource.TMDB,
        media_id="30984",
        tmdb_id="30984",
        json_object={"Item": {"ProviderIds": {"Tmdb": "106449"}}},
        item_path="D:/TV/[tmdbid=243224]/episode.mkv",
    )
    assert folio._event_media_identity(direct) == (MediaSource.TMDB, "30984")

    provider = SimpleNamespace(
        media_source=None,
        media_id=None,
        tmdb_id=None,
        json_object={"Item": {"ProviderIds": {"Tmdb": "106449"}}},
        item_path="",
    )
    assert folio._event_media_identity(provider) == (MediaSource.TMDB, "106449")

    path = SimpleNamespace(
        media_source=None,
        media_id=None,
        tmdb_id=None,
        json_object={},
        item_path="D:/动漫/凡人修仙传 [tmdbid=106449]/S01E02.mkv",
    )
    assert folio._event_media_identity(path) == (MediaSource.TMDB, "106449")


def test_event_identity_prefers_raw_douban_over_host_selected_tmdb():
    """原始 ProviderIds 同时含 TMDB 和豆瓣时必须保留豆瓣身份。"""
    event = SimpleNamespace(
        media_source=MediaSource.TMDB,
        media_id="30984",
        json_object={"Item": {"ProviderIds": {"Tmdb": "30984", "Douban": "1460932"}}},
        item_path="",
    )
    assert folio._event_media_identity(event) == (MediaSource.Douban, "1460932")


def test_event_identity_prefers_path_tmdb_over_episode_tvdb():
    """整理路径中的 TMDB 主 ID 优先于 Episode 的 TVDB/IMDb 辅助 ID。"""
    event = SimpleNamespace(
        media_source=MediaSource.TVDB,
        media_id="99999",
        json_object={"Item": {"ProviderIds": {"Tvdb": "99999", "Imdb": "tt99999"}}},
        item_path="D:/TV/死神 [tmdbid=30984]/S02E02.mkv",
    )
    assert folio._event_media_identity(event) == (MediaSource.TMDB, "30984")


def test_series_context_uses_parent_series_year_and_identity(monkeypatch):
    """剧集事件使用 Series 的年份和身份，不能使用 Episode 年份。"""
    class FakeMediaServerChain:
        """模拟媒体服务器父级查询。"""

        def iteminfo(self, server, item_id):
            """返回父级 Series 条目。"""
            assert server == "Embyserver"
            assert item_id == "series-1"
            return SimpleNamespace(
                title="死神",
                year="2004",
                media_source=MediaSource.TMDB,
                media_id="30984",
            )

    monkeypatch.setattr(folio, "MediaServerChain", FakeMediaServerChain)
    monkeypatch.setattr(folio, "MediaServerHelper", lambda: SimpleNamespace(get_services=lambda: {}))
    plugin = _plugin()
    event = SimpleNamespace(
        item_id="series-1",
        server_name="Embyserver",
        item_path="",
        json_object={"Item": {"SeriesName": "死神", "ProductionYear": 2026}},
    )

    context = folio._series_context(plugin, event)

    assert context["title"] == "死神"
    assert context["year"] == "2004"
    assert context["media_source"] == MediaSource.TMDB
    assert context["media_id"] == "30984"


def test_title_candidates_with_same_year_are_not_blindly_selected(monkeypatch):
    """同名同年存在多个媒体候选时必须保持未识别。"""
    candidates = [
        SimpleNamespace(
            title="凡人修仙传", year="2020", type=MediaType.TV,
            media_source=MediaSource.TMDB, media_id="106449",
        ),
        SimpleNamespace(
            title="凡人修仙传", year="2020", type=MediaType.TV,
            media_source=MediaSource.TMDB, media_id="243224",
        ),
    ]
    monkeypatch.setattr(folio, "MediaChain", lambda: SearchMediaChain(candidates))
    meta = folio.MetaInfo("凡人修仙传")
    meta.type = MediaType.TV
    meta.year = "2020"

    assert folio._recognize_title_media(meta) is None


def test_repair_folio_history_fills_poster_from_saved_douban_id(monkeypatch):
    """历史记录已有豆瓣 ID但没有海报时回读详情并保存海报。"""
    plugin = _plugin()
    plugin.get_data = lambda key: {
        "folio_data": {
            "死神": {
                "subject_id": "1460932",
                "subject_name": "死神",
                "media_source": MediaSource.Douban.value,
                "media_id": "1460932",
                "poster_path": "",
                "type": "TV",
                "timestamp": "2026-08-17 10:00:00",
            }
        }
    }.get(key)
    monkeypatch.setattr(
        folio,
        "_load_douban_media",
        lambda subject_id, title, media_type: SimpleNamespace(
            title="死神", poster_path="https://img.example/bleach.webp"
        ),
    )

    changed = folio.repair_folio_history(plugin)

    assert changed == 1
    assert plugin.saved["folio_data"]["死神"]["poster_path"].endswith("bleach.webp")


def test_fanren_reuses_tmdb_identity_and_converts_to_anime_douban(monkeypatch):
    """凡人修仙传复用 TMDB 106449，不再按标题命中真人剧。"""
    FakeDoubanApi.reset()
    chain = FakeMediaChain(converted={
        "id": "34925294",
        "title": "凡人修仙传",
        "pic": {"large": "https://img.example/fanren.webp"},
    })
    monkeypatch.setattr(folio, "DoubanApi", FakeDoubanApi)
    monkeypatch.setattr(folio, "MediaChain", lambda: chain)
    media = SimpleNamespace(
        media_source=MediaSource.TMDB,
        media_id="106449",
        tmdb_id=106449,
        title="凡人修仙传",
        year="2020",
        season=1,
        poster_path="https://img.example/tmdb.jpg",
    )
    plugin = _plugin()
    processed = {}

    assert folio._sync_to_douban(plugin, "凡人修仙传", "do", "TV", processed, media)

    assert FakeDoubanApi.search_calls == []
    assert FakeDoubanApi.status_calls == [("34925294", "do", True)]
    assert chain.convert_calls == [{
        "target_source": MediaSource.Douban,
        "media_source": MediaSource.TMDB,
        "media_id": "106449",
        "mtype": MediaType.TV,
        "season": 1,
    }]
    assert processed["凡人修仙传"]["subject_id"] == "34925294"
    assert processed["凡人修仙传"]["media_source"] == MediaSource.Douban.value
    assert processed["凡人修仙传"]["media_id"] == "34925294"
    assert processed["凡人修仙传"]["poster_path"] == "https://img.example/fanren.webp"


def test_bleach_never_accepts_duke_of_death_title_candidate(monkeypatch):
    """死神标题不得接受死神少爷与黑女仆候选。"""
    assert folio._subject_title_matches("死神 第2季", "死神")
    assert not folio._subject_title_matches("死神 第2季", "死神少爷与黑女仆 第二季")

    FakeDoubanApi.reset()
    FakeDoubanApi.search_result = ("死神少爷与黑女仆 第二季", "35605985")
    monkeypatch.setattr(folio, "DoubanApi", FakeDoubanApi)
    plugin = _plugin()

    assert folio._resolve_douban_subject(
        plugin,
        "死神 第2季",
        "TV",
        mediainfo=None,
        api=FakeDoubanApi("cookie"),
    ) == (None, None, "")


def test_bleach_retries_exact_tmdb_identity_at_series_level(monkeypatch):
    """死神分季转换无结果时复用 TMDB 30984 匹配豆瓣整剧条目。"""
    FakeDoubanApi.reset()
    FakeDoubanApi.search_result = ("死神少爷与黑女仆 第二季", "35605985")
    chain = SeasonFallbackMediaChain(converted={
        "id": "1460932",
        "title": "死神",
        "cover_url": "https://img.example/bleach.webp",
    })
    monkeypatch.setattr(folio, "DoubanApi", FakeDoubanApi)
    monkeypatch.setattr(folio, "MediaChain", lambda: chain)
    media = SimpleNamespace(
        media_source=MediaSource.TMDB,
        media_id="30984",
        title="死神",
        year="2004",
        season=2,
        poster_path="",
    )
    plugin = _plugin()
    processed = {}

    assert folio._sync_to_douban(plugin, "死神 第2季", "do", "TV", processed, media)

    assert FakeDoubanApi.search_calls == []
    assert FakeDoubanApi.status_calls == [("1460932", "do", True)]
    assert [call["season"] for call in chain.convert_calls] == [2, None]
    assert all(call["media_id"] == "30984" for call in chain.convert_calls)
    assert processed["死神 第2季"]["subject_id"] == "1460932"
    assert processed["死神 第2季"]["subject_name"] == "死神"


def test_waiting_subject_reads_douban_detail_to_restore_poster(monkeypatch):
    """待重试条目缺少媒体对象时按已存豆瓣 ID 回读并补齐海报。"""
    FakeDoubanApi.reset()
    monkeypatch.setattr(folio, "DoubanApi", FakeDoubanApi)
    recognize_calls = []

    def recognize(meta, media_source=None, media_id=None, tmdb_id=None):
        """模拟按豆瓣身份读取正式标题和海报。"""
        recognize_calls.append((media_source, media_id, meta.type))
        return SimpleNamespace(
            title="躲在超市后门抽烟的两人",
            poster_path="https://img.example/smoking.webp",
        )

    monkeypatch.setattr(folio, "_recognize_media", recognize)
    title = "躲在超市后门抽烟的两人"
    plugin = _plugin({
        title: {
            "subject_id": "37441858",
            "subject_name": title,
            "media_source": MediaSource.Douban.value,
            "media_id": "37441858",
            "status": "do",
            "poster_path": "",
            "type": "TV",
        }
    })
    processed = {}

    assert folio._sync_to_douban(plugin, title, "do", "TV", processed, mediainfo=None)

    assert FakeDoubanApi.search_calls == []
    assert recognize_calls == [(MediaSource.Douban, "37441858", MediaType.TV)]
    assert processed[title]["subject_id"] == "37441858"
    assert processed[title]["poster_path"] == "https://img.example/smoking.webp"
    assert title not in plugin._wait_process


def test_failed_status_persists_douban_identity_and_poster(monkeypatch):
    """豆瓣状态写入失败时保存完整豆瓣身份和海报供后续精确重试。"""
    FakeDoubanApi.reset()
    FakeDoubanApi.status_result = False
    chain = FakeMediaChain(converted={
        "id": "34925294",
        "title": "凡人修仙传",
        "cover_url": "https://img.example/fanren.webp",
    })
    monkeypatch.setattr(folio, "DoubanApi", FakeDoubanApi)
    monkeypatch.setattr(folio, "MediaChain", lambda: chain)
    media = SimpleNamespace(
        media_source=MediaSource.TMDB,
        media_id="106449",
        title="凡人修仙传",
        year="2020",
        season=1,
        poster_path="",
    )
    plugin = _plugin()

    assert not folio._sync_to_douban(plugin, "凡人修仙传", "do", "TV", {}, media)

    waiting = plugin._wait_process["凡人修仙传"]
    assert waiting["subject_id"] == "34925294"
    assert waiting["media_source"] == MediaSource.Douban.value
    assert waiting["media_id"] == "34925294"
    assert waiting["poster_path"] == "https://img.example/fanren.webp"
