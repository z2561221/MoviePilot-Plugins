<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
  loadingAction: { type: String, default: '' },
  size: { type: String, default: 'x-small' },
})
const emit = defineEmits(['subscribe', 'archive'])

const sourceIds = computed(() => props.item?.source_ids || {})
const tmdbId = computed(() => sourceIds.value.tmdb || '')
const doubanId = computed(() => sourceIds.value.douban || '')
const bangumiId = computed(() => sourceIds.value.bangumi || '')
const prefersBangumi = computed(() => props.item?.media_type === 'anime' && bangumiId.value)
const sourceLabel = computed(() => prefersBangumi.value || (!doubanId.value && bangumiId.value) ? 'Bgm' : '豆瓣')
const sourceId = computed(() => sourceLabel.value === 'Bgm' ? bangumiId.value : doubanId.value)
const sourceColor = computed(() => sourceLabel.value === 'Bgm' ? '#F838A0' : '#08B810')
const doubanSearchText = computed(() => [props.item?.title, props.item?.year].filter(Boolean).join(' '))
const sourceAvailable = computed(() => sourceLabel.value === 'Bgm' ? Boolean(sourceId.value) : Boolean(sourceId.value || doubanSearchText.value))
const sourceTooltip = computed(() => sourceLabel.value === 'Bgm' || sourceId.value ? `打开${sourceLabel.value}` : '搜索豆瓣')

function openExternal(url) {
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}

function openTmdb() {
  if (!tmdbId.value) return
  const mediaPath = props.item?.media_type === 'movie' ? 'movie' : 'tv'
  openExternal(`https://www.themoviedb.org/${mediaPath}/${encodeURIComponent(tmdbId.value)}`)
}

function openSource() {
  if (sourceLabel.value === 'Bgm') {
    if (!sourceId.value) return
    openExternal(`https://bgm.tv/subject/${encodeURIComponent(sourceId.value)}`)
    return
  }
  if (sourceId.value) {
    openExternal(`https://www.douban.com/doubanapp/dispatch?uri=/movie/${encodeURIComponent(sourceId.value)}?from=mdouban&open=app`)
    return
  }
  if (doubanSearchText.value) {
    openExternal(`https://search.douban.com/movie/subject_search?search_text=${encodeURIComponent(doubanSearchText.value)}&cat=1002`)
  }
}
</script>

<template>
  <div class="ar-actions" role="group" :aria-label="`${item.title} 操作`">
    <VTooltip text="订阅" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn v-bind="tooltipProps" :size="size" variant="tonal" color="primary" class="ar-actions__button text-none" prepend-icon="mdi-bookmark-plus-outline" :loading="loadingAction === 'subscribe'" aria-label="订阅" @click="emit('subscribe', item.candidate_id)"><span class="ar-actions__label">订阅</span></VBtn>
      </template>
    </VTooltip>
    <VTooltip text="打开 TMDB" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn v-bind="tooltipProps" :size="size" prepend-icon="mdi-movie-open-outline" variant="tonal" class="ar-actions__button ar-actions__button--tmdb text-none" :disabled="!tmdbId" aria-label="打开 TMDB" @click="openTmdb"><span class="ar-actions__label">TMDB</span></VBtn>
      </template>
    </VTooltip>
    <VTooltip :text="sourceTooltip" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn v-bind="tooltipProps" :size="size" prepend-icon="mdi-open-in-new" variant="tonal" :color="sourceColor" class="ar-actions__button text-none" :disabled="!sourceAvailable" :aria-label="sourceTooltip" @click="openSource"><span class="ar-actions__label">{{ sourceLabel }}</span></VBtn>
      </template>
    </VTooltip>
    <VTooltip text="忽略" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn v-bind="tooltipProps" :size="size" variant="tonal" color="default" class="ar-actions__button text-none" prepend-icon="mdi-eye-off-outline" :loading="loadingAction === 'archive'" aria-label="忽略" @click="emit('archive', item.candidate_id)"><span class="ar-actions__label">忽略</span></VBtn>
      </template>
    </VTooltip>
  </div>
</template>

<style scoped>
.ar-actions { width: max-content; max-width: 100%; display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 5px; }
.ar-actions__button { flex: 0 0 auto; min-width: 68px; padding-inline: 8px; }
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
