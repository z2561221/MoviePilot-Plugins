"""豆瓣中心 V3 豆瓣到 TMDB 转换测试。"""

from types import SimpleNamespace

from app.schemas.types import MediaSource, MediaType

from doubancenter import feed
from doubancenter.model.identity import convert_identity
from doubancenter.service import dashboard_rank_media


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

    def __init__(self, *, mapping=None, tmdb_media=None, douban_media=None, title_media=None):
        """保存各识别分支的预设返回值。"""
        self.mapping = mapping
        self.tmdb_media = tmdb_media
        self.douban_media = douban_media
        self.title_media = title_media
        self.convert_calls = []
        self.recognize_calls = []

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
    assert entry["poster"] == "tmdb-poster.jpg"
    assert chain.recognize_calls[0]["media_source"] == MediaSource.TMDB


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
