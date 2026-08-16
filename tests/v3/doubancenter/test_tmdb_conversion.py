"""豆瓣中心 V3 豆瓣到 TMDB 转换测试。"""

from types import SimpleNamespace

from app.schemas.types import MediaSource, MediaType
from app.sdk.media import MetaInfo

from doubancenter import feed
from doubancenter.adapter import douban as douban_adapter
from doubancenter.adapter import rss as rss_adapter
from doubancenter.model.identity import convert_identity
from doubancenter.service import dashboard_rank_media
from doubancenter.service import dashboard_rank_subscription
from doubancenter.service import bangumi_tmdb


class FakeMediaInfo:
    """提供榜单识别需要的最小媒体对象。"""

    def __init__(
        self,
        *,
        title: str,
        source: MediaSource,
        media_id: str,
        tmdb_id=None,
        douban_id=None,
        poster: str = "",
    ):
        """初始化可识别的媒体字段。"""
        self.title = title
        self.year = "2026"
        self.type = MediaType.TV
        self.media_source = source
        self.media_id = str(media_id)
        self.tmdb_id = tmdb_id
        self.douban_id = douban_id
        self.bangumi_id = None
        self.poster_path = poster
        self.overview = "测试简介"

    def get_poster_image(self):
        """返回测试海报地址。"""
        return self.poster_path


class ConversionChain:
    """模拟跨源转换和后续媒体识别。"""

    def __init__(
        self,
        *,
        mapping=None,
        tmdb_media=None,
        douban_media=None,
        title_media=None,
        douban_detail=None,
        title_mapping=None,
    ):
        """保存各识别分支的预设返回值。"""
        self.mapping = mapping
        self.tmdb_media = tmdb_media
        self.douban_media = douban_media
        self.title_media = title_media
        self.douban_detail = douban_detail
        self.title_mapping = title_mapping
        self.convert_calls = []
        self.recognize_calls = []
        self.douban_info_calls = []
        self.match_tmdb_calls = []

    def convert_media_identity(self, **kwargs):
        """记录转换参数并返回预设映射。"""
        self.convert_calls.append(kwargs)
        if isinstance(self.mapping, Exception):
            raise self.mapping
        return self.mapping

    def recognize_media(self, **kwargs):
        """按识别来源返回对应的测试媒体。"""
        self.recognize_calls.append(kwargs)
        source = kwargs.get("media_source")
        if source == MediaSource.TMDB:
            return self.tmdb_media
        if source == MediaSource.Douban:
            return self.douban_media
        return self.title_media

    def douban_info(self, **kwargs):
        """记录豆瓣详情参数并返回预设详情。"""
        self.douban_info_calls.append(kwargs)
        return self.douban_detail

    def match_tmdbinfo(self, **kwargs):
        """记录 TMDB 标题匹配参数并返回预设映射。"""
        self.match_tmdb_calls.append(kwargs)
        return self.title_mapping


class PluginBaseChain:
    """模拟宿主插件基类自带但没有 V3 身份转换方法的处理链。"""

    def __init__(self, tmdb_media=None):
        """保存识别结果并记录调用。"""
        self.tmdb_media = tmdb_media
        self.recognize_calls = []

    def recognize_media(self, **kwargs):
        """记录媒体识别参数并返回预设结果。"""
        self.recognize_calls.append(kwargs)
        return self.tmdb_media


def test_convert_identity_reads_raw_tmdb_mapping_and_forwards_season():
    """转换助手读取宿主原始 TMDB 字典并传递季号。"""
    chain = ConversionChain(mapping={"id": 60625})

    source, media_id = convert_identity(
        chain,
        target_source=MediaSource.TMDB,
        media_source=MediaSource.Douban,
        media_id="36508123",
        mtype=MediaType.TV,
        season=9,
    )

    assert (source, media_id) == (MediaSource.TMDB, "60625")
    assert chain.convert_calls == [{
        "target_source": MediaSource.TMDB,
        "media_source": MediaSource.Douban,
        "media_id": "36508123",
        "mtype": MediaType.TV,
        "season": 9,
    }]


def test_convert_identity_rejects_zero_tmdb_mapping():
    """转换结果为零值时不得构造 TMDB 身份。"""
    chain = ConversionChain(mapping={"id": 0})

    assert convert_identity(
        chain,
        target_source=MediaSource.TMDB,
        media_source=MediaSource.Douban,
        media_id="36508123",
    ) == (None, None)


def test_convert_identity_retries_original_title_without_year_for_unreleased_tmdb():
    """宿主年份过滤未定档条目时，使用豆瓣英文原名无年份精确匹配。"""
    chain = ConversionChain(
        mapping=None,
        douban_detail={
            "title": "大理石庄园谋杀案",
            "original_title": "Marble Hall Murders",
            "year": "2026",
        },
        title_mapping={
            "id": 283319,
            "name": "Marble Hall Murders",
            "first_air_date": "",
        },
    )

    assert convert_identity(
        chain,
        target_source=MediaSource.TMDB,
        media_source=MediaSource.Douban,
        media_id="37218278",
        mtype=MediaType.TV,
    ) == (MediaSource.TMDB, "283319")
    assert chain.douban_info_calls == [{
        "doubanid": "37218278",
        "mtype": MediaType.TV,
    }]
    assert chain.match_tmdb_calls == [{
        "name": "Marble Hall Murders",
        "mtype": MediaType.TV,
        "year": None,
        "season": None,
    }]


def test_convert_identity_does_not_retry_chinese_title():
    """豆瓣缺少非中文原名时，不得重新按中文标题冒险匹配。"""
    chain = ConversionChain(
        mapping=None,
        douban_detail={
            "title": "大理石庄园谋杀案",
            "original_title": "",
            "year": "2026",
        },
        title_mapping={"id": 283319},
    )

    assert convert_identity(
        chain,
        target_source=MediaSource.TMDB,
        media_source=MediaSource.Douban,
        media_id="37218278",
        mtype=MediaType.TV,
    ) == (None, None)
    assert chain.match_tmdb_calls == []


def test_convert_identity_rejects_conflicting_yearless_match():
    """无年份搜索命中明确不同年份时，不得接受该 TMDB 身份。"""
    chain = ConversionChain(
        mapping=None,
        douban_detail={
            "original_title": "Marble Hall Murders",
            "year": "2026",
        },
        title_mapping={
            "id": 283319,
            "name": "Marble Hall Murders",
            "first_air_date": "2024-01-01",
        },
    )

    assert convert_identity(
        chain,
        target_source=MediaSource.TMDB,
        media_source=MediaSource.Douban,
        media_id="37218278",
        mtype=MediaType.TV,
    ) == (None, None)


def test_convert_identity_uses_mobile_original_title_when_douban_chain_is_limited():
    """豆瓣链受限时使用移动页英文原名，并去掉季号后匹配 TMDB。"""
    chain = ConversionChain(
        mapping=None,
        douban_detail=RuntimeError("rate limited"),
        title_mapping={"id": 95480, "name": "Slow Horses", "first_air_date": "2022-04-01"},
    )

    assert convert_identity(
        chain,
        target_source=MediaSource.TMDB,
        media_source=MediaSource.Douban,
        media_id="36689816",
        mtype=MediaType.TV,
        season=6,
        fallback_title_loader=lambda: ["Slow Horses Season 6（2026）"],
    ) == (MediaSource.TMDB, "95480")
    assert chain.match_tmdb_calls == [{
        "name": "Slow Horses",
        "mtype": MediaType.TV,
        "year": None,
        "season": 6,
    }]
    assert chain.douban_info_calls == []


def test_convert_identity_rejects_chinese_mobile_title():
    """移动页没有英文原名时仍不得按中文标题重试。"""
    chain = ConversionChain(mapping=None, douban_detail=None, title_mapping={"id": 95480})

    assert convert_identity(
        chain,
        target_source=MediaSource.TMDB,
        media_source=MediaSource.Douban,
        media_id="36689816",
        mtype=MediaType.TV,
        season=6,
        fallback_title_loader=lambda: ["流人 第六季（2026）"],
    ) == (None, None)
    assert chain.match_tmdb_calls == []


def test_parse_mobile_original_titles_reads_public_subject_page_markup():
    """豆瓣移动页适配器只读取原名节点并解码实体。"""
    document = """
    <div class="sub-title">流人 第六季</div>
    <div class="sub-original-title">Slow Horses &amp; Friends Season 6（2026）</div>
    """

    assert douban_adapter.parse_mobile_original_titles(document) == [
        "Slow Horses & Friends Season 6（2026）"
    ]


def test_douban_subject_id_reads_coming_rss_link():
    """即将上映 RSS 链接必须提供可转换的豆瓣 subject ID。"""
    assert rss_adapter.douban_subject_id(
        "https://movie.douban.com/subject/37218278/"
    ) == "37218278"


def test_preserve_existing_tmdb_identity_during_transient_refresh_failure():
    """刷新瞬时失败时不得把已确认的 TMDB 主身份回退为豆瓣。"""
    entry = {
        "title": "瑞克和莫蒂 第九季",
        "douban_id": "36508123",
        "poster": "douban-poster.jpg",
    }
    existing = {
        "title": "瑞克和莫蒂",
        "tmdb_title": "瑞克和莫蒂",
        "original_title": "瑞克和莫蒂 第九季",
        "media_source": MediaSource.TMDB.value,
        "media_id": "60625",
        "tmdbid": 60625,
        "douban_id": "36508123",
        "poster": "tmdb-poster.jpg",
    }

    feed._preserve_existing_tmdb_identity(entry, existing)

    assert entry["media_source"] == MediaSource.TMDB.value
    assert entry["media_id"] == "60625"
    assert entry["tmdbid"] == 60625
    assert entry["title"] == "瑞克和莫蒂 第九季"
    assert entry["tmdb_title"] == "瑞克和莫蒂"
    assert "original_title" not in entry
    assert entry["poster"] == "tmdb-poster.jpg"


def test_preserve_existing_tmdb_identity_rejects_changed_douban_subject():
    """同一榜单位置换成其他豆瓣条目时不得沿用旧 TMDB 身份。"""
    entry = {
        "title": "流人 第六季",
        "douban_id": "36689816",
        "poster": "new-poster.jpg",
    }
    existing = {
        "title": "瑞克和莫蒂",
        "media_source": MediaSource.TMDB.value,
        "media_id": "60625",
        "tmdbid": 60625,
        "douban_id": "36508123",
        "poster": "old-poster.jpg",
    }

    feed._preserve_existing_tmdb_identity(entry, existing)

    assert entry.get("media_source") is None
    assert entry.get("media_id") is None
    assert entry.get("tmdbid") is None
    assert entry["title"] == "流人 第六季"
    assert entry["poster"] == "new-poster.jpg"


def test_rank_refresh_converts_douban_identity_before_recognition():
    """榜单刷新优先按豆瓣 ID 转换，并保存 TMDB 主身份和海报。"""
    tmdb_media = FakeMediaInfo(
        title="瑞克和莫蒂",
        source=MediaSource.TMDB,
        media_id="60625",
        tmdb_id=60625,
        poster="tmdb-poster.jpg",
    )
    chain = ConversionChain(mapping={"id": 60625}, tmdb_media=tmdb_media)
    plugin = SimpleNamespace(chain=chain)
    item = {
        "title": "瑞克和莫蒂 第九季",
        "year": "2026",
        "media_type": "tv",
        "doubanid": "36508123",
    }
    entry = {
        "title": item["title"],
        "year": item["year"],
        "poster": "douban-poster.jpg",
        "douban_id": "36508123",
    }

    result = feed._apply_display_recognition(
        plugin,
        item,
        entry,
        "tv_global",
        {"key": "tv_global", "route": "/douban/tv/weekly_global"},
    )

    assert result is tmdb_media
    assert entry["media_source"] == MediaSource.TMDB.value
    assert entry["media_id"] == "60625"
    assert entry["tmdbid"] == 60625
    assert entry["douban_id"] == "36508123"
    assert entry["title"] == "瑞克和莫蒂 第九季"
    assert entry["tmdb_title"] == "瑞克和莫蒂"
    assert "original_title" not in entry
    assert entry["poster"] == "tmdb-poster.jpg"
    assert chain.recognize_calls[0]["media_source"] == MediaSource.TMDB


def test_rank_refresh_keeps_douban_name_for_marble_hall_murders():
    """英文 TMDB 名称只写入辅助字段，榜单仍展示豆瓣中文名。"""
    tmdb_media = FakeMediaInfo(
        title="Marble Hall Murders",
        source=MediaSource.TMDB,
        media_id="283319",
        tmdb_id=283319,
        poster="tmdb-poster.jpg",
    )
    chain = ConversionChain(mapping={"id": 283319}, tmdb_media=tmdb_media)
    plugin = SimpleNamespace(chain=chain)
    item = {
        "title": "大理石庄园谋杀案",
        "year": "2026",
        "media_type": "tv",
        "doubanid": "37218278",
    }
    entry = {
        "title": item["title"],
        "year": item["year"],
        "douban_id": "37218278",
        "original_title": item["title"],
    }

    result = feed._apply_display_recognition(
        plugin,
        item,
        entry,
        "coming",
        {"key": "coming", "route": "/douban/tv/coming"},
    )

    assert result is tmdb_media
    assert entry["title"] == "大理石庄园谋杀案"
    assert entry["tmdb_title"] == "Marble Hall Murders"
    assert entry["media_source"] == MediaSource.TMDB.value
    assert entry["media_id"] == "283319"
    assert entry["tmdbid"] == 283319
    assert "original_title" not in entry


def test_rank_refresh_keeps_douban_name_for_slow_horses_season_six():
    """带季号的豆瓣名称保持不变，同时记录 TMDB 基础剧名。"""
    tmdb_media = FakeMediaInfo(
        title="Slow Horses",
        source=MediaSource.TMDB,
        media_id="95480",
        tmdb_id=95480,
        poster="tmdb-poster.jpg",
    )
    chain = ConversionChain(mapping={"id": 95480}, tmdb_media=tmdb_media)
    plugin = SimpleNamespace(chain=chain)
    item = {
        "title": "流人 第六季",
        "year": "2026",
        "media_type": "tv",
        "doubanid": "36689816",
    }
    entry = {
        "title": item["title"],
        "year": item["year"],
        "douban_id": "36689816",
    }

    result = feed._apply_display_recognition(
        plugin,
        item,
        entry,
        "coming",
        {"key": "coming", "route": "/douban/tv/coming"},
    )

    assert result is tmdb_media
    assert entry["title"] == "流人 第六季"
    assert entry["tmdb_title"] == "Slow Horses"
    assert entry["media_source"] == MediaSource.TMDB.value
    assert entry["media_id"] == "95480"
    assert entry["tmdbid"] == 95480


def test_rank_refresh_reuses_existing_tmdb_identity_before_network_conversion():
    """同一豆瓣条目已有 TMDB 身份时直接复用，避免重复请求转换链。"""
    tmdb_media = FakeMediaInfo(
        title="瑞克和莫蒂",
        source=MediaSource.TMDB,
        media_id="60625",
        tmdb_id=60625,
        poster="tmdb-poster.jpg",
    )
    chain = ConversionChain(mapping=RuntimeError("should not convert"), tmdb_media=tmdb_media)
    plugin = SimpleNamespace(chain=chain)
    item = {
        "title": "瑞克和莫蒂 第九季",
        "year": "2026",
        "media_type": "tv",
        "doubanid": "36508123",
        "link": "https://movie.douban.com/subject/36508123/",
    }
    entry = {
        "title": item["title"],
        "year": item["year"],
        "poster": "douban-poster.jpg",
        "douban_id": "36508123",
    }
    existing = {
        "title": "瑞克和莫蒂",
        "media_source": MediaSource.TMDB.value,
        "media_id": "60625",
        "tmdbid": 60625,
        "link": "https://movie.douban.com/subject/36508123/",
    }

    result = feed._apply_display_recognition(
        plugin,
        item,
        entry,
        "tv_global",
        {"key": "tv_global", "route": "/douban/tv/weekly_global"},
        existing=existing,
    )

    assert result is tmdb_media
    assert chain.convert_calls == []
    assert entry["media_source"] == MediaSource.TMDB.value
    assert entry["media_id"] == "60625"
    assert entry["douban_id"] == "36508123"
    assert entry["title"] == "瑞克和莫蒂 第九季"
    assert entry["tmdb_title"] == "瑞克和莫蒂"


def test_rank_refresh_uses_media_chain_when_plugin_base_chain_cannot_convert():
    """插件基类处理链缺少 V3 转换方法时必须切换到 MediaChain。"""
    tmdb_media = FakeMediaInfo(
        title="瑞克和莫蒂",
        source=MediaSource.TMDB,
        media_id="60625",
        tmdb_id=60625,
    )
    plugin_chain = PluginBaseChain(tmdb_media=tmdb_media)
    conversion_chain = ConversionChain(mapping={"id": 60625}, tmdb_media=tmdb_media)
    plugin = SimpleNamespace(chain=plugin_chain)
    item = {
        "title": "瑞克和莫蒂 第九季",
        "year": "2026",
        "media_type": "tv",
        "doubanid": "36508123",
    }
    entry = {
        "title": item["title"],
        "year": item["year"],
        "douban_id": "36508123",
    }

    result = feed._apply_display_recognition(
        plugin,
        item,
        entry,
        "tv_global",
        {"key": "tv_global", "route": "/douban/tv/weekly_global"},
        media_chain_cls=lambda: conversion_chain,
    )

    assert result is tmdb_media
    assert conversion_chain.convert_calls[0]["media_id"] == "36508123"
    assert conversion_chain.recognize_calls[0]["media_source"] == MediaSource.TMDB
    assert plugin_chain.recognize_calls == []
    assert entry["media_source"] == MediaSource.TMDB.value
    assert entry["media_id"] == "60625"
    assert entry["title"] == "瑞克和莫蒂 第九季"
    assert entry["tmdb_title"] == "瑞克和莫蒂"


def test_rank_refresh_keeps_douban_identity_when_mapping_is_missing():
    """豆瓣 ID 无映射时不允许回退标题并误写 TMDB 身份。"""
    wrong_title_media = FakeMediaInfo(
        title="错误匹配",
        source=MediaSource.TMDB,
        media_id="999",
        tmdb_id=999,
    )
    chain = ConversionChain(mapping=None, title_media=wrong_title_media)
    plugin = SimpleNamespace(chain=chain)
    item = {
        "title": "流人 第六季",
        "year": "2026",
        "media_type": "tv",
        "doubanid": "36689816",
    }
    entry = {
        "title": item["title"],
        "year": item["year"],
        "poster": "douban-poster.jpg",
        "douban_id": "36689816",
    }

    result = feed._apply_display_recognition(
        plugin,
        item,
        entry,
        "coming",
        {"key": "coming", "route": "/douban/tv/coming"},
    )

    assert result is None
    assert chain.recognize_calls == []
    assert entry["douban_id"] == "36689816"
    assert entry["title"] == "流人 第六季"
    assert "tmdb_title" not in entry
    assert entry.get("tmdbid") is None
    assert entry.get("media_source") is None


def test_manual_resolve_returns_tmdb_identity_and_preserves_douban_id():
    """手动识别转换成功后返回 TMDB 主身份并保留豆瓣辅助 ID。"""
    tmdb_media = FakeMediaInfo(
        title="瑞克和莫蒂",
        source=MediaSource.TMDB,
        media_id="60625",
        tmdb_id=60625,
        poster="tmdb-poster.jpg",
    )
    chain = ConversionChain(mapping={"id": 60625}, tmdb_media=tmdb_media)

    result = dashboard_rank_media.resolve_media_from_rank(
        object(),
        "tv",
        "瑞克和莫蒂 第九季",
        "2026",
        media_source="douban",
        media_id="36508123",
        media_chain_cls=lambda: chain,
    )

    assert result["success"] is True
    assert result["data"]["media_source"] == MediaSource.TMDB.value
    assert result["data"]["media_id"] == "60625"
    assert result["data"]["tmdb_id"] == 60625
    assert result["data"]["douban_id"] == "36508123"
    assert chain.convert_calls[0]["season"] == 9


def test_manual_resolve_keeps_douban_identity_when_mapping_is_missing():
    """手动转换无映射时使用豆瓣详情，但不伪造 TMDB ID。"""
    douban_media = FakeMediaInfo(
        title="流人 第六季",
        source=MediaSource.Douban,
        media_id="36689816",
        douban_id="36689816",
        poster="douban-poster.jpg",
    )
    chain = ConversionChain(mapping=None, douban_media=douban_media)

    result = dashboard_rank_media.resolve_media_from_rank(
        object(),
        "tv",
        "流人 第六季",
        "2026",
        media_source="douban",
        media_id="36689816",
        media_chain_cls=lambda: chain,
    )

    assert result["success"] is True
    assert result["data"]["media_source"] == MediaSource.Douban.value
    assert result["data"]["media_id"] == "36689816"
    assert result["data"]["douban_id"] == "36689816"
    assert result["data"]["tmdb_id"] is None


def test_manual_resolve_uses_title_fallback_without_stable_identity():
    """没有来源身份时仍保留原有的标题识别兜底能力。"""
    tmdb_media = FakeMediaInfo(
        title="Marble Hall Murders",
        source=MediaSource.TMDB,
        media_id="283319",
        tmdb_id=283319,
        poster="tmdb-poster.jpg",
    )
    chain = ConversionChain(title_media=tmdb_media)

    result = dashboard_rank_media.resolve_media_from_rank(
        object(),
        "tv",
        "Marble Hall Murders",
        "",
        media_chain_cls=lambda: chain,
    )

    assert result["success"] is True
    assert result["data"]["media_source"] == MediaSource.TMDB.value
    assert result["data"]["media_id"] == "283319"
    assert result["data"]["tmdb_id"] == 283319
    assert len(chain.recognize_calls) == 1
    assert "media_source" not in chain.recognize_calls[0]


def test_bangumi_subject_title_year_identifies_tmdb_and_rejects_bangumi_identity():
    """Bangumi subject 只作为标题年份来源，标题识别必须返回 TMDB 身份。"""
    tmdb_media = FakeMediaInfo(
        title="Yan neko",
        source=MediaSource.TMDB,
        media_id="312949",
        tmdb_id=312949,
    )
    chain = ConversionChain(title_media=tmdb_media)
    subject = {"id": 622206, "name": "ヤニねこ", "name_cn": "尼古喵喵", "date": "2026-04-01"}

    result = bangumi_tmdb.recognize_bangumi_tmdb(
        object(),
        chain,
        MetaInfo("ヤニねこ"),
        bangumi_id="622206",
        media_type=MediaType.TV,
        subject_fetcher=lambda plugin, bangumi_id: subject,
    )

    assert result["mediainfo"] is tmdb_media
    assert result["title"] == "尼古喵喵"
    assert result["year"] == "2026"
    assert chain.recognize_calls[0]["meta"].name == "尼古喵喵"
    assert chain.recognize_calls[0]["cache"] is False
    assert "media_source" not in chain.recognize_calls[0]

    bangumi_media = FakeMediaInfo(
        title="尼古喵喵",
        source=MediaSource.Bangumi,
        media_id="622206",
    )
    bangumi_chain = ConversionChain(title_media=bangumi_media)
    failed = bangumi_tmdb.recognize_bangumi_tmdb(
        object(),
        bangumi_chain,
        MetaInfo("ヤニねこ"),
        bangumi_id="622206",
        media_type=MediaType.TV,
        subject_fetcher=lambda plugin, bangumi_id: subject,
    )
    assert failed["mediainfo"] is None


def test_bangumi_subject_uses_tmdb_limited_title_year_search():
    """宿主限定 TMDB 搜索命中时直接复用候选媒体对象。"""
    tmdb_media = FakeMediaInfo(
        title="尼古喵喵",
        source=MediaSource.TMDB,
        media_id="312949",
        tmdb_id=312949,
    )
    chain = ConversionChain()
    search_calls = []
    chain.search = lambda query, media_source=None: (
        search_calls.append((query, media_source)) or (MetaInfo(query), [tmdb_media])
    )
    subject = {"id": 622206, "name": "ヤニねこ", "name_cn": "尼古喵喵", "date": "2026-04-01"}

    result = bangumi_tmdb.recognize_bangumi_tmdb(
        object(),
        chain,
        MetaInfo("ヤニねこ"),
        bangumi_id="622206",
        media_type=MediaType.TV,
        subject_fetcher=lambda plugin, bangumi_id: subject,
    )

    assert result["mediainfo"] is tmdb_media
    assert search_calls == [("尼古喵喵 2026", MediaSource.TMDB)]


def test_bangumi_rank_refresh_saves_tmdb_identity(monkeypatch):
    """Bangumi 榜单刷新成功后保存 TMDB 主身份并保留 Bangumi 辅助 ID。"""
    tmdb_media = FakeMediaInfo(
        title="Yan neko",
        source=MediaSource.TMDB,
        media_id="312949",
        tmdb_id=312949,
        poster="tmdb-poster.jpg",
    )
    plugin = SimpleNamespace(
        chain=ConversionChain(title_media=tmdb_media),
        save_data=lambda key, value: None,
    )
    subject = {"id": 622206, "name": "ヤニねこ", "name_cn": "尼古喵喵", "date": "2026-04-01"}
    monkeypatch.setattr(feed, "_fetch_bangumi_subject", lambda current, bangumi_id: subject)
    item = {"title": "ヤニねこ", "year": "2026", "bangumi_id": "622206"}
    entry = {"title": item["title"], "year": item["year"], "bangumi_id": "622206"}

    result = feed._apply_bangumi_recognition(plugin, item, entry)

    assert result is tmdb_media
    assert entry["media_source"] == MediaSource.TMDB.value
    assert entry["media_id"] == "312949"
    assert entry["tmdb_id"] == 312949
    assert entry["tmdbid"] == 312949
    assert entry["bangumi_id"] == "622206"
    assert entry["title"] == "尼古喵喵"


def test_manual_bangumi_resolve_returns_tmdb_identity():
    """手动点击榜单识别时复用 Bangumi subject 标题年份得到的 TMDB 身份。"""
    tmdb_media = FakeMediaInfo(
        title="Yan neko",
        source=MediaSource.TMDB,
        media_id="312949",
        tmdb_id=312949,
    )
    chain = ConversionChain(title_media=tmdb_media)
    subject = {"id": 622206, "name": "ヤニねこ", "name_cn": "尼古喵喵", "date": "2026-04-01"}

    result = dashboard_rank_media.resolve_media_from_rank(
        object(),
        "tv",
        "ヤニねこ",
        "2026",
        media_source="bangumi",
        media_id="622206",
        media_chain_cls=lambda: chain,
        bangumi_subject_fetcher=lambda plugin, bangumi_id: subject,
    )

    assert result["success"] is True
    assert result["data"]["media_source"] == MediaSource.TMDB.value
    assert result["data"]["media_id"] == "312949"
    assert result["data"]["tmdb_id"] == 312949
    assert result["data"]["bangumi_id"] == "622206"


def test_manual_bangumi_subscription_passes_tmdb_identity_to_subscribe_chain():
    """手动订阅识别成功后向订阅链传递 TMDB 来源和 ID。"""
    tmdb_media = FakeMediaInfo(
        title="Yan neko",
        source=MediaSource.TMDB,
        media_id="312949",
        tmdb_id=312949,
    )
    media_chain = ConversionChain(title_media=tmdb_media)
    captured = {}
    subject = {"id": 622206, "name": "ヤニねこ", "name_cn": "尼古喵喵", "date": "2026-04-01"}

    class SubscribeChain:
        """记录手动订阅调用。"""

        def exists(self, mediainfo, meta):
            """模拟没有重复订阅。"""
            return False

        def add(self, **kwargs):
            """保存订阅身份并返回成功。"""
            captured.update(kwargs)
            return 1, ""

    result = dashboard_rank_subscription.subscribe_from_rank(
        object(),
        None,
        "tv",
        "ヤニねこ",
        "2026",
        bangumi_id="622206",
        media_chain_cls=lambda: media_chain,
        subscribe_chain_cls=SubscribeChain,
        bangumi_subject_fetcher=lambda plugin, bangumi_id: subject,
    )

    assert result == {"success": True, "message": "已添加订阅"}
    assert captured["media_source"] == MediaSource.TMDB
    assert captured["media_id"] == "312949"
