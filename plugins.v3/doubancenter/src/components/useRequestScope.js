import { getCurrentInstance, nextTick, onActivated, onBeforeUnmount, onDeactivated, onScopeDispose, watch } from 'vue'

// 请求归属覆盖实例切换、路由离开、KeepAlive 失活和卸载。
export function useRequestScope(owner, onInvalidate = () => {}) {
  let active = true
  let available = true
  let disposed = false
  let navigation = 0
  let epoch = 0
  const timers = new Map()
  function invalidate() {
    epoch += 1
    for (const [timer, finish] of timers) {
      clearTimeout(timer)
      finish(false)
    }
    timers.clear()
    onInvalidate()
  }
  function pause() { active = false; invalidate() }
  function resume() { if (available && !disposed) active = true }
  function deactivate() { available = false; pause() }
  function capture() {
    const generation = epoch
    const id = owner()
    return () => active && generation === epoch && id === owner()
  }
  function wait(ms) {
    if (!active) return Promise.resolve(false)
    return new Promise(resolve => {
      const timer = setTimeout(() => { timers.delete(timer); resolve(true) }, ms)
      timers.set(timer, resolve)
    })
  }
  function later(callback, ms) {
    const current = capture()
    void wait(ms).then(finished => { if (finished && current()) callback() })
  }
  watch(owner, invalidate, { flush: 'sync' })
  const instance = getCurrentInstance()
  const cleanups = []
  if (instance) {
    onBeforeUnmount(deactivate)
    onDeactivated(deactivate)
    onActivated(() => { available = true; resume() })
    // 使用宿主已有 router 的公开守卫，避免引入第二份 vue-router。
    const router = instance.proxy?.$router
    if (router?.beforeEach) cleanups.push(router.beforeEach((to, from) => {
      if (to.path !== from.path) { navigation += 1; pause() }
    }))
    if (router?.afterEach) cleanups.push(router.afterEach(async () => {
      const currentNavigation = navigation
      // 导航结束后等待卸载/失活钩子；仍显示的复用组件和取消导航才能恢复。
      await nextTick()
      if (currentNavigation === navigation) resume()
    }))
  }
  onScopeDispose(() => {
    disposed = true
    deactivate()
    for (const cleanup of cleanups) cleanup?.()
  })
  return { capture, invalidate, pause, resume, wait, later, isActive: () => active }
}
