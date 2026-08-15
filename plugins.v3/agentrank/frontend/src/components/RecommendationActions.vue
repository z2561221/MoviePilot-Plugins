<script setup>
import { computed, inject, ref } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
  loadingAction: { type: String, default: '' },
  size: { type: String, default: 'x-small' },
  nativeSubscribe: { type: Function, default: null },
})
const emit = defineEmits(['subscribe', 'archive', 'like', 'dislike', 'native-subscribe-opened'])

const injectedNativeSubscribe = inject('moviepilot:nativeSubscribe', null)
const nativeSubscribePending = ref(false)

function firstId(...values) {
  for (const value of values) {
    if (value === null || value === undefined) continue
    const text = String(value).trim()
    if (text && text !== '0') return text
  }
  return ''
}

const sourceIds = computed(() => {
  const raw = props.item?.source_ids || {}
  const value = { ...raw }
  const aliases = {
    tmdb: ['tmdb', 'tmdb_id', 'tmdbid', 'themoviedb', 'themoviedb_id'],
    douban: ['douban', 'douban_id', 'doubanid'],
    bangumi: ['bangumi', 'bangumi_id', 'bangumiid', 'bgm', 'bgm_id'],
    anilist: ['anilist', 'anilist_id', 'anilistid'],
  }
  Object.entries(aliases).forEach(([canonical, names]) => {
    if (firstId(value[canonical])) return
    const match = names.map(name => value[name]).find(valueForAlias => firstId(valueForAlias))
    if (match !== undefined) value[canonical] = match
  })
  Object.entries(aliases).forEach(([canonical, names]) => {
    if (firstId(value[canonical])) return
    const match = [props.item?.[canonical], ...names.map(name => props.item?.[name])]
      .find(valueForAlias => firstId(valueForAlias))
    if (match !== undefined) value[canonical] = match
  })
  return value
})

const tmdbId = computed(() => firstId(sourceIds.value.tmdb))
const doubanId = computed(() => firstId(sourceIds.value.douban))
const bangumiId = computed(() => firstId(sourceIds.value.bangumi))
const anilistId = computed(() => firstId(sourceIds.value.anilist))
const nativeSubscribe = computed(() => props.nativeSubscribe || injectedNativeSubscribe)
const nativeMediaType = computed(() => props.item?.media_type === 'movie' ? '电影' : '电视剧')
const alreadySubscribed = computed(() => props.item?.subscribed === true)
const likePressed = computed(() => props.item?.feedback_kind === 'like')
const dislikePressed = computed(() => props.item?.feedback_kind === 'dislike')
const likeLoading = computed(() => props.loadingAction === `feedback:like:${props.item?.candidate_id}`)
const dislikeLoading = computed(() => props.loadingAction === `feedback:dislike:${props.item?.candidate_id}`)
const actionBusy = computed(() => Boolean(props.loadingAction))

const nativeMedia = computed(() => {
  const explicitSource = String(props.item?.media_source || '').trim()
  const explicitId = firstId(props.item?.media_id)
  const fallbackId = tmdbId.value || doubanId.value || bangumiId.value || anilistId.value
  const fallbackSource = tmdbId.value
    ? 'themoviedb'
    : doubanId.value
      ? 'douban'
      : bangumiId.value
        ? 'bangumi'
        : anilistId.value
          ? 'anilist'
          : ''
  const source = explicitSource && explicitId ? explicitSource : fallbackSource
  const sourceId = explicitSource && explicitId ? explicitId : fallbackId
  const media = {
    title: String(props.item?.title || props.item?.name || '').trim(),
    name: String(props.item?.title || props.item?.name || '').trim(),
    type: nativeMediaType.value,
    media_type: props.item?.media_type || '',
    year: props.item?.year ? String(props.item.year) : '',
    poster_path: String(props.item?.poster_path || '').trim(),
  }
  if (source && sourceId) {
    media.media_source = source
    media.media_id = sourceId
  }
  if (tmdbId.value) {
    media.tmdb_id = tmdbId.value
  }
  if (doubanId.value) {
    media.douban_id = doubanId.value
  }
  if (bangumiId.value) {
    media.bangumi_id = bangumiId.value
  }
  if (anilistId.value) {
    media.anilist_id = anilistId.value
  }
  return media
})

function openExternal(url) {
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}

function openTmdb() {
  if (!tmdbId.value) return
  const mediaPath = props.item?.media_type === 'movie' ? 'movie' : 'tv'
  openExternal(`https://www.themoviedb.org/${mediaPath}/${encodeURIComponent(tmdbId.value)}`)
}

/** 先调用宿主原生订阅，无效媒体才回退插件安全链。 */
async function handleSubscribe() {
  if (nativeSubscribePending.value) return
  const callback = nativeSubscribe.value
  if (typeof callback !== 'function') {
    emit('subscribe', props.item?.candidate_id)
    return
  }
  nativeSubscribePending.value = true
  try {
    const result = await callback(nativeMedia.value)
    if (result?.success === true) {
      emit('native-subscribe-opened', props.item?.candidate_id)
      return
    }
    if (result?.code === 'PERMISSION_DENIED') return
    emit('subscribe', props.item?.candidate_id)
  } catch (_) {
    emit('subscribe', props.item?.candidate_id)
  } finally {
    nativeSubscribePending.value = false
  }
}
</script>

<template>
  <div class="ar-actions" role="group" :aria-label="`${item.title} 操作`">
    <VTooltip text="订阅" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn v-bind="tooltipProps" :size="size" variant="tonal" color="primary" class="ar-actions__button text-none" :prepend-icon="alreadySubscribed ? 'mdi-bookmark-check-outline' : 'mdi-bookmark-plus-outline'" :loading="loadingAction === 'subscribe' || nativeSubscribePending" :disabled="alreadySubscribed || (actionBusy && loadingAction !== 'subscribe')" :aria-label="alreadySubscribed ? '已订阅' : '订阅'" @click="handleSubscribe"><span class="ar-actions__label">{{ alreadySubscribed ? '已订阅' : '订阅' }}</span></VBtn>
      </template>
    </VTooltip>
    <VTooltip text="打开 TMDB" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn v-bind="tooltipProps" :size="size" prepend-icon="mdi-movie-open-outline" variant="tonal" class="ar-actions__button ar-actions__button--tmdb text-none" :disabled="!tmdbId" aria-label="打开 TMDB" @click="openTmdb"><span class="ar-actions__label">TMDB</span></VBtn>
      </template>
    </VTooltip>
    <VTooltip text="忽略" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn v-bind="tooltipProps" :size="size" variant="tonal" color="default" class="ar-actions__button text-none" prepend-icon="mdi-eye-off-outline" :loading="loadingAction === 'archive'" :disabled="actionBusy && loadingAction !== 'archive'" aria-label="忽略" @click="emit('archive', item.candidate_id)"><span class="ar-actions__label">忽略</span></VBtn>
      </template>
    </VTooltip>
    <VTooltip :text="likePressed ? '已点赞' : '点赞'" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn
          v-bind="tooltipProps"
          :size="size"
          variant="tonal"
          :color="likePressed ? 'primary' : 'default'"
          class="ar-actions__button text-none"
          :prepend-icon="likePressed ? 'mdi-thumb-up' : 'mdi-thumb-up-outline'"
          :loading="likeLoading"
          :disabled="actionBusy && !likeLoading"
          :aria-label="likePressed ? '已点赞' : '点赞'"
          :aria-pressed="likePressed ? 'true' : 'false'"
          @click="emit('like', item.candidate_id)"
        ><span class="ar-actions__label">点赞</span></VBtn>
      </template>
    </VTooltip>
    <VTooltip :text="dislikePressed ? '已点踩' : '点踩'" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn
          v-bind="tooltipProps"
          :size="size"
          variant="tonal"
          :color="dislikePressed ? 'primary' : 'default'"
          class="ar-actions__button text-none"
          :prepend-icon="dislikePressed ? 'mdi-thumb-down' : 'mdi-thumb-down-outline'"
          :loading="dislikeLoading"
          :disabled="actionBusy && !dislikeLoading"
          :aria-label="dislikePressed ? '已点踩' : '点踩'"
          :aria-pressed="dislikePressed ? 'true' : 'false'"
          @click="emit('dislike', item.candidate_id)"
        ><span class="ar-actions__label">点踩</span></VBtn>
      </template>
    </VTooltip>
  </div>
</template>

<style scoped>
.ar-actions { width: max-content; max-width: 100%; display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 5px; }
.ar-actions__button { flex: 0 0 auto; min-width: 68px; min-height: 40px; padding-inline: 8px; }
.ar-actions__button--tmdb {
  color: #0288d1 !important;
  color: color-mix(in srgb, #0288d1 78%, rgb(var(--v-theme-on-surface)) 22%) !important;
}
@media (max-width: 760px) {
  .ar-actions__button { min-width: 60px; padding-inline: 5px; }
}
@media (max-width: 390px) {
  .ar-actions { gap: 3px; }
  .ar-actions__button { min-width: 56px; padding-inline: 4px; }
  .ar-actions__button :deep(.v-btn__prepend) { display: none; }
}
</style>
