"""验证下载中心 V3 版本例外和仓库发布门禁。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / ".github/scripts/check_plugin_versions.py"
PR_WORKFLOW = REPO_ROOT / ".github/workflows/plugin-gate.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github/workflows/release.yml"
TEST_RUNNER = REPO_ROOT / "tests/run.py"


def _write_v3_fixture(
    repo: Path,
    *,
    plugin_id: str = "DownloadManagerLocal",
    legacy_version: str = "3.2.9",
    v3_version: str = "3.3.0",
    exception_id: str | None = "DownloadManagerLocal",
    exception_legacy: str = "3.2.9",
    exception_v3: str = "3.3.0",
) -> None:
    """构造一个最小 V3 仓库，隔离验证精确版本例外。"""
    plugin_dir = repo / "plugins.v3" / plugin_id.lower()
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "__init__.py").write_text(
        f"class {plugin_id}:\n    plugin_version = '{v3_version}'\n",
        encoding="utf-8",
    )
    (repo / "package.json").write_text("{}\n", encoding="utf-8")
    (repo / "package.v2.json").write_text(
        json.dumps({plugin_id: {"version": legacy_version, "v3": False}}),
        encoding="utf-8",
    )
    (repo / "package.v3.json").write_text(
        json.dumps(
            {
                plugin_id: {
                    "version": v3_version,
                    "system_version": ">=3.0.0",
                    "history": {f"v{v3_version}": "迁移"},
                }
            }
        ),
        encoding="utf-8",
    )
    if exception_id:
        exceptions_path = repo / ".github/v3-version-exceptions.json"
        exceptions_path.parent.mkdir(parents=True)
        exceptions_path.write_text(
            json.dumps(
                {
                    exception_id: {
                        "legacy_version": exception_legacy,
                        "v3_version": exception_v3,
                        "reason": "user-approved same-major V3 migration",
                    }
                }
            ),
            encoding="utf-8",
        )


def _run_checker(repo: Path) -> subprocess.CompletedProcess[str]:
    """从夹具仓运行真实版本检查器。"""
    return subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "package.json",
            "package.v2.json",
            "package.v3.json",
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def test_checker_accepts_download_manager_exact_exception(tmp_path: Path) -> None:
    """只允许已登记的下载中心 3.2.9 到 3.3.0 迁移。"""
    _write_v3_fixture(tmp_path)

    result = _run_checker(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_rejects_exception_target_mismatch(tmp_path: Path) -> None:
    """V3 package 偏离登记目标版本时必须失败。"""
    _write_v3_fixture(tmp_path, v3_version="3.3.1")

    result = _run_checker(tmp_path)

    assert result.returncode == 1
    assert "例外目标与 package 版本不一致" in result.stdout


def test_checker_rejects_exception_for_other_plugin(tmp_path: Path) -> None:
    """下载中心例外不能被其他插件借用。"""
    _write_v3_fixture(
        tmp_path,
        plugin_id="OtherPlugin",
        exception_id="DownloadManagerLocal",
    )

    result = _run_checker(tmp_path)

    assert result.returncode == 1
    assert "不存在对应 V3 条目" in result.stdout
    assert "V3 版本应从旧代 3.2.9 跃迁至 4.0.0" in result.stdout


def test_checker_keeps_default_next_major_rule(tmp_path: Path) -> None:
    """无例外插件仍必须按默认规则跃迁下一主版本。"""
    _write_v3_fixture(
        tmp_path,
        plugin_id="OtherPlugin",
        legacy_version="2.6.1",
        v3_version="2.6.2",
        exception_id=None,
    )

    result = _run_checker(tmp_path)

    assert result.returncode == 1
    assert "V3 版本应从旧代 2.6.1 跃迁至 3.0.0" in result.stdout


def test_current_repository_passes_version_gate() -> None:
    """真实工作树中的 package 与插件版号必须一致。"""
    result = _run_checker(REPO_ROOT)

    assert result.returncode == 0, result.stdout + result.stderr


def test_workflows_and_runner_include_v3_gate() -> None:
    """PR、Release 与全量测试入口都必须覆盖 V3。"""
    pr_workflow = PR_WORKFLOW.read_text(encoding="utf-8")
    release_workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    runner = TEST_RUNNER.read_text(encoding="utf-8")

    checker_command = (
        "python .github/scripts/check_plugin_versions.py "
        "package.json package.v2.json package.v3.json"
    )
    assert checker_command in pr_workflow
    assert checker_command in release_workflow
    assert "package.v3.json" in release_workflow
    assert 'for generation in ("ci", "v3", "v2", "v1"):' in runner

