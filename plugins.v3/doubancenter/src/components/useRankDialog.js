import { ref, watch } from 'vue'

export function useRankDialog({ requestScope, resolveRankMedia, tmdbIdOf }) {
  const dialogItem = ref(null)
  const showDialog = ref(false)
  const dialogResolving = ref(false)
  const dialogResolveError = ref('')
  const dialogResolveToken = ref(0)

  watch(showDialog, open => {
    if (!open) {
      dialogResolveToken.value += 1
      dialogResolving.value = false
    }
  }, { flush: 'sync' })

  async function showActionDialog(rk, item) {
    const scope = requestScope()
    if (!scope.isActive()) return
    const current = scope.capture()
    const token = ++dialogResolveToken.value
    dialogItem.value = { rk, item: { ...(item || {}) } }
    dialogResolveError.value = ''
    dialogResolving.value = false
    showDialog.value = true
    if (tmdbIdOf(item)) return
    dialogResolving.value = true
    try {
      const media = await resolveRankMedia(rk, item)
      if (!current() || token !== dialogResolveToken.value) return
      dialogItem.value = { rk, item: media }
      if (!tmdbIdOf(media)) dialogResolveError.value = '未找到对应的 TMDB 条目'
    } catch (error) {
      if (current() && token === dialogResolveToken.value) dialogResolveError.value = error?.message || 'TMDB 识别失败'
    } finally {
      if (current() && token === dialogResolveToken.value) dialogResolving.value = false
    }
  }

  return { dialogItem, showDialog, dialogResolving, dialogResolveError, dialogResolveToken, showActionDialog }
}
