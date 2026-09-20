from datetime import datetime, timezone
from html.parser import HTMLParser

from app.plugins.localtoolkit.adapter.cleanup_notification import plain_report
from app.plugins.localtoolkit.model.library_cleanup import (
    CleanupCandidate,
    CleanupCondition,
    CleanupResult,
    CleanupVerification,
)
from app.plugins.localtoolkit.service.cleanup_report import build_report

NOW = datetime(2026, 9, 8, tzinfo=timezone.utc)


def movie(number=1, title="电影 <测试> & 特别篇"):
    return CleanupCandidate(
        movie_id=str(number), title=title, date_created="2026-01-01T00:00:00Z",
        server="emby", library_id="movies",
    )


def report_result(movies):
    return CleanupResult([CleanupCondition(1)], movies)


class TagChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.open_tags = []

    def handle_starttag(self, tag, attrs):
        assert tag == "b"
        assert not attrs
        self.open_tags.append(tag)

    def handle_endtag(self, tag):
        assert self.open_tags.pop() == tag


def test_report_escapes_titles_and_preserves_same_body_in_every_phase():
    candidate = movie()
    result = report_result([candidate])
    reports = [
        build_report({"auto_delete": True}, result, "", NOW, phase=phase,
                     verification=CleanupVerification(removed=[candidate]))
        for phase in ["deleting", "verifying", "finished"]
    ]
    assert len({text.split("<b>本轮清理结果</b>")[0] for text in reports}) == 1
    assert "电影 &lt;测试&gt; &amp; 特别篇" in reports[0]
    assert "｜2026-01-01" in reports[0] and "入库时长：" not in reports[0]
    assert "\n\n<b>02." not in reports[0]
    assert "**" not in reports[0] and "```" not in reports[0]
    assert "正在清理" in reports[0] and "正在复核" in reports[1]
    assert "确认移除：1 部" in reports[2] and "✅ 本轮删除完毕" in reports[2]
    assert "电影 <测试> & 特别篇" in plain_report(reports[2])


def test_remaining_and_unknown_items_cannot_claim_completion():
    candidates = [movie(i, f"电影 {i}") for i in range(3)]
    text = build_report(
        {"auto_delete": True}, report_result(candidates), "", NOW,
        phase="finished", verification=CleanupVerification(
            removed=candidates[:1], remaining=candidates[1:2], unknown=candidates[2:],
        ),
    )
    assert "✅ 本轮删除完毕" not in text
    assert "仍然存在：1 部" in text and "无法核验：1 部" in text
    assert "电影 1：仍然存在" in text and "电影 2：无法核验" in text


def test_long_html_and_emoji_report_stays_in_one_message_without_cutting_tags():
    candidates = [movie(i, "<&>😀" * 80) for i in range(50)]
    result = report_result(candidates)
    verification = CleanupVerification(remaining=candidates[:25], unknown=candidates[25:])
    text = build_report({"auto_delete": True}, result, "", NOW,
                        phase="finished", verification=verification)
    checker = TagChecker()
    checker.feed(text)
    assert checker.open_tags == []
    assert len(text.encode("utf-16-le")) // 2 < 3800
    assert "本轮目标：50 部" in text
    assert "仍然存在：25 部" in text and "无法核验：25 部" in text
    assert "未展开" in text
    assert text.endswith("核验范围：媒体库条目")


def test_check_only_summary_cannot_inject_html():
    text = build_report({}, report_result([]), "<b>演练</b> & 未删除", NOW)
    assert "&lt;b&gt;演练&lt;/b&gt; &amp; 未删除" in text
    assert "本轮删除完毕" not in text
