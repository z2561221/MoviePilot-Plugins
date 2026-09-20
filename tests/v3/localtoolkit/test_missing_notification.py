"""缺集扫描、长报告和通知渠道格式回归。"""

from html import escape
from html.parser import HTMLParser
from types import SimpleNamespace

from app.plugins.localtoolkit.service.check_missing import CheckMissingModule
from app.plugins.localtoolkit.service.missing_report import build_missing_report


class ReportParser(HTMLParser):
    """检查完整粗体标签并收集可见文本。"""

    def __init__(self):
        """初始化标签栈和文本。"""
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        """报告只使用受支持的粗体标签。"""
        assert tag == "b"
        self.tags.append(tag)

    def handle_endtag(self, tag):
        """核对结束标签匹配。"""
        assert self.tags.pop() == tag

    def handle_data(self, data):
        """保存解码后的报告正文。"""
        self.text.append(data)


def test_large_missing_report_preserves_totals_and_explains_omissions():
    """大量含特殊字符的剧集按完整条目截断，总数和省略提示始终可见。"""
    results = [
        {"path": "动画 <&> 🔬", "title": ("剧名 <&> 🌌" * 20) + " [tmdbid=123]",
         "season": index, "missing": list(range(1, 80, 2))}
        for index in range(1, 61)
    ]
    report = build_missing_report(results, "扫描 2 个路径，缺失 2400 集")
    assert len(report.encode("utf-16-le")) // 2 <= 3200
    caption = f"<b>本地工具集 - 扫描缺集</b>\n{report}\n<a href=\"{escape('https://example.invalid/' + 'x' * 400)}\">查看详情</a>"
    assert len(caption.encode("utf-16-le")) // 2 < 4096
    parser = ReportParser()
    parser.feed(report)
    parser.close()
    assert not parser.tags
    assert "缺失 2400 集" in "".join(parser.text)
    assert "另有" in report and "项未展开" in report
    assert "32 个区间" in report
    assert "[tmdb" not in report


def test_scan_notifies_grouped_html_and_plain_without_changing_missing_results(tmp_path, monkeypatch):
    """真实临时 STRM 样本保持扫描结果，并按通知源输出合适格式。"""
    from app.sdk.services import ServiceConfigHelper

    monkeypatch.setattr(ServiceConfigHelper, "get_notification_configs", lambda: [
        SimpleNamespace(name="tg", type="telegram", enabled=True, switchs=["插件"]),
        SimpleNamespace(name="mail", type="email", enabled=True, switchs=["插件"]),
    ])
    root = tmp_path / "library"
    folder = root / "动画 & 剧集" / "示例剧 [tmdbid=1]"
    folder.mkdir(parents=True)
    for name in ["Show.S01E01.strm", "Show.S01E03.strm", "Show.S02E02.strm", "Show.S02E04.strm"]:
        (folder / name).write_text("https://example.invalid/media", encoding="utf-8")
    messages = []
    data = {}
    plugin = SimpleNamespace(
        post_message=lambda **kwargs: messages.append(kwargs),
        get_data=lambda key: data.get(key),
        save_data=lambda key, value: data.update({key: value}),
    )
    module = CheckMissingModule(plugin)
    module.load_config({"notify": True, "scan_paths": [str(root), str(tmp_path / "absent")]})
    result = module.run_once()
    assert result["success"] is True and result["missing_total"] == 3
    assert [item["missing"] for item in data["check_missing_result"] if item.get("season")] == [[2], [1, 3]]
    assert len(messages) == 3
    telegram, email, history = messages
    assert telegram["parse_mode"] == "HTML" and telegram["source"] == "tg"
    assert "<b>示例剧 · S01</b>\n缺集：2" in telegram["text"]
    assert "<b>示例剧 · S02</b>\n缺集：1, 3" in telegram["text"]
    assert "动画 &amp; 剧集" in telegram["text"]
    assert "路径不存在，未能扫描" in telegram["text"]
    assert email["parse_mode"] == "plain" and "<b>" not in email["text"]
    assert "动画 & 剧集" in email["text"]
    assert history["parse_mode"] == "plain"
    module.send_notification("清理 TMDB 缓存", "清理完成：8 个缓存键")
    assert len(messages) == 4 and messages[-1]["parse_mode"] == "plain"


def test_season_subdirectory_is_scanned_when_series_root_has_no_direct_file(tmp_path):
    """剧集根目录没有海报或视频文件时，季目录 STRM 仍参与缺集判断。"""
    root = tmp_path / "library"
    season = root / "动画" / "示例剧" / "Season 1"
    season.mkdir(parents=True)
    for name in ("Show.S01E01.strm", "Show.S01E03.strm"):
        (season / name).write_text("https://example.invalid/media", encoding="utf-8")
    data = {}
    plugin = SimpleNamespace(
        post_message=lambda **_kwargs: None,
        get_data=lambda key: data.get(key),
        save_data=lambda key, value: data.update({key: value}),
    )
    module = CheckMissingModule(plugin)
    module.load_config({"notify": False, "scan_paths": [str(root)]})
    result = module.run_once()
    assert result["missing_total"] == 1
    assert data["check_missing_result"][0]["missing"] == [2]
