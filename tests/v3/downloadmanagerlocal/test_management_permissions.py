"""真实 HTTP 路由授权先于插件管理副作用。"""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.plugins.downloadmanagerlocal import DownloadManagerLocal
from app.plugins.downloadmanagerlocal.controller.security import require_admin
from app.sdk.security import verify_token


def _app(token):
    """使用插件实际路由及身份依赖，存储完全隔离在内存。"""
    plugin = object.__new__(DownloadManagerLocal)
    state = {"upload_limit_site_rules": {"original": {"limit_kib": 4}}}
    writes = []
    plugin.get_config = lambda: deepcopy(state)
    def save(config):
        writes.append(deepcopy(config))
        state.update(config)
        return True
    plugin.update_config = save
    app = FastAPI()
    def identity():
        if token is None:
            raise HTTPException(401, "Not authenticated")
        return token
    app.dependency_overrides[verify_token] = identity
    routes = plugin.get_api()
    for route in routes:
        values = {key: value for key, value in route.items() if key != "auth"}
        app.add_api_route(**values)
    return app, routes, state, writes


@pytest.mark.parametrize("admin,expected", [(False, 403), (None, 401)])
def test_every_management_route_rejects_before_writing(admin, expected):
    """普通用户及未登录请求不能绕过管理入口，包括有副作用的扫描。"""
    app, routes, state, writes = _app(None if admin is None else SimpleNamespace(super_user=admin))
    before = deepcopy(state)
    with TestClient(app) as client:
        for route in routes:
            if "POST" not in route["methods"]:
                continue
            assert any(item.dependency is require_admin for item in route.get("dependencies", []))
            response = client.post(route["path"], json={})
            assert response.status_code == expected, (route["path"], response.text)
    assert state == before
    assert writes == []


@pytest.mark.parametrize("admin", [True, False])
def test_permissions_and_real_management_write_match_current_identity(admin):
    """能力查询与实际授权一致，管理员仍可保存且不破坏普通用户只读入口。"""
    app, _, state, writes = _app(SimpleNamespace(super_user=admin))
    with TestClient(app) as client:
        assert client.get("/permissions").json() == {"can_manage": admin}
        result = client.post("/upload_limit_site_rules_update", json={"rules": {"review": {"limit_kib": 9}}})
    assert result.status_code == (200 if admin else 403)
    if admin:
        assert result.json()["success"] is True
        assert state["upload_limit_site_rules"] == {"review": {"limit_kib": 9}}
        assert len(writes) == 1
    else:
        assert writes == []


def test_permission_view_rejects_stale_grants_and_fails_closed():
    """运行真实Vue监听器，旧实例管理权限不可带入新实例。"""
    import subprocess
    from pathlib import Path
    script = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const vue = require('vue');
(async()=>{
 for (const name of ['Config','Page']) {
  const props = vue.reactive({api:{},pluginId:'A',initialConfig:{}}), pending=[], cleanups=[];
  const source=fs.readFileSync('src/components/'+name+'.vue','utf8').match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'');
  const context={...vue, console, defineProps:()=>props,defineEmits:()=>()=>{},onMounted:()=>{},onBeforeUnmount:fn=>cleanups.push(fn),getPluginApi:(_api,id,path)=>path==='permissions'?new Promise((resolve,reject)=>pending.push({id,resolve,reject})):Promise.resolve({}),postPluginApi:()=>{},postPluginJsonApi:()=>{},isApiRequestCancellation:e=>e?.name==='AbortError',document:{removeEventListener(){}}};
  vm.createContext(context);const scope=vue.effectScope();scope.run(()=>vm.runInContext(source+'\nglobalThis.result={canManage,permissionError}',context));
  assert.equal(context.result.canManage.value,false);props.pluginId='B';await vue.nextTick();
  pending[0].resolve({can_manage:true});await new Promise(resolve=>setImmediate(resolve));assert.equal(context.result.canManage.value,false);
  pending[1].resolve({can_manage:false});await new Promise(resolve=>setImmediate(resolve));assert.equal(context.result.canManage.value,false);
  props.api={};await vue.nextTick();pending[2].resolve({can_manage:true});await new Promise(resolve=>setImmediate(resolve));assert.equal(context.result.canManage.value,true);
  props.pluginId='C';await vue.nextTick();pending[3].reject(new Error('offline'));await new Promise(resolve=>setImmediate(resolve));assert.equal(context.result.canManage.value,false);
  cleanups.forEach(fn=>fn());scope.stop();
 }
})().catch(e=>{console.error(e);process.exitCode=1})
"""
    frontend = Path(__file__).resolve().parents[3] / "plugins.v3/downloadmanagerlocal/frontend"
    result = subprocess.run(["node", "-e", script], cwd=frontend, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
