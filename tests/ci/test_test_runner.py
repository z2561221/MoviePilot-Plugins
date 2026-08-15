"""验证插件仓分代测试 runner 的源码边界。"""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_test_runner_module():
    """从脚本路径加载分代测试 runner。"""
    script = REPO_ROOT / "tests/run.py"
    spec = importlib.util.spec_from_file_location("plugin_test_runner", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_skips_orphaned_generation_tests(tmp_path: Path, capsys) -> None:
    """分代 runner 只收集存在同代插件源码的测试目录。"""
    module = _load_test_runner_module()
    tests_dir = tmp_path / "tests"
    repo_root = tmp_path
    valid_tests = tests_dir / "v3/downloadmanagerlocal"
    orphan_tests = tests_dir / "v3/orphanplugin"
    plugin_source = repo_root / "plugins.v3/downloadmanagerlocal"
    valid_tests.mkdir(parents=True)
    orphan_tests.mkdir(parents=True)
    plugin_source.mkdir(parents=True)
    (valid_tests / "test_ok.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    (orphan_tests / "test_orphan.py").write_text(
        "def test_orphan(): pass\n",
        encoding="utf-8",
    )

    targets = module._generation_targets(
        "v3",
        tests_dir=tests_dir,
        repo_root=repo_root,
    )

    assert targets == [valid_tests]
    assert "跳过无源码测试目录" in capsys.readouterr().err
