"""观影分季回归使用的隔离媒体样本和存储替身。"""

import copy
import threading
from types import SimpleNamespace

from app.schemas.types import MediaSource, MediaType


def huanzhu_media():
    """还珠的源媒体覆盖多部，豆瓣按部收录。"""
    seasons = [
        {"season_number": 1, "air_date": "1998-04-28", "episode_count": 24, "poster_path": "/hz1.jpg"},
        {"season_number": 2, "air_date": "1999-04-21", "episode_count": 48, "poster_path": "/hz2.jpg"},
    ]
    return SimpleNamespace(
        media_source=MediaSource.TMDB, media_id="4285", type=MediaType.TV,
        title="还珠格格", year="1998", first_air_date="1998-04-28", season=1,
        poster_path="https://image.tmdb.org/t/p/original/series.jpg",
        tmdb_info={"seasons": seasons, "number_of_episodes": 192, "first_air_date": "1998-04-28"},
        season_info=seasons, seasons={1: list(range(1, 25)), 2: list(range(1, 49))},
        season_years={1: "1998", 2: "1999"}, episode_group=None, episode_groups=[],
    )


def mushoku_media():
    """剧集组第 3 季含第 2 季序章，保留宿主原始季字段。"""
    seasons = [
        {"season_number": 1, "air_date": "2021-01-11", "episode_count": 23, "poster_path": "/mt1.jpg"},
        {"season_number": 2, "air_date": "2023-07-10", "episode_count": 24, "poster_path": "/mt2.jpg"},
    ]
    groups = [
        {"order": 1, "episodes": [{"air_date": "2021-01-11", "season_number": 1}]},
        {"order": 2, "episodes": [{"air_date": "2021-10-04", "season_number": 1}]},
        {"order": 3, "episodes": [
            {"air_date": "2023-07-03", "season_number": 0},
            {"air_date": "2023-07-10", "season_number": 2},
        ]},
    ]
    return SimpleNamespace(
        media_source=MediaSource.TMDB, media_id="94664", type=MediaType.TV,
        title="无职转生～到了异世界就拿出真本事～", year="2021", season=1,
        poster_path="https://image.tmdb.org/t/p/original/series.jpg",
        tmdb_info={"seasons": seasons, "number_of_episodes": 61, "first_air_date": "2021-01-11"},
        season_info=groups, seasons={1: list(range(1, 12)), 2: list(range(1, 13)), 3: list(range(1, 14))},
        season_years={1: "2021", 2: "2021", 3: "2023"},
        episode_group="61d225784d0e8d0069c57beb", episode_groups=groups,
    )


HUANZHU_SUBJECTS = [
    {"id": "1786739", "title": "还珠格格", "year": "1998", "type": "tv", "is_tv": True,
     "episodes_count": 24, "pubdate": ["1998-10-28(中国大陆)", "1998-04-28(中国台湾)"]},
    {"id": "1786740", "title": "还珠格格第二部", "year": "1999", "type": "tv", "is_tv": True,
     "episodes_count": 48, "pubdate": ["1999-07-25(中国大陆)", "1999-04-21(中国台湾)"]},
]

MUSHOKU_SUBJECTS = [
    {"id": "30513783", "title": "无职转生：到了异世界就拿出真本事", "year": "2021",
     "type": "tv", "is_tv": True, "episodes_count": 11, "pubdate": ["2021-01-10(日本)"]},
    {"id": "35306636", "title": "无职转生：到了异世界就拿出真本事 Part.2", "year": "2021",
     "type": "tv", "is_tv": True, "episodes_count": 12, "pubdate": ["2021-10-03(日本)"]},
    {"id": "35460731", "title": "无职转生Ⅱ 到了异世界就拿出真本事 Part.1", "year": "2023",
     "type": "tv", "is_tv": True, "episodes_count": 13, "pubdate": ["2023-07-02(日本)"]},
]


class FolioMediaChain:
    """模拟整剧 IMDb 总命中首部，而搜索能找到各独立分季。"""

    def __init__(self, media, subjects):
        """保存固定媒体与详情，不访问宿主或网络。"""
        self.media = media
        self.subjects = copy.deepcopy(subjects)
        self.convert_calls = []

    def convert_media_identity(self, **kwargs):
        """仅模拟正向转换，反向同名消歧默认无证据。"""
        self.convert_calls.append(kwargs)
        return self.subjects[0] if kwargs["target_source"] == MediaSource.Douban and self.subjects else None

    def search_medias(self, meta, media_source=None):
        """返回与宿主搜索结果相同的统一身份对象。"""
        return [SimpleNamespace(media_source=MediaSource.Douban, media_id=item["id"],
                                title=item["title"], year=item.get("year"),
                                type=MediaType.TV if item.get("is_tv") else MediaType.MOVIE)
                for item in self.subjects]

    def douban_info(self, doubanid, mtype=None):
        """按 ID 返回完整豆瓣详情。"""
        return next((item for item in self.subjects if item["id"] == doubanid), None)

    def recognize_media(self, **kwargs):
        """模拟指定源身份与剧集组的媒体加载。"""
        return self.media if kwargs["media_id"] == self.media.media_id else None


class FolioPlugin:
    """可验证持久化和锁语义的插件替身。"""

    plugin_version = "3.0.6"

    def __init__(self, data=None, data_path=None):
        """隔离原始档案及备份目录。"""
        self.data = {"folio_data": copy.deepcopy(data or {})}
        self.data_path = data_path
        self._sync_lock = threading.Lock()
        self._folio_repair_plans = {}
        self._folio_cookie = "test-cookie"
        self._folio_private = True
        self._folio_notify = False
        self._wait_process = {}

    def get_data(self, key, plugin_id=""):
        """返回独立快照，模拟实际序列化存储。"""
        return copy.deepcopy(self.data.get(key))

    def save_data(self, key, value):
        """记录明确提交的数据。"""
        self.data[key] = copy.deepcopy(value)

    def get_data_path(self):
        """返回测试临时目录。"""
        return self.data_path
