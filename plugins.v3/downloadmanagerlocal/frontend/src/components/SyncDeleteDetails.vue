<script setup>
defineProps({ job: { type: Object, required: true } })
const labels = { pending: '待执行', deleted: '已删除', absent: '已不存在', removed: '已移除', paused: '保留并暂停' }
const label = state => labels[state] || state
const dateText = stamp => stamp ? new Date(stamp * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '—'
</script>

<template>
  <div class="dm-sync-details dm-history-detail">
    <div v-if="job.resolution" class="dm-history-entry-meta">{{ job.resolution.actor }} · {{ dateText(job.resolution.resolved_at) }}<span v-if="job.resolution.reason && job.resolution.reason !== '用户忽略'"> · {{ job.resolution.reason }}</span></div>
    <template v-for="(path, index) in job.event?.paths || []" :key="`source:${index}`">
      <div class="dm-sync-detail-path mt-2">事件路径 · {{ path }}</div>
      <div v-if="job.event?.original_paths?.[index] && job.event.original_paths[index] !== path" class="dm-sync-detail-path mt-2">历史源路径 · {{ job.event.original_paths[index] }} → {{ path }}</div>
    </template>
    <div v-for="file in [...(job.plan?.cloud_files || []), ...(job.plan?.source_files || [])]" :key="`${file.storage}:${file.path}`" class="dm-sync-detail-path mt-2">{{ label(file.status) }} · {{ file.storage }} · {{ file.path }}</div>
    <div v-for="task in job.plan?.tasks || []" :key="`${task.downloader}:${task.id}`" class="dm-sync-detail-path mt-2">{{ label(task.status) }} · {{ task.downloader }} · {{ task.id }}</div>
    <div class="text-caption mt-2">整理记录已处理 {{ job.records_done?.length || 0 }} / {{ job.plan?.records?.length || 0 }}</div>
    <div v-if="job.plan?.download_records?.length" class="text-caption mt-2">旧下载记录已标记 {{ job.download_records_done?.length || 0 }} / {{ job.plan.download_records.length }}</div>
  </div>
</template>

<style scoped>
.dm-sync-detail-path { overflow-wrap: anywhere; font-size: 12px; line-height: 1.5; }
</style>
