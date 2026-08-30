"""Run the repository Ruff ratchet and strict checks for touched quality-gate files."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = REPO_ROOT / ".github" / "ruff-ratchet-baseline.json"


def _ruff_command() -> list[str]:
    executable = shutil.which("ruff")
    if executable:
        return [executable]
    if importlib.util.find_spec("ruff") is not None:
        return [sys.executable, "-m", "ruff"]
    raise RuntimeError("Ruff is unavailable; install it or expose the ruff module through PYTHONPATH")


def _run_ruff(arguments: list[str]) -> list[dict]:
    process = subprocess.run(
        [*_ruff_command(), "check", *arguments, "--output-format=json"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if process.returncode not in (0, 1):
        raise RuntimeError(process.stderr.strip() or "Ruff failed without diagnostic output")
    return json.loads(process.stdout or "[]")


def _load_baseline(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_ratchet(config: dict) -> tuple[int, list[str]]:
    diagnostics = _run_ruff(config.get("paths") or ["."])
    counts = Counter(item.get("code") for item in diagnostics if item.get("code"))
    maximum = config.get("maximum_by_code") or {}
    failures = [
        f"{code}: current={count}, baseline={int(maximum.get(code, 0))}"
        for code, count in sorted(counts.items())
        if count > int(maximum.get(code, 0))
    ]
    return len(diagnostics), failures


def _check_strict_paths(config: dict) -> list[str]:
    paths = config.get("strict_paths") or []
    if not paths:
        return []
    select = ",".join(config.get("strict_select") or ["E4", "E7", "E9", "F"])
    diagnostics = _run_ruff([*paths, "--select", select])
    return [
        f"{Path(item['filename']).relative_to(REPO_ROOT)}:{item['location']['row']}:{item['location']['column']} "
        f"{item['code']} {item['message']}"
        for item in diagnostics
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    args = parser.parse_args()
    baseline_path = args.baseline if args.baseline.is_absolute() else REPO_ROOT / args.baseline
    config = _load_baseline(baseline_path)
    total, ratchet_failures = _check_ratchet(config)
    strict_failures = _check_strict_paths(config)
    if ratchet_failures or strict_failures:
        print("Ruff ratchet failed:")
        for failure in [*ratchet_failures, *strict_failures]:
            print(f"- {failure}")
        return 1
    print(f"Ruff ratchet passed: {total} diagnostics, no rule count increased")
    print(f"Strict paths passed: {len(config.get('strict_paths') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
