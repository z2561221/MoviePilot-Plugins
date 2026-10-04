"""无浏览器执行实际 Vue 组件的异步边界回归。"""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("case", ["native", "dashboard", "config"])
def test_frontend_async_boundaries(case):
    """宿主拒绝、取消和成功返回应保持各自的副作用边界。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for Vue behavior tests")
    frontend = Path(__file__).resolve().parents[3] / "plugins.v3/agentrank/frontend"
    if not (frontend / "node_modules/vue").exists():
        pytest.skip("Install the plugin frontend dependencies for Vue behavior tests")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("frontend_behavior.cjs")), case],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
