"""Run the DoubanCenter focused suite and enforce branch-coverage thresholds."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_THRESHOLDS = REPO_ROOT / ".github" / "doubancenter-coverage-thresholds.json"


def _run(command: list[str], env: dict[str, str]) -> None:
    process = subprocess.run(command, cwd=REPO_ROOT, env=env, check=False)
    if process.returncode:
        raise RuntimeError(f"command failed with exit code {process.returncode}: {' '.join(command)}")


def _normalized_files(report: dict) -> dict[str, dict]:
    return {name.replace("\\", "/"): value for name, value in report.get("files", {}).items()}


def _check_threshold(label: str, actual: float, minimum: float, failures: list[str]) -> None:
    if actual + 1e-9 < minimum:
        failures.append(f"{label}: actual={actual:.2f}%, minimum={minimum:.2f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    args = parser.parse_args()
    threshold_path = args.thresholds if args.thresholds.is_absolute() else REPO_ROOT / args.thresholds
    config = json.loads(threshold_path.read_text(encoding="utf-8"))
    if not os.environ.get("MOVIEPILOT_BACKEND_PATH"):
        print("MOVIEPILOT_BACKEND_PATH is required for the V3 test bootstrap", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="doubancenter-coverage-") as temp_dir:
        report_path = Path(temp_dir) / "coverage.json"
        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(Path(temp_dir) / ".coverage")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        python = sys.executable
        _run([python, "-m", "coverage", "erase"], env)
        _run(
            [
                python,
                "-m",
                "coverage",
                "run",
                "--branch",
                "--source=plugins.v3/doubancenter",
                "-m",
                "pytest",
                "tests/v3/doubancenter",
                "-q",
            ],
            env,
        )
        _run([python, "-m", "coverage", "json", "-o", str(report_path)], env)
        report = json.loads(report_path.read_text(encoding="utf-8"))

    failures: list[str] = []
    total = float(report["totals"]["percent_covered"])
    _check_threshold("TOTAL", total, float(config["minimum_total_percent"]), failures)
    files = _normalized_files(report)
    observed = {"TOTAL": total}
    for name, minimum in config.get("minimum_file_percent", {}).items():
        if name not in files:
            failures.append(f"{name}: missing from coverage report")
            continue
        actual = float(files[name]["summary"]["percent_covered"])
        observed[name] = actual
        _check_threshold(name, actual, float(minimum), failures)
    if failures:
        print("DoubanCenter coverage gate failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("DoubanCenter coverage gate passed:")
    for name, actual in observed.items():
        print(f"- {name}: {actual:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
