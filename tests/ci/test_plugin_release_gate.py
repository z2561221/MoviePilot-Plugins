"""验证仓库 V3 版本白名单和发布门禁。"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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
    exception_mode: str = "migration",
    include_legacy: bool = True,
) -> None:
    """构造一个最小 V3 仓库，隔离验证精确版本例外。"""
    plugin_dir = repo / "plugins.v3" / plugin_id.lower()
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "__init__.py").write_text(
        f"class {plugin_id}:\n    plugin_version = '{v3_version}'\n",
        encoding="utf-8",
    )
    (repo / "package.json").write_text("{}\n", encoding="utf-8")
    legacy_package = (
        {plugin_id: {"version": legacy_version, "v3": False}}
        if include_legacy
        else {}
    )
    (repo / "package.v2.json").write_text(
        json.dumps(legacy_package), encoding="utf-8"
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
        policy = {
            "mode": exception_mode,
            "v3_version": exception_v3,
            "reason": "user-approved MoviePilot V3 version line",
        }
        if exception_mode == "migration":
            policy["legacy_version"] = exception_legacy
        exceptions_path.write_text(
            json.dumps({exception_id: policy}), encoding="utf-8"
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


def test_checker_requires_migration_source(tmp_path: Path) -> None:
    """迁移类白名单必须精确绑定真实旧代条目。"""
    _write_v3_fixture(
        tmp_path,
        include_legacy=False,
    )

    result = _run_checker(tmp_path)

    assert result.returncode == 1
    assert "迁移例外缺少旧代条目" in result.stdout


def test_checker_accepts_explicit_v3_only_plugin(tmp_path: Path) -> None:
    """全新 V3-only 插件无需伪造旧代条目。"""
    _write_v3_fixture(
        tmp_path,
        plugin_id="BackupCenter",
        v3_version="3.0.0",
        exception_id="BackupCenter",
        exception_v3="3.0.0",
        exception_mode="v3_only",
        include_legacy=False,
    )

    result = _run_checker(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_rejects_legacy_entry_for_v3_only_plugin(tmp_path: Path) -> None:
    """V3-only 分类必须反向阻止旧代条目残留。"""
    _write_v3_fixture(
        tmp_path,
        plugin_id="BackupCenter",
        legacy_version="0.0.1",
        v3_version="3.0.0",
        exception_id="BackupCenter",
        exception_v3="3.0.0",
        exception_mode="v3_only",
    )

    result = _run_checker(tmp_path)

    assert result.returncode == 1
    assert "已声明 V3-only，不得保留旧代条目" in result.stdout


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


@pytest.mark.parametrize("minimum", [">=3.0.0", ">=3.1.3", ">=3.12.0"])
def test_new_v3_only_classification_accepts_truthful_host_minimum(tmp_path, minimum):
    _write_v3_fixture(tmp_path, plugin_id="NewPet", v3_version="1.0.0",
                      exception_id=None, include_legacy=False)
    path = tmp_path / "package.v3.json"
    package = json.loads(path.read_text("utf-8"))
    package["NewPet"].update(v3_only=True, system_version=minimum)
    path.write_text(json.dumps(package), encoding="utf-8")
    result = _run_checker(tmp_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("minimum", [">=2.9.0", ">=4.0.0", "3.1.3", ">=3.1.3,<4", ""])
def test_invalid_v3_host_minimum_still_fails(tmp_path, minimum):
    _write_v3_fixture(tmp_path)
    path = tmp_path / "package.v3.json"
    package = json.loads(path.read_text("utf-8"))
    package["DownloadManagerLocal"]["system_version"] = minimum
    path.write_text(json.dumps(package), encoding="utf-8")
    assert _run_checker(tmp_path).returncode == 1


def test_new_classification_cannot_bypass_legacy_migration(tmp_path):
    _write_v3_fixture(tmp_path, plugin_id="OtherPlugin", exception_id=None)
    path = tmp_path / "package.v3.json"
    package = json.loads(path.read_text("utf-8"))
    package["OtherPlugin"]["v3_only"] = True
    path.write_text(json.dumps(package), encoding="utf-8")
    result = _run_checker(tmp_path)
    assert result.returncode == 1
    assert "不得保留旧代条目" in result.stdout


def test_agentmascot_frontend_is_built_tested_and_checked_for_drift():
    steps = yaml.safe_load(PR_WORKFLOW.read_text("utf-8"))["jobs"]["plugin-release-gate"]["steps"]
    step = next(item for item in steps if item.get("working-directory") == "plugins.v3/agentmascot")
    for command in ["npm ci", "npm run build", "npm test", "git diff --exit-code -- dist", "git ls-files --others"]:
        assert command in step["run"]


def test_current_repository_passes_version_gate() -> None:
    """真实工作树中的 package 与插件版号必须一致。"""
    result = _run_checker(REPO_ROOT)

    assert result.returncode == 0, result.stdout + result.stderr


def test_current_repository_has_only_approved_v3_version_policies() -> None:
    """第三方 3.x 版号例外必须严格限于用户批准的四个插件。"""
    policies = json.loads(
        (REPO_ROOT / ".github/v3-version-exceptions.json").read_text(
            encoding="utf-8"
        )
    )

    assert set(policies) == {
        "DownloadManagerLocal",
        "DoubanCenter",
        "AgentRank",
        "BackupCenter",
    }
    assert policies["BackupCenter"]["mode"] == "v3_only"
    assert all(policy["v3_version"].startswith("3.") for policy in policies.values())


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


def test_release_workflow_keeps_existing_releases_immutable() -> None:
    """同版目录有后续改动时也不得删除并重建历史 Release。"""
    release_workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert 'git show-ref --tags --verify --quiet "refs/tags/$tag"' in release_workflow
    assert "verify_release_assets.py" in release_workflow
    assert 'gh release delete "$tag"' not in release_workflow
    assert 'git push origin :refs/tags/"$tag"' not in release_workflow


def test_manual_release_is_limited_to_main_and_serialized():
    """Manual runs cannot publish a business branch or race another release."""
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    assert workflow["jobs"]["release"]["if"] == "github.ref == 'refs/heads/main'"
    assert workflow["concurrency"] == {
        "group": "plugin-release", "cancel-in-progress": False
    }


def test_frontend_node_tests_are_part_of_the_required_gate():
    """The mandatory version gate also runs frontend instance-routing tests."""
    workflow = yaml.safe_load(PR_WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["plugin-release-gate"]["steps"]
    assert any(step.get("run") == "node --test tests/v3/*/*.test.mjs" for step in steps)


@pytest.mark.parametrize(
    "plugin_dir", sorted((REPO_ROOT / "plugins.v3").glob("*/frontend/package.json")),
    ids=lambda path: path.parents[1].name,
)
def test_frontend_built_references_exist(plugin_dir: Path):
    """Every packaged Vue entry must resolve its JS and CSS dependencies."""
    _assert_frontend_built_references(plugin_dir.parents[1] / "dist")


def _assert_frontend_built_references(dist: Path):
    """按引用文件所在目录解析相对依赖，内容版本目录不回退到旧根资源。"""
    assets = dist / "assets"
    pending = [dist / "index.html", assets / "remoteEntry.js"]
    visited = set()
    pattern = re.compile(
        r"((?:\./|/assets/)[^\"'()]+\.(?:js|css))|"
        r"[\"']([^\"']+\.css)[\"']"
    )
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        assert current.is_file(), f"Missing frontend entry: {current}"
        visited.add(current)
        for match in pattern.findall(current.read_text(encoding="utf-8")):
            name = next(part for part in match if part)
            asset = dist / name.lstrip("/") if name.startswith("/assets/") else current.parent / name
            asset = asset.resolve()
            assert asset.is_relative_to(dist.resolve()), f"Asset escapes dist: {name}"
            assert asset.is_file(), f"Missing asset in {current.name}: {name}"
            if asset.suffix == ".js":
                pending.append(asset)


@pytest.mark.parametrize("missing", [None, "Config.js", "Config.css"])
def test_versioned_frontend_dependencies_resolve_beside_entry(tmp_path: Path, missing: str | None):
    """内容目录的依赖必须实际存在；同名旧根资源不能掩盖丢失文件。"""
    dist = tmp_path / "dist"
    assets = dist / "assets"
    revision = assets / "r1"
    revision.mkdir(parents=True)
    (dist / "index.html").write_text('<script src="/assets/remoteEntry.js"></script>', encoding="utf-8")
    (assets / "remoteEntry.js").write_text("export * from './r1/remoteEntry.js';", encoding="utf-8")
    (revision / "remoteEntry.js").write_text(
        'dynamicLoadingCss(["Config.css"]); import("./Config.js");', encoding="utf-8"
    )
    for name in ["Config.js", "Config.css"]:
        (assets / name).write_text("", encoding="utf-8")
        if name != missing:
            (revision / name).write_text("", encoding="utf-8")
    if missing:
        with pytest.raises(AssertionError, match=f"Missing asset.*{re.escape(missing)}"):
            _assert_frontend_built_references(dist)
    else:
        _assert_frontend_built_references(dist)
