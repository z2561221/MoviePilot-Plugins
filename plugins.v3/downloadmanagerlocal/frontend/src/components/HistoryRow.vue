<script setup>
import { ref } from 'vue'

defineProps({
  time: String,
  name: String,
  status: String,
  color: String,
})
const expanded = ref(false)
</script>

<template>
  <article class="dm-history-row">
    <div class="dm-history-summary">
      <span class="dm-history-time" :title="time">{{ time || '—' }}</span>
      <strong class="dm-history-name" :title="name">{{ name || '—' }}</strong>
      <VChip class="dm-history-status" size="x-small" variant="tonal" :color="color" :title="status">{{ status || '—' }}</VChip>
      <VBtn class="dm-history-toggle" size="small" variant="text" color="primary"
        :aria-expanded="expanded" :aria-label="(expanded ? '收起明细 · ' : '查看明细 · ') + (name || '记录')"
        @click="expanded = !expanded">{{ expanded ? '收起' : '明细' }}</VBtn>
    </div>
    <div v-if="expanded" class="dm-history-expanded">
      <strong>{{ name || '—' }}</strong>
      <div class="dm-history-entry-meta">{{ time || '—' }} · {{ status || '—' }}</div>
      <slot />
    </div>
  </article>
</template>
