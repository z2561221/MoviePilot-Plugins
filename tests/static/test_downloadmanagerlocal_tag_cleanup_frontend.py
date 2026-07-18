from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "plugins.v2" / "downloadmanagerlocal" / "frontend" / "src" / "components" / "Config.vue"


def test_frontend_exposes_keep_first_cleanup_workflow():
    """标签清理界面必须默认保留，并经预览后提交明确快照。"""
    source = CONFIG.read_text(encoding="utf-8")

    assert "{ key: 'tag_cleanup', title: '标签清理'" in source
    assert "cleanupKeep[tagSelectionKey(group.name, item.tag)] = true" in source
    assert "previewCleanupTags" in source
    assert "tag_cleanup_scan" in source
    assert "tag_cleanup_execute" in source
