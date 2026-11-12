import { ref, watch, onScopeDispose } from 'vue'
import { getPluginApi, isApiRequestCancellation } from './api'

// 显示权限按当前API与实例读取，服务端仍逐次授权每个管理操作。
export function useManagementPermissions(api, pluginId) {
  const canManage = ref(false)
  const permissionError = ref('')
  let alive = true
  let generation = 0
  watch(() => [api(), pluginId()], async ([client, id]) => {
    const current = ++generation
    const owns = () => alive && current === generation && client === api() && id === pluginId()
    canManage.value = false
    permissionError.value = ''
    try {
      const result = await getPluginApi(client, id, 'permissions', { feedback: 'silent' })
      if (owns()) canManage.value = result?.success === true && result.data?.can_manage === true
    } catch (error) {
      if (owns() && !isApiRequestCancellation(error)) permissionError.value = '权限读取失败，请重新打开页面。'
    }
  }, { immediate: true, flush: 'sync' })
  onScopeDispose(() => { alive = false; generation++ })
  return { canManage, permissionError }
}
