"""AgentRank MoviePilot media recognition adapter tests."""

import importlib
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_media_recognition_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

adapter_package = sys.modules.setdefault(
    f"{PACKAGE_NAME}.adapter", ModuleType(f"{PACKAGE_NAME}.adapter")
)
adapter_package.__path__ = [str(PLUGIN_DIR / "adapter")]

candidate_module = importlib.import_module(f"{PACKAGE_NAME}.model.candidate")
board_module = importlib.import_module(f"{PACKAGE_NAME}.model.board")
media_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.media")
poster_module = importlib.import_module(f"{PACKAGE_NAME}.service.poster")

Candidate = candidate_module.Candidate
RecommendationBoard = board_module.RecommendationBoard
RecommendationItem = board_module.RecommendationItem
MediaRecognitionAdapter = media_module.MediaRecognitionAdapter
BoardPosterRepairService = poster_module.BoardPosterRepairService
BoardSourceRepairService = poster_module.BoardSourceRepairService
PosterImageService = poster_module.PosterImageService


class FakeMediaType:
    """Expose the minimal MoviePilot media type enum contract."""

    MOVIE = "movie-enum"
    TV = "tv-enum"


class FakeMeta:
    """Capture title, year, and media type passed to MediaChain."""

    def __init__(self, title):
        self.title = title
        self.year = ""
        self.type = None


def test_recognition_prefers_tmdb_id_and_rebuilds_display_fields():
    """A recognized result becomes the sole display identity while source IDs remain."""
    calls = []

    class FakeChain:
        def recognize_media(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                tmdb_id=900,
                title="TMDB 标准标题",
                type=FakeMediaType.MOVIE,
                year="2026",
                original_title="Original",
                overview="Overview",
                poster_path="https://image.example/poster.jpg",
                backdrop_path="https://image.example/backdrop.jpg",
                category="剧情",
                genres=[{"id": 18, "name": "剧情"}],
                genre_ids=[18],
                actors=[{"name": "演员甲"}],
                directors=[{"name": "导演乙"}],
                origin_country=["中国大陆"],
                vote_average=8.6,
                popularity=123.4,
            )

    candidate = Candidate(
        candidate_id="douban:db-9",
        title="来源标题",
        media_type="movie",
        year=2025,
        source_ids={"douban": "db-9", "tmdb": "900"},
    )
    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)

    result = adapter.recognize(candidate)

    assert calls[0]["tmdbid"] == 900
    assert calls[0]["mtype"] == FakeMediaType.MOVIE
    assert result.candidate_id == "tmdb:movie:900"
    assert result.title == "TMDB 标准标题"
    assert result.year == 2026
    assert result.poster_path.endswith("poster.jpg")
    assert result.source_ids == {"douban": "db-9", "tmdb": "900"}
    assert result.media_type == "movie"
    assert result.metadata["mp_media_type"] == "电影"
    assert result.genres == ["剧情"]
    assert result.actors == ["演员甲"]
    assert result.directors == ["导演乙"]
    assert result.regions == ["中国大陆"]
    assert result.rating == 8.6
    assert result.popularity == 123.4
    assert result.metadata["recognized_by"] == "moviepilot"


def test_recognize_many_is_bounded_and_preserves_input_order():
    """批量识别最多使用六个工作线程，并按输入顺序返回候选。"""
    adapter = MediaRecognitionAdapter(lambda: None, FakeMeta, FakeMediaType)
    active = 0
    maximum_active = 0
    guard = threading.Lock()

    def recognize(candidate):
        """记录并发峰值并模拟有序识别结果。"""
        nonlocal active, maximum_active
        with guard:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.02)
        with guard:
            active -= 1
        if candidate.candidate_id == "tmdb:movie:7":
            raise ValueError("single candidate failed")
        return candidate

    adapter.recognize = recognize
    candidates = [
        Candidate(
            candidate_id=f"tmdb:movie:{index}",
            title=f"Title {index}",
            media_type="movie",
            source_ids={"tmdb": str(index)},
        )
        for index in range(1, 13)
    ]

    result = adapter.recognize_many(candidates)

    assert [item.candidate_id if item else None for item in result] == [
        *[f"tmdb:movie:{index}" for index in range(1, 7)],
        None,
        *[f"tmdb:movie:{index}" for index in range(8, 13)],
    ]
    assert 1 < maximum_active <= 6


def test_recognition_maps_douban_id_to_tmdb_before_source_recognition():
    """豆瓣来源先走宿主映射，再用类型化 TMDB 身份读取完整媒体。"""
    calls = []

    class FakeChain:
        """记录来源映射与最终 TMDB 识别顺序。"""

        def get_tmdbinfo_by_doubanid(self, doubanid, mtype=None):
            """返回豆瓣对应的 TMDB 信息。"""
            calls.append(("map", doubanid, mtype))
            return {"id": 910}

        def recognize_media(self, **kwargs):
            """返回按 TMDB ID 读取的标准剧集。"""
            calls.append(("recognize", kwargs))
            assert kwargs["tmdbid"] == 910
            return SimpleNamespace(
                tmdb_id=910,
                title="豆瓣映射剧集",
                type=FakeMediaType.TV,
            )

    result = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType).recognize(
        Candidate(
            candidate_id="douban:910",
            title="豆瓣映射剧集",
            media_type="tv",
            source_ids={"douban": "db-910"},
        )
    )

    assert calls[0][0] == "map"
    assert calls[1][0] == "recognize"
    assert result.candidate_id == "tmdb:tv:910"
    assert result.source_ids["douban"] == "db-910"
    assert result.source_ids["tmdb"] == "910"


def test_recognition_uses_new_source_mediaid_contract_for_anilist():
    """新版宿主的 source/mediaid 入口可直接把 AniList ID 转成 TMDB 媒体。"""
    calls = []

    class FakeChain:
        """只实现新版请求级来源识别入口。"""

        def recognize_media(self, **kwargs):
            """按 source/mediaid 返回 AniList 对应剧集。"""
            calls.append(kwargs)
            assert kwargs["source"] == "anilist"
            assert kwargs["mediaid"] == "321"
            return SimpleNamespace(
                tmdb_id=654,
                title="新版 AniList 剧集",
                type=FakeMediaType.TV,
            )

    result = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType).recognize(
        Candidate(
            candidate_id="anilist:321",
            title="新版 AniList 剧集",
            media_type="anime",
            source_ids={"anilist": "321"},
        )
    )

    assert len(calls) == 1
    assert result.candidate_id == "tmdb:tv:654"
    assert result.source_ids == {"anilist": "321", "tmdb": "654"}


def test_title_fallback_uses_at_most_two_distinct_titles():
    """来源识别失败时，TMDB 标题兜底最多尝试两个不同标题。"""
    calls = []

    class FakeChain:
        """记录所有标题识别调用但始终返回空。"""

        def recognize_media(self, **kwargs):
            """记录标题并模拟没有匹配结果。"""
            calls.append((kwargs.get("source"), kwargs.get("tmdbid"), kwargs["meta"].title))
            return None

    candidate = Candidate(
        candidate_id="anilist:321",
        title="中文标题",
        original_title="Original Title",
        media_type="anime",
        source_ids={"anilist": "321"},
    )

    assert MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType).recognize(candidate) is None

    title_calls = [title for source, tmdbid, title in calls if source == "themoviedb" or tmdbid is None]
    assert len(set(title_calls)) <= 2


def test_recognition_excludes_non_director_crew_from_director_evidence():
    """宿主混合主创列表中的编剧、剪辑与制片不得冒充导演。"""

    class FakeChain:
        """返回带混合 crew 职责的媒体识别结果。"""

        def recognize_media(self, **kwargs):
            """提供一个导演与三个非导演主创。"""
            return SimpleNamespace(
                tmdb_id=903,
                title="主创职责测试",
                type=FakeMediaType.MOVIE,
                genres=[{"name": "剧情"}],
                directors=[
                    {"name": "真导演", "job": "Director", "department": "Directing"},
                    {
                        "name": "摄影指导甲",
                        "job": "Director of Photography",
                        "department": "Camera",
                    },
                    {"name": "编剧甲", "job": "Writer", "department": "Writing"},
                    {"name": "剪辑乙", "job": "Editor", "department": "Editing"},
                    {"name": "制片丙", "job": "Producer", "department": "Production"},
                ],
            )

    candidate = Candidate(
        candidate_id="tmdb:movie:903",
        title="主创职责测试",
        media_type="movie",
        source_ids={"tmdb": "903"},
    )
    result = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType).recognize(
        candidate
    )

    assert result.directors == ["真导演"]


def test_recognition_uses_actual_type_and_animation_features_not_source_name():
    """Bangumi 也可识别为真人剧，动画电影则保留电影订阅基础类型。"""
    results = [
        SimpleNamespace(
            tmdb_id=901,
            title="Bangumi 真人剧",
            type=FakeMediaType.TV,
            category="剧情",
            genres=[{"id": 18, "name": "剧情"}],
            genre_ids=[18],
        ),
        SimpleNamespace(
            tmdb_id=902,
            title="动画电影",
            type=FakeMediaType.MOVIE,
            category="动画",
            genres=[{"id": 16, "name": "动画"}],
            genre_ids=[16],
        ),
    ]

    class FakeChain:
        def recognize_media(self, **kwargs):
            return results.pop(0)

    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)
    bangumi = adapter.recognize(
        Candidate(
            candidate_id="bangumi:1",
            title="Bangumi 真人剧",
            media_type="anime",
            source_ids={"bangumi": "1"},
        )
    )
    animation_movie = adapter.recognize(
        Candidate(
            candidate_id="douban:2",
            title="动画电影",
            media_type="movie",
            source_ids={"douban": "2"},
        )
    )

    assert bangumi.media_type == "tv"
    assert bangumi.metadata["mp_media_type"] == "电视剧"
    assert animation_movie.media_type == "anime"
    assert animation_movie.metadata["mp_media_type"] == "电影"


def test_recognition_rejects_media_without_tmdb_id():
    """A MoviePilot match without TMDB identity is not eligible for Agent ranking."""
    class FakeChain:
        def recognize_media(self, **kwargs):
            return SimpleNamespace(title="Bangumi only", tmdb_id=None)

    candidate = Candidate(
        candidate_id="bangumi:7",
        title="Anime",
        media_type="anime",
        source_ids={"bangumi": "7"},
    )
    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)

    assert adapter.recognize(candidate) is None


def test_enrich_cross_source_ids_adds_douban_id_for_tmdb_item():
    """TMDB 榜单条目最终展示前可补齐豆瓣 ID。"""
    calls = []

    class FakeChain:
        def get_doubaninfo_by_tmdbid(self, tmdb_id, mtype=None):
            calls.append((tmdb_id, mtype))
            return {"id": "douban-900"}

    candidate = Candidate(
        candidate_id="tmdb:tv:900",
        title="TMDB剧集",
        media_type="tv",
        source_ids={"tmdb": "900"},
    )
    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)

    assert adapter.enrich_cross_source_ids(candidate) is candidate
    assert candidate.source_ids["douban"] == "douban-900"
    assert calls == [(900, FakeMediaType.TV)]


def test_enrich_cross_source_ids_relaxes_year_when_exact_tmdb_match_is_empty():
    """严格 TMDB 映射为空时按标题执行一次无年份豆瓣匹配。"""
    calls = []

    class FakeChain:
        """记录严格与降级匹配参数。"""

        def get_doubaninfo_by_tmdbid(self, tmdb_id, mtype=None):
            """模拟严格年份匹配失败。"""
            calls.append(("exact", tmdb_id, mtype))
            return {}

        def match_doubaninfo(self, name, mtype=None, year=None):
            """模拟无年份匹配成功。"""
            calls.append(("relaxed", name, mtype, year))
            return {"id": "douban-901"}

    candidate = Candidate(
        candidate_id="tmdb:movie:901",
        title="年份漂移新片",
        media_type="movie",
        source_ids={"tmdb": "901"},
    )
    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)

    adapter.enrich_cross_source_ids(candidate)

    assert candidate.source_ids["douban"] == "douban-901"
    assert calls == [
        ("exact", 901, FakeMediaType.MOVIE),
        ("relaxed", "年份漂移新片", FakeMediaType.MOVIE, None),
    ]


def test_enrich_cross_source_ids_accepts_legacy_tmdb_alias():
    """旧榜单使用 themoviedb 别名时仍能补齐豆瓣入口。"""

    class FakeChain:
        def get_doubaninfo_by_tmdbid(self, tmdb_id, mtype=None):
            assert tmdb_id == 902
            return {"id": "douban-902"}

    candidate = Candidate(
        candidate_id="tmdb:movie:902",
        title="旧别名电影",
        media_type="movie",
        source_ids={"themoviedb": "902"},
    )
    adapter = MediaRecognitionAdapter(FakeChain, FakeMeta, FakeMediaType)

    adapter.enrich_cross_source_ids(candidate)

    assert candidate.source_ids["tmdb"] == "902"
    assert candidate.source_ids["douban"] == "douban-902"


def test_legacy_board_repair_replaces_only_broken_poster_urls():
    """Poster migration preserves ranking identity and skips already valid images."""
    assert BoardPosterRepairService._needs_repair(
        "data:image/jpeg;base64,legacy"
    )
    board = RecommendationBoard(
        profile_id="alice",
        username="alice",
        run_id="old-run",
        status="success",
        recommendations=[
            RecommendationItem(
                candidate_id="douban:7",
                rank=1,
                title="Legacy",
                media_type="tv",
                year=2026,
                source_ids={"douban": "7"},
                poster_path="https://img1.doubanio.com/legacy.webp",
                summary="Keep summary",
            ),
            RecommendationItem(
                candidate_id="tmdb:8",
                rank=2,
                title="Current",
                poster_path="https://image.tmdb.org/current.jpg",
            ),
        ],
    )

    class Repository:
        def __init__(self):
            self.saved = None

        def load_board(self, username):
            return board if username == "alice" else None

        def save_board(self, value):
            self.saved = value

    class MediaAdapter:
        def recognize(self, candidate):
            candidate.poster_path = "https://image.tmdb.org/repaired.jpg"
            return candidate

    repository = Repository()
    result = BoardPosterRepairService(repository, MediaAdapter()).repair_profiles(
        ["alice"]
    )

    assert result == {"alice": 1}
    assert repository.saved is board
    assert board.recommendations[0].candidate_id == "douban:7"
    assert board.recommendations[0].summary == "Keep summary"
    assert board.recommendations[0].poster_path.endswith("repaired.jpg")
    assert board.recommendations[1].poster_path.endswith("current.jpg")


def test_legacy_board_source_repair_persists_douban_id():
    """旧榜单中的 TMDB 条目应在重载修复时补齐豆瓣 ID。"""
    item = RecommendationItem(
        candidate_id="tmdb:movie:99",
        rank=1,
        title="Existing",
        media_type="movie",
        source_ids={"tmdb": "99"},
    )
    board = RecommendationBoard(
        profile_id="alice",
        run_id="old-run",
        recommendations=[item],
    )

    class Repository:
        """提供最小榜单读写桩。"""

        def __init__(self):
            self.saved = None

        def load_board(self, profile_id):
            """返回指定画像的榜单。"""
            return board if profile_id == "alice" else None

        def save_board(self, value):
            """记录榜单保存。"""
            self.saved = value

    class MediaAdapter:
        """提供最小跨源补链桩。"""

        def enrich_cross_source_ids(self, value):
            """写入豆瓣 ID。"""
            value.source_ids["douban"] = "db-99"
            return value

    repository = Repository()
    result = BoardSourceRepairService(repository, MediaAdapter()).repair_profiles(
        ["alice"]
    )

    assert result == {"alice": 1}
    assert repository.saved is board
    assert item.source_ids["douban"] == "db-99"


def test_recommendation_item_normalizes_legacy_source_id_aliases():
    """详情榜单兼容旧版顶层与嵌套来源 ID 字段。"""
    item = RecommendationItem.from_dict(
        {
            "candidate_id": "tmdb:tv:903",
            "rank": 1,
            "title": "旧字段剧集",
            "original_name": "Legacy Show",
            "themoviedb": "903",
            "source_ids": {"bgm_id": "bgm-903"},
        }
    )

    assert item.source_ids["tmdb"] == "903"
    assert item.source_ids["bangumi"] == "bgm-903"
    assert item.original_title == "Legacy Show"


def test_poster_image_service_returns_bounded_tmdb_thumbnail_url():
    """TMDB 原图被收敛为 w200 URL，榜单响应不再内嵌 Base64。"""
    service = PosterImageService()
    board = {
        "recommendations": [
            {
                "poster_path": (
                    "https://image.tmdb.org/t/p/original/example.jpg"
                )
            },
            {"poster_path": "https://image.example/poster.jpg"},
            {"poster_path": "data:image/jpeg;base64,oversized"},
        ]
    }

    result = service.enrich_board(board)

    assert result["recommendations"][0]["poster_path"] == (
        "https://image.tmdb.org/t/p/w200/example.jpg"
    )
    assert result["recommendations"][1]["poster_path"] == (
        "https://image.example/poster.jpg"
    )
    assert result["recommendations"][2]["poster_path"] == ""
    assert PosterImageService.thumbnail_url.cache_parameters()["maxsize"] == 512
