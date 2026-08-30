"""验证 MoviePilot V3 插件试行评分规则。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCORER = REPO_ROOT / ".github/scripts/score_plugin_quality.py"


def _load_scorer():
    """从脚本路径加载评分器。"""
    spec = importlib.util.spec_from_file_location("plugin_quality_scorer", SCORER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_fixture(repo: Path, *, source_extra: str = "") -> None:
    """写入一个满足静态合同的最小 V3 插件仓夹具。"""
    plugin_dir = repo / "plugins.v3/exampleplugin"
    tests_dir = repo / "tests/v3/exampleplugin"
    plugin_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)
    (plugin_dir / "__init__.py").write_text(
        '''"""示例插件。"""

class ExamplePlugin:
    """提供评分夹具。"""

    plugin_name = "示例插件"
    plugin_desc = "用于验证评分器。"
    plugin_icon = "example.png"
    plugin_version = "1.0.0"
    plugin_author = "Kurisu"
    auth_level = 1
\n'''
        + source_extra
        + '''
    def init_plugin(self, config=None):
        """初始化插件。"""
        self.config = config or {}

    def stop_service(self):
        """释放插件资源。"""
        self.config = {}
''',
        encoding="utf-8",
    )
    (plugin_dir / "README.md").write_text("# 示例插件\n", encoding="utf-8")
    (tests_dir / "test_plugin.py").write_text(
        '''def test_one():
    assert True

def test_two():
    assert True

def test_three():
    assert True
''',
        encoding="utf-8",
    )
    (repo / "package.v3.json").write_text(
        json.dumps(
            {
                "ExamplePlugin": {
                    "name": "示例插件",
                    "description": "用于验证评分器。",
                    "version": "1.0.0",
                    "icon": "example.png",
                    "author": "Kurisu",
                    "level": 1,
                    "system_version": ">=3.0.0",
                    "history": {"v1.0.0": "初始版本"},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_static_trial_score_is_capped_at_eight(tmp_path: Path) -> None:
    """L1 静态证据可以给出规范质量分，但不伪造运行态证据。"""
    scorer = _load_scorer()
    _write_fixture(tmp_path)

    report = scorer.score_repository(tmp_path)[0]

    assert report["rule_version"] == "3.0.2"
    assert report["quality_score"] == 10.0
    assert report["quality_max_score"] == 9.0
    assert "gated_score" not in report
    assert "score_cap" not in report
    assert report["evidence_level"] == "L1"
    assert report["readiness"] == "static_only"
    assert report["blocker_count"] == 0


def test_reviewed_internal_import_exception_is_machine_audited(tmp_path: Path) -> None:
    """有完整审计字段的逐符号内部导入例外不应被重复扣分。"""
    scorer = _load_scorer()
    _write_fixture(
        tmp_path,
        source_extra="    from app.adapters.external.cookiecloud import CookieCloudHelper\n",
    )
    exceptions = tmp_path / ".github/plugin-quality-exceptions.json"
    exceptions.parent.mkdir(parents=True, exist_ok=True)
    exceptions.write_text(
        json.dumps(
            {
                "ExamplePlugin": {
                    "imports": [
                        {
                            "module": "app.adapters.external.cookiecloud",
                            "symbol": "CookieCloudHelper",
                            "reason": "当前 V3 宿主尚未提供稳定 SDK 出口。",
                            "host_version": "test-host",
                            "removal_condition": "稳定 SDK 导出 CookieCloudHelper 后移除。",
                            "test": "tests/test_plugin.py::test_one",
                        }
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = scorer.score_repository(tmp_path)[0]

    internal = next(
        item for item in report["checks"] if item["check_id"] == "contract.internal_imports"
    )
    assert internal["status"] == "pass"
    assert internal["points"] == internal["max_points"] == 0.4


def test_forbidden_v3_import_creates_blocker(tmp_path: Path) -> None:
    """V3 禁用导入必须成为阻断项。"""
    scorer = _load_scorer()
    _write_fixture(tmp_path, source_extra="    from app.core.config import settings\n")

    report = scorer.score_repository(tmp_path)[0]

    assert "contract.forbidden_imports" in report["blockers"]
    assert report["readiness"] == "blocked"
    assert report["quality_score"] < 10.0


def test_host_session_import_is_a_v3_contract_blocker(tmp_path: Path) -> None:
    """宿主内部会话入口与 ORM Model 一样必须阻断。"""
    scorer = _load_scorer()
    _write_fixture(tmp_path, source_extra="    from app.db import ScopedSession\n")

    report = scorer.score_repository(tmp_path)[0]

    assert "contract.internal_imports" in report["blockers"]
    assert report["quality_score"] < 10.0


def test_unreviewed_internal_import_is_a_contract_blocker(tmp_path: Path) -> None:
    """未登记的宿主内部导入必须阻断评分。"""
    scorer = _load_scorer()
    _write_fixture(
        tmp_path,
        source_extra="    from app.adapters.external.cookiecloud import OtherHelper\n",
    )

    report = scorer.score_repository(tmp_path)[0]

    internal = next(
        item for item in report["checks"] if item["check_id"] == "contract.internal_imports"
    )
    assert "contract.internal_imports" in report["blockers"]
    assert internal["status"] == "blocked"
    assert report["readiness"] == "blocked"


def test_empty_stop_service_is_valid_without_owned_resources(tmp_path: Path) -> None:
    """没有插件自有长期资源时，幂等空 stop_service 不应被扣分。"""
    scorer = _load_scorer()
    _write_fixture(tmp_path)
    init_file = tmp_path / "plugins.v3/exampleplugin/__init__.py"
    init_file.write_text(
        init_file.read_text(encoding="utf-8").replace(
            "        self.config = {}\n", "        return None\n"
        ),
        encoding="utf-8",
    )

    report = scorer.score_repository(tmp_path)[0]
    cleanup = next(item for item in report["checks"] if item["check_id"] == "lifecycle.cleanup")

    assert cleanup["status"] == "pass"
    assert cleanup["points"] == cleanup["max_points"] == 0.4


def test_hardcoded_secret_is_reported_without_echoing_value(tmp_path: Path) -> None:
    """疑似硬编码凭据必须阻断，报告不能回显凭据内容。"""
    scorer = _load_scorer()
    secret = "sk-live-1234567890abcdef"
    _write_fixture(tmp_path, source_extra=f'    api_key = "{secret}"\n')

    report = scorer.score_repository(tmp_path)[0]
    serialized = json.dumps(report, ensure_ascii=False)

    assert "security.secret_literals" in report["blockers"]
    assert secret not in serialized


def test_json_cli_output_contains_rule_and_tree_hash(tmp_path: Path, capsys) -> None:
    """JSON 输出必须携带规则版本和评分输入哈希。"""
    scorer = _load_scorer()
    _write_fixture(tmp_path)

    exit_code = scorer.main(["--repo", str(tmp_path), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["rule_version"] == "3.0.2"
    assert len(payload["reports"][0]["tree_sha256"]) == 64


def test_current_repository_can_score_all_v3_plugins() -> None:
    """真实仓库所有 V3 package 条目都必须能生成报告。"""
    scorer = _load_scorer()

    reports = scorer.score_repository(REPO_ROOT)

    package = json.loads((REPO_ROOT / "package.v3.json").read_text(encoding="utf-8"))
    assert {report["plugin_id"] for report in reports} == set(package)
    assert all(report["evidence_level"] == "L1" for report in reports)
