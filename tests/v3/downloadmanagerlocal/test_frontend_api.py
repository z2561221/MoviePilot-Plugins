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
    script = (
        f"import {{isApiRequestCancellation as requestCancelled}} from {API_MODULE.as_uri()!r};\n"
        "globalThis.isApiRequestCancellation = requestCancelled;\n" + script
    )
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
      import {{ getPluginApi, isApiRequestCancellation }} from {module_url!r}

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
      await assert.rejects(() => getPluginApi(failureApi, 'CloneDownloadManager', 'overview'), error => {{
        assert.equal(error.message, '业务失败');assert.equal(error.payload.data.code, 1);return true;
      }})
      for (const reason of [{{__CANCEL__:true}},{{code:'ERR_CANCELED'}},{{name:'AbortError'}},{{name:'CanceledError'}}]) {{
        assert.equal(isApiRequestCancellation(reason),true)
      }}
      assert.equal(isApiRequestCancellation(new Error('network')),false)

      const networkApi = {{ get: async () => {{ throw new Error('network down') }} }}
      await assert.rejects(() => getPluginApi(networkApi, 'CloneDownloadManager', 'overview'), /network down/)
    """

    result = _run_node(script)

    assert result.returncode == 0, result.stdout + result.stderr


def test_page_actions_do_not_write_back_after_instance_change_or_cancellation() -> None:
    """操作在途切实例或被取消时不显示旧结果，也不补发新实例查询。"""
    script = r'''
      import assert from 'node:assert/strict';
      import {readFileSync} from 'node:fs';
      const source=readFileSync('plugins.v3/downloadmanagerlocal/frontend/src/components/Page.vue','utf8')
        .match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'');
      for(const action of ['doRecovery','doDelete','doRetryRenames','doRetryRename','restoreArchive','deleteArchive']) {
        for(const cancelled of [false,true]) {
          const pending=[],watchers=[],cleanups=[];
          const props={pluginId:'A',api:{}};
          const request=(...args)=>new Promise((resolve,reject)=>pending.push({args,resolve,reject}));
          const build=new Function('ref','computed','watch','onMounted','onBeforeUnmount','defineProps','defineEmits','getPluginApi','postPluginApi',
            source+'\nreturn {doRecovery,doDelete,doRetryRenames,doRetryRename,restoreArchive,deleteArchive,actionMsg,activeTab};');
          const state=build(value=>({value}),get=>({get value(){return get()}}),(source,cb)=>watchers.push(cb),
            ()=>{},fn=>cleanups.push(fn),()=>props,()=>()=>{},request,request);
          const work=state[action]('hash');
          if(cancelled)pending[0].reject({code:'ERR_CANCELED',message:'cancelled'});
          else {props.pluginId='B';watchers[0]();pending[0].resolve({code:0,msg:'old result'});}
          await new Promise(resolve=>setImmediate(resolve));
          for(const item of pending.slice(1))item.resolve({items:[],total:0});
          await work;
          assert.equal(state.actionMsg.value,'',action);
          assert.equal(pending.length,1,action+' must not refresh a different instance');
        }
      }
    '''
    result = _run_node(script)
    assert result.returncode == 0, result.stdout + result.stderr


def test_config_waiting_actions_never_write_to_a_new_instance() -> None:
    """切换实例或替换配置后，等待策略保存的扫描和分配不能在新实例发起。"""
    script = r'''
      import assert from 'node:assert/strict';
      import {readFileSync} from 'node:fs';
      const source=readFileSync('plugins.v3/downloadmanagerlocal/frontend/src/components/Config.vue','utf8')
        .match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'');
      for (const action of ['reallocateUploadLimits','scanUploadSites','clearUploadSiteRules']) {
        const watchers=[],pending=[],cleanups=[];
        const props={pluginId:'A',api:{},initialConfig:{upload_limit_downloaders:['QB'],upload_limit_site_rules:{keep:{limit_kib:1}}}};
        const request=(api,id,path,payload)=>path==='permissions' ? Promise.resolve({can_manage:true}) : new Promise((resolve,reject)=>pending.push({id,path,payload,resolve,reject}));
        const build=new Function('reactive','ref','computed','watch','onMounted','onBeforeUnmount','defineProps','defineEmits','getPluginApi','postPluginJsonApi','isApiRequestCancellation',
          source+'\nreturn {form,queueUploadSiteRulesSave,reallocateUploadLimits,scanUploadSites,clearUploadSiteRules,uploadMessage};');
        globalThis.document={removeEventListener(){},visibilityState:'hidden'};
        const state=build(value=>value,value=>({value}),get=>({get value(){return get()}}),
          (source,cb,options)=>{watchers.push({source,cb});if(options?.immediate)cb(source())},()=>{},fn=>cleanups.push(fn),()=>props,()=>()=>{},request,request,
          error=>error?.code==='ERR_CANCELED');
        const saved=state.queueUploadSiteRulesSave({site:{limit_kib:2}});
        await Promise.resolve();await Promise.resolve();
        const work=state[action]();
        props.pluginId='B';watchers[1].cb();
        const replacement={upload_limit_downloaders:['TR'],upload_limit_site_rules:{new:{limit_kib:9}}};
        props.initialConfig=replacement;watchers[0].cb(replacement);
        pending[0].resolve({code:0,rules:{site:{limit_kib:2}}});
        await saved;await new Promise(resolve=>setImmediate(resolve));
        for(const pendingRequest of pending.slice(1))pendingRequest.resolve({code:0,rules:{}});
        await work;
        assert.equal(pending.length,1,action+' must not send a late write');
        assert.equal(state.form.upload_limit_site_rules.new.limit_kib,9,action+' must preserve new draft');
        assert.equal(state.uploadMessage.value,'');
        cleanups.forEach(fn=>fn());
      }
    '''
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


def test_config_save_respects_draft_instance_and_unmount() -> None:
    """执行实际组件，旧成功、旧错误、排队请求不能影响新草稿或实例。"""
    script = r'''
      import assert from 'node:assert/strict';
      import { readFileSync } from 'node:fs';
      const source = readFileSync('plugins.v3/downloadmanagerlocal/frontend/src/components/Config.vue', 'utf8')
        .match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '');
      const props = {pluginId: 'first-instance', api: {}, initialConfig: {upload_limit_site_rules: {Site: {limit_kib: 100}}}};
      const watchers = [], cleanups = [], pending = [];
      const build = new Function('ref', 'reactive', 'computed', 'watch', 'onMounted', 'onBeforeUnmount',
        'defineProps', 'defineEmits', 'getPluginApi', 'postPluginJsonApi',
        source + '\nreturn {form,queueUploadSiteRulesSave,uploadMessage,uploadMessageStatus};');
      globalThis.document = { removeEventListener() {} };
      const state = build(value => ({value}), value => value, fn => ({get value(){return fn()}}),
        (get, cb, options) => {watchers.push({get,cb});if(options?.immediate)cb(get());},
        () => {}, fn => cleanups.push(fn), () => props, () => () => {}, () => {},
        (api,id,path,body) => new Promise((resolve,reject) => pending.push({id,body,resolve,reject})));
      const tick = () => new Promise(resolve => setImmediate(resolve));
      const rules = limit => ({Site:{limit_kib:limit}});
      const first = state.queueUploadSiteRulesSave(rules(100));
      await tick();
      const queued = state.queueUploadSiteRulesSave(rules(200));
      props.initialConfig = {upload_limit_site_rules: rules(500)};
      watchers[0].cb(props.initialConfig);
      pending[0].resolve({code:0,rules:rules(100)});
      await Promise.all([first,queued]);
      assert.equal(state.form.upload_limit_site_rules.Site.limit_kib, 500);
      assert.equal(pending.length, 1);
      const current = state.queueUploadSiteRulesSave(rules(600));
      await tick();pending[1].resolve({code:0,rules:rules(600)});await current;
      assert.equal(state.form.upload_limit_site_rules.Site.limit_kib, 600);
      const oldInstance = state.queueUploadSiteRulesSave(rules(700));await tick();
      const staleQueued = state.queueUploadSiteRulesSave(rules(800));
      props.pluginId = 'second-instance';watchers[1].cb(props.pluginId);
      pending[2].reject(new Error('old instance failed'));
      await Promise.all([oldInstance,staleQueued]);
      assert.equal(pending.length, 3);
      assert.equal(state.uploadMessageStatus.value, 'success');
      const disposed = state.queueUploadSiteRulesSave(rules(900));await tick();
      for(const cleanup of cleanups)cleanup();
      pending[3].resolve({code:0,rules:rules(900)});await disposed;
      assert.equal(state.form.upload_limit_site_rules.Site.limit_kib, 600);
    '''
    result = _run_node(script)
    assert result.returncode == 0, result.stdout + result.stderr
