from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PAGE = REPO / "plugins.v2" / "downloadmanagerlocal" / "frontend" / "src" / "components" / "Page.vue"


def _page_source() -> str:
    """读取下载中心详情页 Vue 源码。"""
    return PAGE.read_text(encoding="utf-8")


def test_downloadmanagerlocal_mobile_history_and_archive_use_cards():
    """移动端命名历史和归档记录必须有卡片列表，避免依赖表格横滑。"""
    source = _page_source()

    assert 'class="dm-mobile-list dm-history-list"' in source
    assert 'class="dm-record-card dm-history-card"' in source
    assert 'class="dm-mobile-list dm-archive-list"' in source
    assert 'class="dm-record-card dm-archive-card"' in source


def test_downloadmanagerlocal_mobile_hides_desktop_tables():
    """移动端必须隐藏桌面表格并展示卡片列表。"""
    source = _page_source()

    assert 'class="dm-table-scroll dm-desktop-table"' in source
    assert ".dm-mobile-list { display: none;" in source
    assert "@media (max-width: 760px)" in source
    assert ".dm-desktop-table { display: none; }" in source
    assert ".dm-mobile-list { display: grid;" in source


def test_downloadmanagerlocal_mobile_status_chip_keeps_full_label():
    """Mobile card status chips must not be squeezed or ellipsized."""
    source = _page_source()

    assert source.count('class="dm-record-status"') >= 2
    assert ".dm-record-status {" in source
    assert "flex: 0 0 auto;" in source
    assert ".dm-record-status :deep(.v-chip__content)" in source
    assert "overflow: visible;" in source
    assert "white-space: normal;" in source
    assert "word-break: keep-all;" in source
