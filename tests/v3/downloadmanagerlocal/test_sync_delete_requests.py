"""使用真实 Vue 响应式模型验证同步删除面板的请求归属。"""

import subprocess
from pathlib import Path


def test_sync_delete_options_and_retry_have_independent_ownership():
    """配置编辑不吞选项，刷新不吞重试受理回执。"""
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
  const props = vue.reactive({canManage:true,api:{}, pluginId:'A', mode, form:mode==='config'?{sync_delete_enabled:false,sync_delete_servers:['Emby']}:null});
  const request = (api,id,path,payload) => new Promise((resolve,reject)=>pending.push({resolve,reject,id,path,payload}));
  const context = {defineProps:()=>props, defineExpose:()=>{}, ref:vue.ref, computed:vue.computed,
    watch:(...args)=>{const stop=vue.watch(...args);cleanups.push(stop)}, onBeforeUnmount:fn=>cleanups.push(fn),
    getPluginApi:request, postPluginJsonApi:request,
    isApiRequestCancellation:error=>error?.code==='ERR_CANCELED', console, Date};
  vm.createContext(context);
  vm.runInContext(code+'\nglobalThis.test={load,retry,servers,rows,error,notice,loading,retryId,total,enabled,editMapping,addMapping,removeMapping,toggleMapping,expandedMappings,cloudMappings,localMappings};',context);
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
  assert.equal(config.localMappings.value.length,0,'unused group must not add an empty mapping');
  config.addMapping('sync_delete_cloud_paths',4);
  assert.equal(config.cloudMappings.value.length,1);
  assert.equal(config.expandedMappings.value.sync_delete_cloud_paths,0,'new mapping opens for editing');
  config.props.form.sync_delete_cloud_paths='/emby#/strm#/media#/library';
  config.props.form.sync_delete_cloud=false;
  config.editMapping('sync_delete_cloud_paths',0,2,'/new-media');
  assert.equal(config.props.form.sync_delete_cloud_paths,'/emby#/strm#/new-media#/library');
  assert.equal(config.props.form.sync_delete_cloud,false,'path editing must not enable cloud deletion');
  config.editMapping('sync_delete_cloud_paths',0,3,'/new library');
  assert.equal(config.cloudMappings.value[0][2],'/new-media','local path edits must preserve the cloud mapping');
  const draft=config.props.form.sync_delete_cloud_paths;
  config.toggleMapping('sync_delete_cloud_paths',0);
  assert.equal(config.expandedMappings.value.sync_delete_cloud_paths,-1);
  config.toggleMapping('sync_delete_cloud_paths',0);
  assert.equal(config.props.form.sync_delete_cloud_paths,draft,'collapsing a mapping must preserve its draft');
  config.addMapping('sync_delete_cloud_paths',4);
  assert.equal(config.expandedMappings.value.sync_delete_cloud_paths,1);
  config.removeMapping('sync_delete_cloud_paths',0);
  assert.equal(config.expandedMappings.value.sync_delete_cloud_paths,0,'removing an earlier mapping keeps the same editor open');
  config.removeMapping('sync_delete_cloud_paths',0);
  assert.equal(config.cloudMappings.value.length,0);
  assert.equal(config.expandedMappings.value.sync_delete_cloud_paths,-1);
  config.props.form.sync_delete_cloud_paths=draft;
  config.props.form.sync_delete_cloud_paths=' \n'+config.props.form.sync_delete_cloud_paths;
  config.removeMapping('sync_delete_cloud_paths',0);
  assert.equal(config.props.form.sync_delete_cloud_paths,'');
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
  assert.equal(Object.keys(history.expandedMappings.value).length,0);
  history.pending.at(-1).reject({code:'ERR_CANCELED',message:'cancelled'});await settle();
  assert.equal(history.error.value,'','request cancellation is normal control flow');
  assert.equal(history.loading.value,false);
  history.close();
  console.log('request ownership cases passed');
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    result = subprocess.run(["node", "-e", script], cwd=frontend, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "request ownership cases passed" in result.stdout


def test_saving_supported_scenarios_keeps_paths_and_disables_retired_options():
    """三种流程保存路径和删除分工，但不能带出隐藏的旧删除选项。"""
    frontend = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal/frontend"
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const code = fs.readFileSync('src/components/Config.vue', 'utf8')
  .match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '');
const build = new Function('reactive','ref','computed','watch','onMounted','onBeforeUnmount',
  'defineProps','defineEmits','getPluginApi','postPluginJsonApi','isApiRequestCancellation',
  code+'\nreturn {form,saveConfig};');
for (const scenario of [
  {sync_delete_local_paths:'/emby-local#/library',sync_delete_cloud_paths:'',sync_delete_cloud:false},
  {sync_delete_local_paths:'',sync_delete_cloud_paths:'/emby-strm#/strm#/media',sync_delete_cloud:true},
  {sync_delete_local_paths:'/emby-local#/library',sync_delete_cloud_paths:'/emby-strm#/strm#/media#/library-cloud',sync_delete_cloud:false},
]) {
  const initialConfig = {...scenario,sync_delete_servers:['Emby'],sync_delete_source_paths:'/downloads',
    sync_delete_exclude_paths:'/downloads/keep',sync_delete_force_cloud:true,sync_delete_library_deleted:true,
    sync_delete_source:true,sync_delete_torrents:true,sync_delete_records:true,unrelated_setting:'keep'};
  const props = {api:{},pluginId:'A',initialConfig};
  const before = JSON.stringify(initialConfig);
  const emitted = [];
  const noRequest = () => {throw new Error('saving a draft must not issue a deletion request')};
  const state = build(value=>value,value=>({value}),get=>({get value(){return get()}}),
    (source,cb,options)=>{if(options?.immediate)cb(source())},()=>{},()=>{},()=>props,
    ()=>(...args)=>emitted.push(args),noRequest,noRequest,()=>false);
  state.saveConfig();
  assert.equal(emitted.length,1);
  assert.equal(emitted[0][0],'save');
  assert.deepEqual(emitted[0][1],{...state.form,sync_delete_force_cloud:false,sync_delete_library_deleted:false});
  for (const [key,value] of Object.entries(scenario)) assert.equal(emitted[0][1][key],value);
  assert.equal(emitted[0][1].sync_delete_source_paths,'/downloads');
  assert.equal(emitted[0][1].sync_delete_exclude_paths,'/downloads/keep');
  assert.equal(emitted[0][1].unrelated_setting,'keep');
  assert.equal(JSON.stringify(initialConfig),before,'saving must not modify the supplied config');
  state.form.sync_delete_cloud_paths+='\n###';
  state.form.sync_delete_local_paths+='\n#';
  state.saveConfig();
  assert.equal(emitted[1][1].sync_delete_cloud_paths,scenario.sync_delete_cloud_paths,'unused empty inputs must not create invalid mappings');
  assert.equal(emitted[1][1].sync_delete_local_paths,scenario.sync_delete_local_paths);
}
console.log('supported scenario save cases passed');
"""
    result = subprocess.run(["node", "-e", script], cwd=frontend, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "supported scenario save cases passed" in result.stdout
