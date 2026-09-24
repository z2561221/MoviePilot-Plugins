"""验证 Vue 联邦 API helper 处理 MoviePilot V3 最终 payload。"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_MODULE = REPO_ROOT / "plugins.v3/downloadmanagerlocal/frontend/src/components/api.js"


def test_page_ignores_stale_history_and_unmounted_errors() -> None:
    """执行实际页面脚本，验证乱序响应和销毁后错误不能回写。"""
    script = r'''
      import assert from 'node:assert/strict';
      import { readFileSync } from 'node:fs';
      const source = readFileSync('plugins.v3/downloadmanagerlocal/frontend/src/components/Page.vue', 'utf8')
        .match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '');
      const pending = [], cleanups = [];
      const props = { pluginId: 'test-instance', api: {} };
      const getApi = (api, id, path) => new Promise((resolve, reject) => pending.push({path, resolve, reject}));
      const build = new Function('ref', 'computed', 'watch', 'onMounted', 'onBeforeUnmount',
        'defineProps', 'defineEmits', 'getPluginApi', 'postPluginApi',
        source + '\nreturn {loadHistory, page, records, error, loading, nextPage, overview, overviewFeatureCards};');
      globalThis.document = { removeEventListener() {} };
      const state = build(value => ({value}), get => ({get value() { return get(); }}), () => {},
        () => {}, fn => cleanups.push(fn), () => props, () => () => {}, getApi, () => {});
      state.overview.value = {cards: {transfer: {today_success: 31, today_fallback: 7, success_total: 227}}};
      assert.equal(state.overviewFeatureCards.value[0].desc, '今日 31 · 兜底 7 · 累计 196');
      state.overview.value = {cards: {iyuu: {today_success: 9, today_fail: 3, success_total: 110, fail_total: 7}}};
      assert.equal(state.overviewFeatureCards.value[1].desc, '成功 9 · 失败 3 · 累计 101');
      state.overview.value = {cards: {iyuu: {today_success: 0, today_fail: 0, success_total: 110, fail_total: 7}}};
      assert.equal(state.overviewFeatureCards.value[1].desc, '成功 0 · 失败 0 · 累计 110');
      const first = state.loadHistory(), second = state.loadHistory();
      pending[1].resolve({items: [{hash: 'page1'}], total: 45}); await second;
      state.nextPage();
      pending[2].resolve({items: [{hash: 'page2'}], total: 45});
      await new Promise(resolve => setImmediate(resolve));
      pending[0].resolve({items: [{hash: 'old-page1'}], total: 45}); await first;
      assert.equal(state.page.value, 2);
      assert.equal(state.records.value[0].hash, 'page2');
      const last = state.loadHistory();
      for (const cleanup of cleanups) cleanup();
      pending[3].reject(new Error('late error')); await last;
      assert.equal(state.error.value, '');
      assert.equal(state.records.value[0].hash, 'page2');
    '''
    result = _run_node(script)
    assert result.returncode == 0, result.stdout + result.stderr


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    """用 Node ESM 执行一段 API helper 合同断言。"""
    return subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_frontend_api_strict_envelope_bare_payload_and_network_reject() -> None:
    """严格解包标准 envelope，裸查询和网络失败保持各自合同。"""
    module_url = API_MODULE.as_uri()
    script = f"""
      import assert from 'node:assert/strict'
      import {{ getPluginApi }} from {module_url!r}

      const successApi = {{
        get: async path => {{ assert.equal(path, 'plugin/CloneDownloadManager/overview'); return ({{ success: true, message: '', data: {{ code: 0, value: 7 }} }}) }}
      }}
      assert.deepEqual(await getPluginApi(successApi, 'CloneDownloadManager', 'overview'), {{ code: 0, value: 7 }})

      const bareApi = {{
        get: async path => {{ assert.equal(path, 'plugin/CloneDownloadManager/overview'); return ({{ code: 0, cards: {{ transfer: {{ active: false }} }} }}) }}
      }}
      assert.deepEqual(
        await getPluginApi(bareApi, 'CloneDownloadManager', 'overview'),
        {{ code: 0, cards: {{ transfer: {{ active: false }} }} }}
      )

      const customApi = {{
        get: async () => ({{ success: true, message: '', data: {{ code: 0 }}, trace: 'keep' }})
      }}
      assert.deepEqual(
        await getPluginApi(customApi, 'CloneDownloadManager', 'overview'),
        {{ success: true, message: '', data: {{ code: 0 }}, trace: 'keep' }}
      )

      const failureApi = {{
        get: async () => ({{ success: false, message: '业务失败', data: {{ code: 1 }} }})
      }}
      await assert.rejects(() => getPluginApi(failureApi, 'CloneDownloadManager', 'overview'), /业务失败/)

      const networkApi = {{ get: async () => {{ throw new Error('network down') }} }}
      await assert.rejects(() => getPluginApi(networkApi, 'CloneDownloadManager', 'overview'), /network down/)
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
      const result = await getPluginApi(api, 'CloneDownloadManager', 'overview', {{ feedback: 'silent' }})
      assert.deepEqual(received, {{ feedback: 'silent' }})
      assert.deepEqual(result, {{ nested: {{ data: 9 }} }})
    """

    result = _run_node(script)

    assert result.returncode == 0, result.stdout + result.stderr
    source = API_MODULE.read_text(encoding="utf-8")
    assert "response.data.data" not in source
