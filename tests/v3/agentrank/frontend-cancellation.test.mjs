import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'
import { useAgentRankState } from '../../../plugins.v3/agentrank/frontend/src/components/useAgentRankState.js'
import { isApiRequestCancellation } from '../../../plugins.v3/agentrank/frontend/src/components/api.js'
const frontend = new URL('../../../plugins.v3/agentrank/frontend/', import.meta.url)
const vue = createRequire(new URL('package.json', frontend))('vue')

for (const marker of [{ name: 'AbortError' }, { name: 'CanceledError' }, { code: 'ERR_CANCELED' }, { __CANCEL__: true }]) {
  test(`取消不写错误、不留下重试、不重发操作：${JSON.stringify(marker)}`, async () => {
    const error = Object.assign(new Error('cancelled'), marker)
    let calls = 0
    const api = { get: async () => { throw error }, post: async () => { calls++; throw error } }
    const scope = vue.effectScope()
    const state = scope.run(() => useAgentRankState(api, 'AgentRank'))
    try {
      await assert.rejects(state.loadOptions(), caught => caught === error)
      assert.equal(state.error.value, null)
      assert.equal(state.operations.options.error, null)
      assert.equal(state.operations.options.retry, null)
      assert.equal(state.loading.options, false)
      state.selectedProfileId.value = 'test-profile'
      await assert.rejects(state.refresh(), caught => caught === error)
      assert.equal(calls, 1)
      assert.equal(state.feedback.value, null)
      assert.equal(state.error.value, null)
      assert.equal(state.loading.action, '')
    } finally { scope.stop() }
  })
}

test('真实网络错误继续保留错误及重试入口', async () => {
  const scope=vue.effectScope()
  const state=scope.run(()=>useAgentRankState({get:async()=>{throw new Error('offline')}},'AgentRank'))
  try {
    await assert.rejects(state.loadOptions(), /offline/)
    assert.equal(state.error.value.message,'offline')
    assert.equal(typeof state.operations.options.retry,'function')
  } finally {scope.stop()}
})

test('页面刷新按钮收到取消时不显示成功或错误提示', async () => {
  const source=readFileSync(new URL('src/components/Page.vue',frontend),'utf8')
  const handler=source.slice(source.indexOf('async function handleRefresh()'),source.indexOf('async function runAction('))
  const snackbar=vue.ref({show:false}),cancelled=Object.assign(new Error('cancelled'),{name:'AbortError'})
  let polling=0
  const handle=new Function('state','snackbar','scheduleRunProgressPoll','isApiRequestCancellation',handler+';return handleRefresh')(
    {refresh:async()=>{throw cancelled}},snackbar,()=>polling++,isApiRequestCancellation)
  await handle()
  assert.equal(snackbar.value.show,false)
  assert.equal(polling,0)
})


test('旧请求取消不能结束后来请求的加载', async () => {
  let cancel, finish
  let calls=0
  const scope=vue.effectScope()
  const state=scope.run(()=>useAgentRankState({get:()=>++calls===1
    ? new Promise((_resolve,reject)=>{cancel=reject})
    : new Promise(resolve=>{finish=resolve})},'AgentRank'))
  try {
    state.selectedProfileId.value='test-profile'
    const first=state.loadConversation()
    const second=state.loadConversation()
    assert.equal(calls,2)
    const cancelled=Object.assign(new Error('cancelled'),{code:'ERR_CANCELED'})
    const caught=assert.rejects(first,error=>error===cancelled)
    cancel(cancelled)
    await caught
    assert.equal(state.operations.conversation.loading,true)
    assert.equal(state.error.value,null)
    assert.equal(state.operations.conversation.retry,null)
    finish({success:true,message:'ok',data:{messages:[{id:'current'}]}})
    await second
    assert.equal(state.operations.conversation.loading,false)
    assert.equal(state.conversation.value.messages[0].id,'current')
  } finally {scope.stop()}
})

test('后台状态请求取消时保留原状态且不给出重试错误', async () => {
  const scope=vue.effectScope()
  const cancelled=Object.assign(new Error('cancelled'),{name:'AbortError'})
  const state=scope.run(()=>useAgentRankState({get:async()=>{throw cancelled}},'AgentRank'))
  try {
    state.selectedProfileId.value='test-profile'
    await vue.nextTick()
    const previous=state.conversationStatus.value
    const result=await state.loadConversationStatus()
    assert.equal(result,previous)
    assert.equal(state.operations['conversation:status'].loading,false)
    assert.equal(state.operations['conversation:status'].retry,null)
    assert.equal(state.operations['conversation:status'].error,null)
  } finally {scope.stop()}
})
