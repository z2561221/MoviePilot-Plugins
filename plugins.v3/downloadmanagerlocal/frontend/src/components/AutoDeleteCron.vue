<script setup>
import { ref, watch } from 'vue'
const props = defineProps({ modelValue: { type: String, default: '' }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const preset = ref('custom')
const minute = ref(0)
const hour = ref(3)
const day = ref(0)
const choices = [{ title: '每天指定时间', value: 'daily' }, { title: '每小时', value: 'hourly' }, { title: '每周', value: 'weekly' }, { title: '自定义表达式', value: 'custom' }]
function publish() {
  if (preset.value === 'custom') return
  const min = Math.max(0, Math.min(59, Number(minute.value) || 0))
  const h = Math.max(0, Math.min(23, Number(hour.value) || 0))
  emit('update:modelValue', preset.value === 'hourly' ? `${min} * * * *` : preset.value === 'daily' ? `${min} ${h} * * *` : `${min} ${h} * * ${day.value}`)
}
watch(() => props.modelValue, value => {
  const fields = String(value || '').trim().split(/\s+/)
  if (fields.length !== 5 || !/^\d+$/.test(fields[0]) || fields[2] !== '*' || fields[3] !== '*') { preset.value = 'custom'; return }
  minute.value = Number(fields[0])
  if (fields[1] === '*' && fields[4] === '*') preset.value = 'hourly'
  else if (/^\d+$/.test(fields[1])) { hour.value = Number(fields[1]); preset.value = fields[4] === '*' ? 'daily' : /^\d$/.test(fields[4]) ? 'weekly' : 'custom'; if (preset.value === 'weekly') day.value = Number(fields[4]) }
  else preset.value = 'custom'
}, { immediate: true })
</script>
<template>
  <div class="dm-auto-cron">
    <VSelect v-model="preset" :disabled="disabled" :items="choices" label="Cron 可视化周期" variant="outlined" density="compact" hide-details @update:model-value="publish" />
    <div v-if="preset !== 'custom'" class="dm-auto-cron-time">
      <VSelect v-if="preset === 'weekly'" v-model="day" :disabled="disabled" :items="['周一','周二','周三','周四','周五','周六','周日'].map((title, value) => ({title,value}))" label="星期" variant="outlined" density="compact" hide-details @update:model-value="publish" />
      <VTextField v-if="preset !== 'hourly'" v-model.number="hour" :disabled="disabled" type="number" min="0" max="23" label="时" variant="outlined" density="compact" hide-details @update:model-value="publish" />
      <VTextField v-model.number="minute" :disabled="disabled" type="number" min="0" max="59" label="分" variant="outlined" density="compact" hide-details @update:model-value="publish" />
    </div>
    <VTextField :model-value="modelValue" :disabled="disabled" label="Cron 表达式 · 上海时间" density="compact" variant="outlined" hint="分 时 日 月 周；周一为 0。可直接编辑任意标准五段表达式。" persistent-hint @update:model-value="emit('update:modelValue', $event)" />
  </div>
</template>
<style scoped>
.dm-auto-cron { display: grid; gap: 8px; }
.dm-auto-cron-time { display: flex; gap: 8px; }
.dm-auto-cron-time > * { min-width: 80px; }
</style>
