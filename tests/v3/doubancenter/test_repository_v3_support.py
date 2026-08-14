"""插件仓 V3 代际同步与发布映射测试。"""

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.sync_to_mp_local import sync_to_target  # noqa: E402


def test_sync_to_target_writes_only_v3_layout(tmp_path):
    """V3 同步必须写入 package.v3.json 与 plugins.v3。"""
    source = tmp_path / "source"
    target = tmp_path / "target"
    source_plugin = source / "plugins.v3" / "doubancenter"
    target_v2_plugin = target / "plugins.v2" / "doubancenter"
    source_plugin.mkdir(parents=True)
    target_v2_plugin.mkdir(parents=True)
    (target / "plugins.v3").mkdir(parents=True)
    (source / "package.v3.json").write_text(
        json.dumps({"DoubanCenter": {"name": "豆瓣中心", "version": "3.0.0"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (target / "package.v3.json").write_text("{}", encoding="utf-8")
    (target / "package.v2.json").write_text(
        json.dumps({"DoubanCenter": {"version": "1.2.20"}}),
        encoding="utf-8",
    )
    (source_plugin / "__init__.py").write_text("plugin_version = '3.0.0'\n", encoding="utf-8")
    (target_v2_plugin / "__init__.py").write_text("plugin_version = '1.2.20'\n", encoding="utf-8")

    actions = sync_to_target(
        source,
        target,
        ["DoubanCenter"],
        include_icons=False,
        generation="v3",
    )

    assert json.loads((target / "package.v3.json").read_text(encoding="utf-8"))["DoubanCenter"]["version"] == "3.0.0"
    assert json.loads((target / "package.v2.json").read_text(encoding="utf-8"))["DoubanCenter"]["version"] == "1.2.20"
    assert (target / "plugins.v3" / "doubancenter" / "__init__.py").is_file()
    assert (target_v2_plugin / "__init__.py").read_text(encoding="utf-8") == "plugin_version = '1.2.20'\n"
    assert "plugin:DoubanCenter" in actions


def test_release_workflow_maps_package_v3_to_plugins_v3():
    """Release workflow 必须按索引代际选择同代源码目录。"""
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "'package.v3.json'" in workflow
    assert 'process_package "package.v3.json" "plugins.v3"' in workflow
