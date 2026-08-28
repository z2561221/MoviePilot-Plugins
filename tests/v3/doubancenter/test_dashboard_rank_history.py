"""豆瓣中心榜单响应展示测试。"""

from types import SimpleNamespace

from app.plugins.doubancenter.service import dashboard_rank_history


def test_rank_history_response_uses_chinese_legacy_original_title_without_mutating_storage():
    """旧记录标题颠倒时仅在响应副本恢复豆瓣中文名。"""
    stored = {
        "title": "Marble Hall Murders",
        "original_title": "翠鸟谋杀案",
        "tmdb_title": "Marble Hall Murders",
        "media_source": "themoviedb",
        "media_id": "283319",
    }
    plugin = SimpleNamespace(_dashboard_rank_keys=["coming"])

    response = dashboard_rank_history.build_rank_history_response(
        plugin,
        lambda current, key, limit: [stored],
    )

    assert response["data"]["coming"][0]["title"] == "翠鸟谋杀案"
    assert response["data"]["coming"][0]["tmdb_title"] == "Marble Hall Murders"
    assert stored["title"] == "Marble Hall Murders"
    assert stored["original_title"] == "翠鸟谋杀案"


def test_rank_history_response_does_not_swap_bangumi_original_title():
    """Bangumi 的日文原名不能被误当成豆瓣中文标题。"""
    stored = {
        "title": "Re:Zero Fourth Season",
        "original_title": "Re:ゼロから始める異世界生活 4th season",
    }
    plugin = SimpleNamespace(_dashboard_rank_keys=["bangumi"])

    response = dashboard_rank_history.build_rank_history_response(
        plugin,
        lambda current, key, limit: [stored],
    )

    assert response["data"]["bangumi"][0]["title"] == stored["title"]
