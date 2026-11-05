"""前端同步删除组件的编译及跨实例异步回包隔离。"""

import subprocess
from pathlib import Path


def test_sync_delete_component_compiles_and_rejects_stale_results():
    root = Path(__file__).resolve().parents[3]
    frontend = root / "plugins.v3/downloadmanagerlocal/frontend"
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const compiler = require('vue/compiler-sfc');
const source = fs.readFileSync('src/components/SyncDeletePane.vue', 'utf8');
const parsed = compiler.parse(source);
assert.equal(parsed.errors.length, 0);
const compiled = compiler.compileScript(parsed.descriptor, {id:'sync-delete'});
const template = compiler.compileTemplate({source:parsed.descriptor.template.content, filename:'SyncDeletePane.vue', id:'sync-delete', compilerOptions:{bindingMetadata:compiled.bindings}});
assert.equal(template.errors.length, 0);
let pending = [];
const props = {api:{}, pluginId:'CloneA', mode:'history', form:null};
const context = {
  defineProps:()=>props, defineExpose:()=>{}, ref:value=>({value}),
  computed:fn=>({get value(){return fn()}}), watch:()=>{}, onBeforeUnmount:()=>{},
  getPluginApi:(api,id,path)=>new Promise(resolve=>pending.push({resolve,id,path})),
  postPluginJsonApi:async()=>({accepted:true}), console, Date,
};
vm.createContext(context);
const code = parsed.descriptor.scriptSetup.content.replace(/^import .*$/gm,'');
vm.runInContext(code + '\nglobalThis.test={load,rows,error,loading};',context);
(async()=>{
 const first=context.test.load();
 assert.equal(pending[0].id,'CloneA');
 props.pluginId='CloneB';
 const second=context.test.load();
 pending[1].resolve({items:[{id:'B'}],total:1,enabled:true});
 await second;
 pending[0].resolve({items:[{id:'A'}],total:1,enabled:true});
 await first;
 assert.equal(context.test.rows.value[0].id,'B');
 assert.equal(context.test.loading.value,false);
 assert(pending.every(item=>item.path.startsWith('sync_delete/history')));
 console.log('component compile and stale instance response checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    subprocess.run(["node", "-e", script], cwd=frontend, check=True, capture_output=True, text=True)
