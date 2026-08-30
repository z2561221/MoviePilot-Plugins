"""插件仓全量单测入口：CI 工具与 v1/v2/v3 分别运行，命令行参数透传给 pytest。

各代插件目录存在同名插件包，同一进程无法同时加载，故各代在独立子进程运行；
CI 工具测试不加载插件运行时。任一组非零退出码即整体失败，无用例的分组直接跳过。
"""
import subprocess
import sys
from pathlib import Path

# 本文件位于 tests/ 下：其父为 tests 目录，再上一级为插件仓根
_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
_GENERATION_SOURCE_DIRS = {
    "v1": "plugins",
    "v2": "plugins.v2",
    "v3": "plugins.v3",
}


def _generation_targets(
    generation: str,
    *,
    tests_dir: Path = _TESTS_DIR,
    repo_root: Path = _REPO_ROOT,
) -> list[Path]:
    """返回本代可执行测试目标，并报告缺少同代源码的历史残留目录。"""
    generation_dir = tests_dir / generation
    if generation == "ci":
        return [generation_dir] if list(generation_dir.rglob("test_*.py")) else []

    source_dir_name = _GENERATION_SOURCE_DIRS[generation]
    source_root = repo_root / source_dir_name
    targets = sorted(generation_dir.glob("test_*.py"))
    for plugin_tests in sorted(path for path in generation_dir.iterdir() if path.is_dir()):
        if not list(plugin_tests.rglob("test_*.py")):
            continue
        if (source_root / plugin_tests.name).is_dir():
            targets.append(plugin_tests)
            continue
        print(
            f"跳过无源码测试目录: {plugin_tests} "
            f"(缺少 {source_root / plugin_tests.name})",
            file=sys.stderr,
        )
    return targets


def _run_generation(generation: str, extra_args: list) -> int:
    """在每个测试目标的独立子进程运行一个代际分组。"""
    targets = _generation_targets(generation)
    if not targets:
        return 0
    exit_code = 0
    for target in targets:
        rc = subprocess.call(
            [sys.executable, "-m", "pytest", str(target), *extra_args],
            cwd=str(_REPO_ROOT),
        )
        exit_code = exit_code or rc
    return exit_code


if __name__ == "__main__":
    extra = sys.argv[1:]
    exit_code = 0
    # CI 工具与各代插件分会话运行；保留首个非零退出码作为整体结果。
    for generation in ("ci", "v3", "v2", "v1"):
        rc = _run_generation(generation, extra)
        exit_code = exit_code or rc
    sys.exit(exit_code)
