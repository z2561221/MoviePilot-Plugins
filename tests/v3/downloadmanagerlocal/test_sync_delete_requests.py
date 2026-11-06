"""使用真实 Vue 响应式模型验证同步删除面板的请求归属。"""

import subprocess
from pathlib import Path


def test_sync_delete_options_preview_and_retry_have_independent_ownership():
    """配置编辑不吞选项，旧预览不覆盖新输入，刷新不吞重试受理回执。"""
    frontend = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal/frontend"
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const vue = require('vue');
const compiler = require('vue/compiler-sfc');
const parsed = compiler.parse(fs.readFileSync('src/components/SyncDeletePane.vue', 'utf8'));
const code = parsed.descriptor.scriptSetup.content.replace(/^import .*$/gm, '');
function setup(mode) {
  const pending = [], cleanups = [];
  const props = vue.reactive({api:{}, pluginId:'A', mode, form:mode==='config'?{sync_delete_enabled:false,sync_delete_servers:['Emby']}:null});
  const request = (api,id,path,payload) => new Promise((resolve,reject)=>pending.push({resolve,reject,id,path,payload}));
  const context = {defineProps:()=>props, defineExpose:()=>{}, ref:vue.ref, computed:vue.computed,
    watch:(...args)=>{const stop=vue.watch(...args);cleanups.push(stop)}, onBeforeUnmount:fn=>cleanups.push(fn),
    getPluginApi:request, postPluginJsonApi:request,
    isApiRequestCancellation:error=>error?.code==='ERR_CANCELED', console, Date};
  vm.createContext(context);
  vm.runInContext(code+'\nglobalThis.test={load,preview,retry,servers,rows,error,notice,loading,previewPath,previewPlan,retryId,total,enabled};',context);
  return {...context.test,props,pending,close:()=>cleanups.forEach(fn=>fn())};
}
const settle = async()=>{await vue.nextTick();await Promise.resolve();await Promise.resolve()};
(async()=>{
  const config=setup('config');
  config.props.form.sync_delete_enabled=true;
  await vue.nextTick();
  config.pending[0].resolve({servers:['Emby']});
  await settle();
  assert.equal(config.servers.value[0],'Emby','editing a setting must not discard server options');
  config.previewPath.value='/emby/old.strm';await vue.nextTick();
  const preview=config.preview();
  config.previewPath.value='/emby/new.strm';await vue.nextTick();
  config.pending[1].resolve({plan:{marker:'old'}});await preview;
  assert.equal(config.previewPlan.value,null,'old path preview must not label the new path');
  config.close();
  const history=setup('history');
  history.pending[0].resolve({items:[{id:'job'}],total:1,enabled:true});await settle();
  const retry=history.retry({id:'job'});
  const refresh=history.load();
  history.pending[2].resolve({items:[],total:0,enabled:true});await refresh;
  history.pending[1].resolve({accepted:true});await settle();
  assert.match(history.notice.value,/队列/,'refresh must not swallow an accepted retry');
  history.pending[3]?.resolve({items:[],total:0,enabled:true});await retry;
  history.props.pluginId='B';await vue.nextTick();
  assert.equal(history.enabled.value,false);
  assert.equal(history.total.value,0);
  history.pending.at(-1).reject({code:'ERR_CANCELED',message:'cancelled'});await settle();
  assert.equal(history.error.value,'','request cancellation is normal control flow');
  assert.equal(history.loading.value,false);
  history.close();
  console.log('request ownership cases passed');
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    result = subprocess.run(["node", "-e", script], cwd=frontend, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "request ownership cases passed" in result.stdout
