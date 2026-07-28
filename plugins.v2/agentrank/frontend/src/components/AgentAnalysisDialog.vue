<script setup>
import { computed, watch } from 'vue'
import { useDisplay } from 'vuetify'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  state: { type: Object, required: true },
  item: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'comment'])
const { smAndDown } = useDisplay()

const candidateId = computed(() => String(props.item?.candidate_id || ''))
const analysis = computed(() => props.state.currentAnalysis(candidateId.value))
const operation = computed(() => props.state.operationState(`analysis:${candidateId.value}`))

const dimensionLabels = {
  type: '类型', theme: '题材', actor: '演员', director: '主创', region: '地区',
  year: '年代', rating: '评分', heat: '热度', freshness: '新鲜感', similarity: '相似性',
}

function close() {
  emit('update:modelValue', false)
}

function evidenceText(evidence) {
  const dimension = dimensionLabels[evidence?.dimension] || evidence?.dimension || '内容特征'
  const relation = evidence?.direction === 'negative' ? '存在冲突' : '具体匹配'
  return `${dimension}：${evidence?.user_value || '偏好未注明'} 与 ${evidence?.candidate_value || '作品特征未注明'} ${relation}`
}

function requestComment(label, content) {
  emit('comment', { label, content: String(content || '').trim() })
}

async function load() {
  if (!props.modelValue || !candidateId.value || !props.item?.analysis_id) return
  try {
    await props.state.loadAnalysis(candidateId.value, props.item.analysis_id)
  } catch (_) {
    // 共享状态保存可见错误和重试动作。
  }
}

watch(
  () => [props.modelValue, props.item?.analysis_id],
  ([open]) => { if (open) load() },
  { immediate: true },
)
</script>

<template>
  <VDialog
    :model-value="modelValue"
    :fullscreen="smAndDown"
    max-width="780"
    scrollable
    @update:model-value="value => emit('update:modelValue', value)"
  >
    <VCard class="ar-analysis">
      <VToolbar density="compact" class="ar-analysis__toolbar">
        <VIcon icon="mdi-text-box-search-outline" color="primary" class="ms-4 me-3" />
        <div class="ar-analysis__heading">
          <div class="ar-analysis__title">Agent分析</div>
          <div class="ar-analysis__subtitle">{{ item?.title || '当前推荐' }}</div>
        </div>
        <VSpacer />
        <VChip v-if="analysis" size="small" color="primary" variant="tonal" class="me-1">
          {{ analysis.support_percentage }}%
        </VChip>
        <VBtn icon="mdi-close" variant="text" aria-label="关闭 Agent 分析" @click="close" />
      </VToolbar>
      <VDivider />

      <VCardText class="ar-analysis__body">
        <div v-if="operation.loading" class="ar-analysis__state">
          <VProgressCircular indeterminate color="primary" />
        </div>
        <VAlert v-else-if="operation.error" type="error" variant="tonal">
          {{ operation.error.message }}
          <template #append>
            <VBtn variant="text" size="small" @click="props.state.retryOperation('analysis:' + candidateId)">重试</VBtn>
          </template>
        </VAlert>
        <VEmptyState v-else-if="!analysis" icon="mdi-text-box-remove-outline" title="分析暂不可用" />
        <div v-else class="ar-analysis__sections">
          <section class="ar-analysis__summary" @click="requestComment('推荐判断', analysis.reason || analysis.summary)">
            <div class="ar-analysis__section-head">
              <div>
                <div class="ar-analysis__section-title">推荐判断</div>
                <div class="ar-analysis__section-copy">{{ analysis.reason || analysis.summary }}</div>
              </div>
              <VTooltip text="评论这条判断">
                <template #activator="{ props: tooltipProps }">
                  <VBtn v-bind="tooltipProps" icon="mdi-comment-edit-outline" variant="text" aria-label="评论推荐判断" @click.stop="requestComment('推荐判断', analysis.reason || analysis.summary)" />
                </template>
              </VTooltip>
            </div>
          </section>

          <section>
            <div class="ar-analysis__section-title">匹配证据</div>
            <div v-if="analysis.positive_evidence?.length" class="ar-analysis__list">
              <div v-for="(evidence, index) in analysis.positive_evidence" :key="`positive-${index}`" class="ar-analysis__row" @click="requestComment(`匹配证据 ${index + 1}`, evidenceText(evidence))">
                <VIcon icon="mdi-check-circle-outline" color="success" size="20" />
                <div class="ar-analysis__row-main">
                  <div>{{ evidenceText(evidence) }}</div>
                  <div class="ar-analysis__row-meta">贡献 {{ evidence.contribution_units }} · 证据 {{ evidence.user_refs?.length || 0 }} 项</div>
                </div>
                <VTooltip text="评论这条证据">
                  <template #activator="{ props: tooltipProps }">
                    <VBtn v-bind="tooltipProps" icon="mdi-comment-edit-outline" variant="text" size="small" :aria-label="`评论匹配证据 ${index + 1}`" @click.stop="requestComment(`匹配证据 ${index + 1}`, evidenceText(evidence))" />
                  </template>
                </VTooltip>
              </div>
            </div>
            <div v-else class="ar-analysis__empty">没有足够的正向具体证据。</div>
          </section>

          <section>
            <div class="ar-analysis__section-title">反向证据</div>
            <div v-if="analysis.counter_evidence?.length" class="ar-analysis__list">
              <div v-for="(evidence, index) in analysis.counter_evidence" :key="`counter-${index}`" class="ar-analysis__row" @click="requestComment(`反向证据 ${index + 1}`, evidenceText(evidence))">
                <VIcon icon="mdi-alert-circle-outline" color="warning" size="20" />
                <div class="ar-analysis__row-main">{{ evidenceText(evidence) }}</div>
                <VTooltip text="评论这条证据">
                  <template #activator="{ props: tooltipProps }">
                    <VBtn v-bind="tooltipProps" icon="mdi-comment-edit-outline" variant="text" size="small" :aria-label="`评论反向证据 ${index + 1}`" @click.stop="requestComment(`反向证据 ${index + 1}`, evidenceText(evidence))" />
                  </template>
                </VTooltip>
              </div>
            </div>
            <div v-else class="ar-analysis__empty">未发现需要特别提示的反向证据。</div>
          </section>

          <section>
            <div class="ar-analysis__section-title">不确定点</div>
            <div v-if="analysis.uncertainties?.length" class="ar-analysis__list">
              <div v-for="(uncertainty, index) in analysis.uncertainties" :key="`uncertainty-${index}`" class="ar-analysis__row" @click="requestComment(`不确定点 ${index + 1}`, uncertainty)">
                <VIcon icon="mdi-help-circle-outline" color="info" size="20" />
                <div class="ar-analysis__row-main">{{ uncertainty }}</div>
                <VTooltip text="评论这条判断">
                  <template #activator="{ props: tooltipProps }">
                    <VBtn v-bind="tooltipProps" icon="mdi-comment-edit-outline" variant="text" size="small" :aria-label="`评论不确定点 ${index + 1}`" @click.stop="requestComment(`不确定点 ${index + 1}`, uncertainty)" />
                  </template>
                </VTooltip>
              </div>
            </div>
            <div v-else class="ar-analysis__empty">当前没有额外不确定点。</div>
          </section>

          <div class="ar-analysis__provenance">
            <span>选择：{{ analysis.selection_source === 'agent' ? 'Agent排序' : '安全候选补位' }}</span>
            <span>策略：{{ analysis.policy_version }}</span>
            <span>记忆版本：{{ analysis.memory_revision }}</span>
          </div>
        </div>
      </VCardText>
    </VCard>
  </VDialog>
</template>

<style scoped>
.ar-analysis { max-height: min(760px, calc(100dvh - 32px)); border-radius: 10px; }
.ar-analysis__toolbar { flex: 0 0 auto; background: rgb(var(--v-theme-surface)); }
.ar-analysis__heading { min-width: 0; }
.ar-analysis__title { font-size: 15px; font-weight: 700; }
.ar-analysis__subtitle { max-width: 440px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: rgba(var(--v-theme-on-surface), .58); font-size: 11px; }
.ar-analysis__body { min-height: 340px; padding: 16px; }
.ar-analysis__state { min-height: 300px; display: grid; place-items: center; }
.ar-analysis__sections { display: grid; gap: 16px; }
.ar-analysis__summary, .ar-analysis__row { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: transparent; }
.ar-analysis__summary { padding: 12px; cursor: pointer; transition: background .12s, border-color .12s; }
.ar-analysis__summary:hover, .ar-analysis__row:hover { border-color: rgba(var(--v-theme-primary), .3); background: rgba(var(--v-theme-primary), .04); }
.ar-analysis__section-head, .ar-analysis__row { display: flex; align-items: flex-start; gap: 10px; }
.ar-analysis__section-head > div:first-child, .ar-analysis__row-main { min-width: 0; flex: 1 1 auto; }
.ar-analysis__section-title { margin-bottom: 6px; color: rgb(var(--v-theme-primary)); font-size: 13px; font-weight: 700; }
.ar-analysis__section-copy, .ar-analysis__row-main { overflow-wrap: anywhere; font-size: 13px; line-height: 1.55; }
.ar-analysis__list { display: grid; gap: 7px; }
.ar-analysis__row { align-items: center; padding: 8px 10px; cursor: pointer; transition: background .12s, border-color .12s; }
.ar-analysis__row-meta, .ar-analysis__empty, .ar-analysis__provenance { color: rgba(var(--v-theme-on-surface), .58); font-size: 11px; }
.ar-analysis__row-meta { margin-top: 2px; }
.ar-analysis__empty { padding: 7px 2px; }
.ar-analysis__provenance { display: flex; flex-wrap: wrap; gap: 6px 16px; padding-top: 10px; border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
@media (max-width: 760px) {
  .ar-analysis { width: 100%; height: 100dvh; max-height: none; border-radius: 0; }
  .ar-analysis__body { padding: 12px; }
  .ar-analysis__subtitle { max-width: min(54vw, 320px); }
}
</style>
