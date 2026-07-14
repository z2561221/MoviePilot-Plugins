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
    <VBtn :size="size" variant="tonal" color="primary" class="ar-actions__button text-none" :loading="loadingAction === 'subscribe'" @click="emit('subscribe', item.candidate_id)">订阅</VBtn>
    <VBtn :size="size" variant="tonal" color="info" class="ar-actions__button text-none" :disabled="!tmdbId" @click="openTmdb">TMDB</VBtn>
    <VBtn :size="size" variant="tonal" :color="sourceColor" class="ar-actions__button text-none" :disabled="!sourceId" @click="openSource">{{ sourceLabel }}</VBtn>
    <VBtn :size="size" variant="tonal" color="default" class="ar-actions__button text-none" :loading="loadingAction === 'archive'" @click="emit('archive', item.candidate_id)">忽略</VBtn>
  </div>
</template>

<style scoped>
.ar-actions { display: flex; flex-wrap: nowrap; align-items: center; gap: 4px; }
.ar-actions__button { min-width: 48px; padding-inline: 7px; }
</style>
