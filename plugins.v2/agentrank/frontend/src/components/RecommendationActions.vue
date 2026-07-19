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

function openExternal(url) {
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}

function openTmdb() {
  if (!tmdbId.value) return
  const mediaPath = props.item?.media_type === 'movie' ? 'movie' : 'tv'
  openExternal(`https://www.themoviedb.org/${mediaPath}/${encodeURIComponent(tmdbId.value)}`)
}

function openSource() {
  if (!sourceId.value) return
  if (sourceLabel.value === 'Bgm') {
    openExternal(`https://bgm.tv/subject/${encodeURIComponent(sourceId.value)}`)
    return
  }
  openExternal(`https://www.douban.com/doubanapp/dispatch?uri=/movie/${encodeURIComponent(sourceId.value)}?from=mdouban&open=app`)
}
</script>

<template>
  <div class="ar-actions" role="group" :aria-label="`${item.title} 操作`">
    <VBtn :size="size" variant="tonal" color="primary" class="ar-actions__button ar-actions__button--command text-none" prepend-icon="mdi-bookmark-plus-outline" :loading="loadingAction === 'subscribe'" @click="emit('subscribe', item.candidate_id)">订阅</VBtn>
    <VTooltip text="打开 TMDB" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn v-bind="tooltipProps" :size="size" icon="mdi-movie-open-outline" variant="tonal" color="info" class="ar-actions__icon" :disabled="!tmdbId" aria-label="打开 TMDB" @click="openTmdb" />
      </template>
    </VTooltip>
    <VTooltip :text="`打开${sourceLabel}`" location="top">
      <template #activator="{ props: tooltipProps }">
        <VBtn v-bind="tooltipProps" :size="size" icon="mdi-open-in-new" variant="tonal" :color="sourceColor" class="ar-actions__icon" :disabled="!sourceId" :aria-label="`打开${sourceLabel}`" @click="openSource" />
      </template>
    </VTooltip>
    <VBtn :size="size" variant="tonal" color="default" class="ar-actions__button ar-actions__button--command text-none" prepend-icon="mdi-eye-off-outline" :loading="loadingAction === 'archive'" @click="emit('archive', item.candidate_id)">忽略</VBtn>
  </div>
</template>

<style scoped>
.ar-actions { width: max-content; max-width: 100%; display: flex; flex-wrap: nowrap; align-items: center; gap: 5px; }
.ar-actions__button--command { min-width: 72px; padding-inline: 8px; }
.ar-actions__icon { flex: 0 0 auto; }
@media (max-width: 760px) {
  .ar-actions { width: 100%; justify-content: flex-end; }
  .ar-actions__button--command { min-width: 68px; }
}
</style>
