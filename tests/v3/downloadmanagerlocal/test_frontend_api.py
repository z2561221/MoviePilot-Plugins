"""验证 Vue 联邦 API helper 只处理 MoviePilot V3 最终 envelope。"""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
API_MODULE = REPO_ROOT / "plugins.v3/downloadmanagerlocal/frontend/src/components/api.js"


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    """用 Node ESM 执行一段 API helper 合同断言。"""
    return subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_frontend_api_success_failure_and_network_reject() -> None:
    """成功读取 response.data，业务失败与网络失败都必须 reject。"""
    module_url = API_MODULE.as_uri()
    script = f"""
      import assert from 'node:assert/strict'
      import {{ getPluginApi }} from {module_url!r}

      const successApi = {{
        get: async () => ({{ success: true, message: '', data: {{ code: 0, value: 7 }} }})
      }}
      assert.deepEqual(await getPluginApi(successApi, 'overview'), {{ code: 0, value: 7 }})

      const failureApi = {{
        get: async () => ({{ success: false, message: '业务失败', data: {{ code: 1 }} }})
      }}
      await assert.rejects(() => getPluginApi(failureApi, 'overview'), /业务失败/)

      const networkApi = {{ get: async () => {{ throw new Error('network down') }} }}
      await assert.rejects(() => getPluginApi(networkApi, 'overview'), /network down/)
    """

    result = _run_node(script)

    assert result.returncode == 0, result.stdout + result.stderr


def test_frontend_api_forwards_silent_feedback_without_double_unwrap() -> None:
    """轮询可传 silent，helper 不得读取 response.data.data。"""
    module_url = API_MODULE.as_uri()
    script = f"""
      import assert from 'node:assert/strict'
      import {{ getPluginApi }} from {module_url!r}

      let received
      const api = {{
        get: async (_path, options) => {{
          received = options
          return {{ success: true, message: '', data: {{ nested: {{ data: 9 }} }} }}
        }}
      }}
      const result = await getPluginApi(api, 'overview', {{ feedback: 'silent' }})
      assert.deepEqual(received, {{ feedback: 'silent' }})
      assert.deepEqual(result, {{ nested: {{ data: 9 }} }})
    """

    result = _run_node(script)

    assert result.returncode == 0, result.stdout + result.stderr
    source = API_MODULE.read_text(encoding="utf-8")
    assert "response.data.data" not in source
