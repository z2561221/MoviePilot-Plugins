<script setup>
defineProps({
  page: { type: Object, required: true },
})
</script>

<template>
  <template v-if="page.archivePage">
    <div class="dc-section dc-section--archive">
      <div class="dc-section-title mb-2">归档记录 <span class="text-caption font-weight-regular text-medium-emphasis">（共 {{ page.archiveData.total || 0 }} 条）</span></div>
      <div v-if="page.archiveData.items && page.archiveData.items.length" class="dc-history-list">
        <div v-for="(item, i) in page.archiveData.items" :key="item.id || i" class="dc-history-row dc-archive-row">
          <VAvatar rounded="sm" class="dc-history-poster mr-2 flex-shrink-0" :color="page.archiveColor(item)" variant="tonal">
            <VImg v-if="page.archivePoster(item)" :src="page.archivePoster(item)" cover />
            <VIcon v-else :icon="page.archiveIcon(item)" size="14" />
          </VAvatar>
          <div class="dc-history-info">
            <div class="dc-history-title">{{ page.archiveTitle(item) }}</div>
            <div class="dc-history-meta">
              <VChip size="x-small" :color="page.archiveColor(item)" variant="tonal" class="mr-1">{{ page.archiveSourceName(item) }}</VChip>
              <VChip v-if="page.archiveRankName(item)" size="x-small" :style="page.rankChipStyle(page.archiveRankKey(item))" variant="tonal" class="dc-rank-chip mr-1">{{ page.archiveRankName(item) }}</VChip>
              <span class="text-caption text-medium-emphasis">{{ page.archiveTime(item) ? page.archiveTime(item).split(' ')[0] : '' }}</span>
              <span v-if="item.archived_at" class="text-caption text-medium-emphasis">归档 {{ item.archived_at.split(' ')[0] }}</span>
            </div>
          </div>
          <VChip size="x-small" :color="page.archiveColor(item)" variant="tonal" class="dc-row-status">{{ page.archiveStatus(item) }}</VChip>
          <VBtn icon="mdi-restore" variant="text" size="x-small" color="primary" class="dc-row-action" :loading="page.actionKey === page.rowKey('archive-restore', item, i)" @click="page.restoreArchive(item, i)" />
          <VBtn icon="mdi-delete-outline" variant="text" size="x-small" color="error" class="dc-row-action" :loading="page.actionKey === page.rowKey('archive-delete', item, i)" @click="page.deleteArchive(item, i)" />
        </div>
      </div>
      <div v-else-if="!page.loading" class="text-center text-medium-emphasis py-4 text-caption">暂无归档记录</div>
      <div v-if="page.archiveData.total_pages > 1" class="dc-pagination">
        <VBtn icon="mdi-chevron-left" variant="text" size="x-small" title="上一页" aria-label="上一页" :disabled="page.archiveData.page <= 1" @click="page.goArchivePage(page.archiveData.page - 1)" />
        <span class="dc-pagination-label">{{ page.archiveData.page }} / {{ page.archiveData.total_pages }}</span>
        <VBtn icon="mdi-chevron-right" variant="text" size="x-small" title="下一页" aria-label="下一页" :disabled="page.archiveData.page >= page.archiveData.total_pages" @click="page.goArchivePage(page.archiveData.page + 1)" />
      </div>
    </div>
  </template>

  <template v-else>
    <div v-if="page.stats" class="dc-section dc-section--stats">
      <div class="dc-section-title mb-2">订阅统计</div>
      <div class="dc-stats-grid">
        <div class="dc-stat-card"><div class="dc-stat-value">{{ page.stats.total || 0 }}</div><div class="dc-stat-label">总订阅数</div></div>
        <div class="dc-stat-card"><div class="dc-stat-value">{{ page.stats.month_new || 0 }}</div><div class="dc-stat-label">本月新增</div></div>
        <div v-for="item in (page.stats.rank_stats || [])" :key="item.key" class="dc-stat-card">
          <div class="dc-stat-value" :style="{ color: page.rankColorOf(item.key) }">{{ item.count }}</div>
          <div class="dc-stat-label">{{ item.name || page.rankNameOf(item.key) }}</div>
        </div>
      </div>
    </div>

    <div v-if="page.rankHistory && Object.keys(page.rankHistory).length" class="dc-section dc-section--rank">
      <div class="dc-section-title mb-2">榜单快照 <span class="text-caption font-weight-regular text-medium-emphasis">（点击条目订阅或打开来源）</span></div>
      <div class="dc-rank-grid dc-rank-grid--snapshot">
        <div v-for="[key, items] in Object.entries(page.rankHistory)" :key="key" class="dc-rank-card">
          <div class="dc-rank-head"><VIcon icon="mdi-format-list-numbered" size="15" :style="page.rankIconStyle(key)" class="mr-1" /><span>{{ page.rankNameOf(key, items?.[0]) }}</span></div>
          <template v-if="items && items.length">
            <div v-for="(item, i) in items.slice(0, 5)" :key="`${key}-${i}`" class="dc-rank-row" title="订阅 / 打开详情" @click="page.showActionDialog(key, item)">
              <VAvatar rounded="sm" class="dc-rank-poster"><VImg v-if="item.poster" :src="page.toPosterThumbnail(item.poster)" cover /><VIcon v-else icon="mdi-filmstrip" size="13" /></VAvatar>
              <span class="dc-rank-title">{{ item.title || '' }}</span>
              <span v-if="key === 'coming' && item.wish_count" class="dc-rank-wish">{{ item.wish_count }}</span>
            </div>
          </template>
          <div v-else class="dc-rank-empty">暂无榜单数据</div>
        </div>
      </div>
    </div>

    <div class="dc-section dc-section--blacklist">
      <div class="dc-section-title mb-2 dc-title-with-chips">
        黑名拦截
        <span class="text-caption font-weight-regular text-medium-emphasis">（关键词 {{ page.blacklistKeywords.length }} 个，最近命中 {{ page.blacklistEntries.length }} 条）</span>
        <VChip v-for="(word, i) in page.blacklistKeywords" :key="`${word}-${i}`" size="x-small" color="error" variant="tonal" class="dc-blacklist-chip">{{ word }}</VChip>
      </div>
      <div v-if="page.blacklistEntries && page.blacklistEntries.length" class="dc-history-list">
        <div v-for="(item, i) in page.blacklistEntries" :key="i" class="dc-history-row dc-status-row">
          <VAvatar size="28" class="mr-2 flex-shrink-0" color="error" variant="tonal"><VIcon icon="mdi-block-helper" size="14" /></VAvatar>
          <div class="dc-history-info"><div class="dc-history-title">{{ item.title || '未命名条目' }}</div><div class="dc-history-meta"><span class="text-caption text-medium-emphasis">{{ item.time || '' }}</span></div></div>
          <VChip size="x-small" color="error" variant="tonal" class="dc-row-status">{{ item.detail || item.reason || '黑名拦截' }}</VChip>
          <VBtn icon="mdi-delete-outline" variant="text" size="x-small" color="error" class="dc-row-action" :loading="page.actionKey === page.rowKey('log', item, i)" @click="page.deleteAntiCheatLog(item, i)" />
        </div>
      </div>
      <div v-else-if="!page.loading" class="text-center text-medium-emphasis py-4 text-caption">暂无被黑名单筛选的条目</div>
    </div>

    <div class="dc-section dc-section--observe">
      <div class="dc-section-title mb-2">观察队列 <span class="text-caption font-weight-regular text-medium-emphasis">（待自动订阅 {{ page.pendingObservations.length }} 条）</span></div>
      <div v-if="page.pendingObservations && page.pendingObservations.length" class="dc-history-list">
        <div v-for="(item, i) in page.pendingObservations" :key="i" class="dc-history-row dc-status-row dc-history-row--clickable" @click="page.showActionDialog(item.rank_key, item)">
          <VAvatar size="28" class="mr-2 flex-shrink-0" color="warning" variant="tonal"><VIcon icon="mdi-clock-outline" size="14" /></VAvatar>
          <div class="dc-history-info">
            <div class="dc-history-title">{{ item.title }}</div>
            <div class="dc-history-meta"><VChip size="x-small" :style="page.rankChipStyle(item.rank_key)" variant="tonal" class="dc-rank-chip mr-1">{{ item.rank_name || page.rankNameOf(item.rank_key, item) }}</VChip><span class="text-caption text-medium-emphasis">观察 {{ item.elapsed_days || 0 }} / {{ item.observe_days || 0 }} 天</span></div>
          </div>
          <VChip size="x-small" color="warning" variant="tonal" class="dc-row-status">剩余 {{ item.remaining_days || 0 }} 天</VChip>
          <VBtn icon="mdi-delete-outline" variant="text" size="x-small" color="error" class="dc-row-action" :loading="page.actionKey === page.rowKey('obs', item, i)" @click.stop="page.deleteObservation(item, i)" />
        </div>
      </div>
      <div v-else-if="!page.loading" class="text-center text-medium-emphasis py-4 text-caption">暂无观察期条目</div>
    </div>

    <div class="dc-section dc-section--history">
      <div class="dc-section-title mb-2">订阅历史 <span class="text-caption font-weight-regular text-medium-emphasis">（共 {{ page.historyData.total }} 条）</span></div>
      <div v-if="page.historyData.items && page.historyData.items.length" class="dc-history-list">
        <div v-for="(item, i) in page.historyData.items" :key="i" class="dc-history-row dc-status-row">
          <VAvatar rounded="sm" class="dc-history-poster mr-2 flex-shrink-0"><VImg v-if="item.poster" :src="page.toPosterThumbnail(item.poster)" cover /><VIcon v-else icon="mdi-filmstrip" size="14" /></VAvatar>
          <div class="dc-history-info">
            <div class="dc-history-title">{{ item.title }}</div>
            <div class="dc-history-meta"><VChip size="x-small" :style="page.rankChipStyle(item.rank_key)" variant="tonal" class="dc-rank-chip mr-1">{{ item.rank_name || page.rankNameOf(item.rank_key, item) }}</VChip><span class="text-caption text-medium-emphasis">{{ item.time ? item.time.split(' ')[0] : '' }}</span></div>
          </div>
          <VChip size="x-small" :color="item.status === 'failed' ? 'error' : 'success'" variant="tonal" class="dc-row-status">{{ item.status === 'failed' ? '订阅失败' : '订阅成功' }}</VChip>
          <VBtn icon="mdi-delete-outline" variant="text" size="x-small" color="error" class="dc-row-action" :loading="page.actionKey === page.rowKey('sub', item, i)" @click="page.deleteSubscribeHistory(item, i)" />
        </div>
      </div>
      <div v-else-if="!page.loading" class="text-center text-medium-emphasis py-4 text-caption">暂无订阅记录</div>
      <div v-if="page.historyData.total_pages > 1" class="d-flex justify-center mt-2">
        <VBtn variant="text" size="x-small" :disabled="page.historyData.page <= 1" class="mx-1" @click="page.goPage(page.historyData.page - 1)">上一页</VBtn>
        <span class="d-flex align-center mx-2 text-caption text-medium-emphasis">{{ page.historyData.page }} / {{ page.historyData.total_pages }}</span>
        <VBtn variant="text" size="x-small" :disabled="page.historyData.page >= page.historyData.total_pages" class="mx-1" @click="page.goPage(page.historyData.page + 1)">下一页</VBtn>
      </div>
    </div>

    <div class="dc-section dc-section--logs">
      <div class="dc-section-title mb-2">观察日志 <span class="text-caption font-weight-regular text-medium-emphasis">（最近 {{ page.cheatLogs.length }} 条）</span></div>
      <div v-if="page.cheatLogs && page.cheatLogs.length" class="dc-history-list">
        <div v-for="(log, i) in page.cheatLogs.slice().reverse()" :key="i" class="dc-history-row dc-status-row">
          <VAvatar rounded="sm" class="dc-history-poster mr-2 flex-shrink-0"><VImg v-if="log.poster" :src="page.toPosterThumbnail(log.poster)" cover /><VIcon v-else icon="mdi-filmstrip" size="14" /></VAvatar>
          <div class="dc-history-info"><div class="dc-history-title">{{ log.title }}</div><div class="dc-history-meta"><VChip size="x-small" :style="page.rankChipStyle(log.rank_key)" variant="tonal" class="dc-rank-chip mr-1">{{ log.rank_name || log.rank_key || '观察日志' }}</VChip><span class="text-caption text-medium-emphasis">{{ log.time ? log.time.split(' ')[0] : '' }}</span></div></div>
          <VChip size="x-small" color="warning" variant="tonal" class="dc-row-status">{{ log.reason || '观察日志' }}</VChip>
          <VBtn icon="mdi-delete-outline" variant="text" size="x-small" color="error" class="dc-row-action" :loading="page.actionKey === page.rowKey('log', log, i)" @click="page.deleteAntiCheatLog(log, i)" />
        </div>
      </div>
      <div v-else-if="!page.loading" class="text-center text-medium-emphasis py-4 text-caption">暂无观察日志</div>
    </div>
  </template>
</template>

<style scoped>
.dc-section { border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .72)); border-radius: 8px; padding: 12px; margin-bottom: 0; background: rgba(var(--v-theme-on-surface), .012); min-width: 0; }
.dc-section--archive { order: 0; grid-column: 1 / -1; }
.dc-section--rank { order: 1; grid-column: 1 / -1; }
.dc-section--blacklist { order: 2; }
.dc-section--observe { order: 3; }
.dc-section--history { order: 4; }
.dc-section--logs { order: 5; }
.dc-section--stats { order: 6; grid-column: 1 / -1; }
.dc-section-title { display: flex; align-items: center; gap: 6px; min-height: 28px; padding-bottom: 8px; margin-bottom: 8px !important; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .42)); font-size: 14px; font-weight: 600; color: rgb(var(--v-theme-primary)); line-height: 1.25; flex-wrap: wrap; }
.dc-section-title::before { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 6px; background: rgba(var(--v-theme-primary), .12); color: rgb(var(--v-theme-primary)); font-size: 12px; font-weight: 700; flex: 0 0 22px; }
.dc-section--archive .dc-section-title::before { content: "归"; font-size: 11px; }
.dc-section--rank .dc-section-title::before { content: "1"; }
.dc-section--blacklist .dc-section-title::before { content: "2"; }
.dc-section--observe .dc-section-title::before { content: "3"; }
.dc-section--history .dc-section-title::before { content: "4"; }
.dc-section--logs .dc-section-title::before { content: "5"; }
.dc-section--stats .dc-section-title::before { content: "6"; }
.dc-title-with-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.dc-blacklist-chip { max-width: 120px; }
.dc-stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: 8px; }
.dc-stat-card { border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .5)); border-radius: 8px; padding: 9px 8px; text-align: center; background: rgba(var(--v-theme-on-surface), .01); }
.dc-stat-value { font-size: 18px; font-weight: 700; color: rgb(var(--v-theme-primary)); }
.dc-stat-label { font-size: 11px; color: rgba(var(--v-theme-on-surface), .5); margin-top: 2px; }
.dc-rank-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 6px; }
.dc-rank-card { border: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * .6)); border-radius: 8px; padding: 6px; min-width: 0; }
.dc-rank-head { display: flex; align-items: center; font-size: 13px; font-weight: 600; margin-bottom: 5px; }
.dc-rank-row { display: flex; align-items: center; gap: 4px; min-width: 0; min-height: 42px; padding: 3px 4px; border-radius: 6px; cursor: pointer; }
.dc-rank-row:hover { background: rgba(var(--v-theme-primary), .07); }
.dc-rank-poster, .dc-history-poster { flex: 0 0 24px !important; width: 24px !important; height: 36px !important; min-width: 24px; min-height: 36px; aspect-ratio: 2 / 3; border-radius: 3px !important; background: rgba(var(--v-theme-on-surface), .08); overflow: hidden; }
.dc-rank-title { display: -webkit-box; flex: 1 1 auto; min-width: 0; font-size: 12px; font-weight: 500; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 2; white-space: normal; overflow-wrap: anywhere; }
.dc-rank-wish { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), .45); font-size: 11px; white-space: nowrap; font-variant-numeric: tabular-nums; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
.dc-rank-empty { font-size: 12px; color: rgba(var(--v-theme-on-surface), .5); padding: 8px; text-align: center; }
.dc-history-list { display: flex; flex-direction: column; gap: 4px; }
.dc-history-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; column-gap: 4px; min-height: 40px; padding: 5px 6px; border-radius: 6px; transition: background .12s; }
.dc-archive-row { grid-template-columns: auto minmax(0, 1fr) auto auto auto; }
.dc-status-row { grid-template-columns: auto minmax(0, 1fr) auto auto; }
.dc-history-row--clickable { cursor: pointer; }
.dc-history-row:hover { background: rgba(var(--v-theme-primary), .04); }
.dc-history-info { min-width: 0; }
.dc-history-title { font-size: 13px; font-weight: 500; line-height: 1.25; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dc-history-meta { display: flex; align-items: center; gap: 4px; margin-top: 1px; min-width: 0; overflow: hidden; }
.dc-pagination { display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 32px; margin-top: 8px; }
.dc-pagination-label { min-width: 48px; text-align: center; font-size: 12px; color: rgba(var(--v-theme-on-surface), .62); font-variant-numeric: tabular-nums; }
.dc-rank-chip { border: 1px solid; font-weight: 700; }
.dc-row-status { max-width: 160px; }
.dc-row-action { flex: 0 0 auto; }
@media (max-width: 760px) {
  .dc-section { grid-column: 1 / -1; padding: 10px; }
  .dc-section--blacklist, .dc-section--observe, .dc-section--history, .dc-section--logs { grid-column: 1 / -1; }
  .dc-rank-grid { grid-template-columns: minmax(0, 1fr); overflow-x: visible; padding-bottom: 0; }
  .dc-rank-card { width: 100%; }
  .dc-rank-grid--snapshot { display: flex; flex-wrap: nowrap; gap: 8px; overflow-x: auto; overflow-y: hidden; padding-bottom: 4px; scrollbar-width: none; -ms-overflow-style: none; touch-action: pan-x; overscroll-behavior-x: contain; }
  .dc-rank-grid--snapshot::-webkit-scrollbar { display: none; }
  .dc-rank-grid--snapshot .dc-rank-card { flex: 0 0 calc((100% - 8px) / 2); width: calc((100% - 8px) / 2); }
  .dc-history-row { grid-template-columns: auto minmax(0, 1fr) auto; column-gap: 4px; padding: 4px 6px; }
  .dc-archive-row { grid-template-columns: auto minmax(0, 1fr) auto auto auto; }
  .dc-status-row { grid-template-columns: auto minmax(0, 1fr) auto auto; }
  .dc-row-status { max-width: 96px; }
  .dc-history-meta :deep(.v-chip) { max-width: 120px; }
  .dc-history-row span.text-caption { display: none; }
}
@media (max-width: 360px) {
  .dc-rank-grid--snapshot .dc-rank-card { flex-basis: 100%; width: 100%; }
}
</style>
