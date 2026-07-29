<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  state: { type: Object, required: true },
})
const emit = defineEmits(['update:modelValue', 'changed'])
const { smAndDown } = useDisplay()
const answers = reactive({})
const localError = ref('')
const activeView = ref('pending')
let visibilityTimer = null

const center = computed(() => activeView.value === 'resolved'
  ? props.state.processedCenter.value
  : props.state.pendingCenter.value)
const items = computed(() => center.value?.items || [])
const operation = computed(() => props.state.operationState(`pending:${activeView.value}`))
const typeLabels = { proposal: '偏好提案', question: '偏好问询', command: '执行确认' }
const statusLabels = {
  pending_confirmation: '待确认', pending: '待回答', confirmed: '已采纳', rejected: '已拒绝',
  answered: '已回答', dismissed: '已关闭', expired: '已过期', failed: '执行失败', superseded: '已替代',
}

function statusText(item) {
  if (item.item_type === 'command' && item.status === 'confirmed') return '已执行'
  if (item.item_type === 'command' && item.status === 'rejected') return '未执行'
  if (item.item_type === 'proposal' && item.status === 'confirmed') return '已采纳'
  if (item.item_type === 'proposal' && item.status === 'rejected') return '未采纳'
  return statusLabels[item.status] || item.status
}

function close() {
  emit('update:modelValue', false)
}

function answerState(item) {
  if (!answers[item.item_id]) {
    answers[item.item_id] = {
      optionId: item.selected_option_id || '',
      customAnswer: item.selected_option_id ? '' : (item.answer_text || ''),
    }
  }
  return answers[item.item_id]
}

function itemOperation(item) {
  return props.state.operationState(`pending:${item.item_type}:${item.item_id}`)
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString()
}

async function load() {
  localError.value = ''
  try { await props.state.loadPendingCenter(activeView.value) }
  catch (error) { localError.value = error?.message || '待处理项目读取失败' }
}

async function switchView(value) {
  activeView.value = value
  await load()
}

async function respond(item, action, options = {}) {
  localError.value = ''
  try {
    await props.state.respondPending(item, action, options)
    emit('changed')
  } catch (error) {
    localError.value = error?.message || '待处理操作失败'
  }
}

function answerQuestion(item) {
  const answer = answerState(item)
  const customAnswer = answer.customAnswer.trim()
  if (!answer.optionId && !customAnswer) {
    localError.value = '请选择一个答案或填写自定义回答'
    return
  }
  respond(item, 'answer', { optionId: customAnswer ? '' : answer.optionId, customAnswer })
}

function reopenQuestion(item) {
  respond(item, 'reopen')
}

function stopVisibilityHeartbeat() {
  if (visibilityTimer) window.clearInterval(visibilityTimer)
  visibilityTimer = null
}

watch(() => props.modelValue, open => {
  stopVisibilityHeartbeat()
  if (!open) return
  load()
  visibilityTimer = window.setInterval(() => {
    if (activeView.value === 'pending') load()
  }, 15000)
}, { immediate: true })
onBeforeUnmount(stopVisibilityHeartbeat)
</script>

<template>
  <VDialog
    :model-value="modelValue"
    :fullscreen="smAndDown"
    max-width="820"
    scrollable
    @update:model-value="value => emit('update:modelValue', value)"
  >
    <VCard class="ar-pending">
      <VToolbar density="compact" class="ar-pending__toolbar">
        <VIcon icon="mdi-inbox-outline" color="primary" class="ms-4 me-3" />
        <div>
          <div class="ar-pending__title">待办中心</div>
          <div class="ar-pending__subtitle">{{ activeView === 'pending' ? `${items.length} 项待办` : `${items.length} 条记录` }}</div>
        </div>
        <VSpacer />
        <VBtn icon="mdi-refresh" variant="text" aria-label="刷新待处理项目" :loading="operation.loading" @click="load" />
        <VBtn icon="mdi-close" variant="text" aria-label="关闭待处理窗口" @click="close" />
      </VToolbar>
      <VDivider />

      <VTabs :model-value="activeView" density="compact" color="primary" grow @update:model-value="switchView">
        <VTab value="pending">待办事项</VTab>
        <VTab value="resolved">处理记录</VTab>
      </VTabs>
      <VDivider />

      <VCardText class="ar-pending__body">
        <VAlert v-if="localError || operation.error" type="error" variant="tonal" density="compact" class="mb-3">
          {{ localError || operation.error?.message }}
        </VAlert>
        <div v-if="operation.loading && !items.length" class="ar-pending__state"><VProgressCircular indeterminate color="primary" /></div>
        <VEmptyState v-else-if="!items.length" icon="mdi-check-all" :title="activeView === 'pending' ? '当前没有待办事项' : '当前没有处理记录'" />
        <div v-else class="ar-pending__list">
          <section v-for="item in items" :key="`${item.item_type}:${item.item_id}`" class="ar-pending__item">
            <div class="ar-pending__item-head">
              <VChip size="x-small" color="primary" variant="tonal">{{ typeLabels[item.item_type] || '待处理' }}</VChip>
              <span>{{ formatTime(item.created_at) }}</span>
              <VChip v-if="activeView === 'resolved'" size="x-small" variant="outlined">{{ statusText(item) }}</VChip>
              <VSpacer />
            </div>
            <div class="ar-pending__item-title">{{ item.title }}</div>
            <div class="ar-pending__summary">{{ item.summary }}</div>
            <ul v-if="item.detail_lines?.length" class="ar-pending__details">
              <li v-for="line in item.detail_lines" :key="line">{{ line }}</li>
            </ul>

            <VAlert v-if="activeView === 'resolved' && item.result_message" density="compact" variant="tonal" type="info" class="mt-2">
              {{ item.result_message }}
            </VAlert>
            <div v-if="item.item_type === 'question' && (activeView === 'pending' || item.status === 'answered')" class="ar-pending__answer">
              <VRadioGroup v-model="answerState(item).optionId" density="compact" hide-details @update:model-value="answerState(item).customAnswer = ''">
                <VRadio v-for="option in item.options || []" :key="option.option_id" :label="option.label" :value="option.option_id" />
              </VRadioGroup>
              <VTextField
                v-if="item.allow_custom_answer"
                v-model="answerState(item).customAnswer"
                label="自定义回答"
                density="compact"
                variant="outlined"
                hide-details
                maxlength="1000"
                class="mt-2"
                @update:model-value="value => { if (value) answerState(item).optionId = '' }"
              />
            </div>

            <div class="ar-pending__actions">
              <VBtn
                v-if="activeView === 'pending' && item.item_type === 'question'"
                size="small"
                variant="text"
                @click="respond(item, 'close')"
              >关闭问询</VBtn>
              <VBtn
                v-else-if="activeView === 'pending'"
                size="small"
                variant="text"
                color="error"
                @click="respond(item, 'reject')"
              >{{ item.item_type === 'proposal' ? '拒绝采纳' : '拒绝执行' }}</VBtn>
              <VBtn
                v-if="activeView === 'pending' && item.item_type === 'question'"
                size="small"
                color="primary"
                variant="tonal"
                :loading="itemOperation(item).loading"
                @click="answerQuestion(item)"
              >提交回答</VBtn>
              <VBtn
                v-else-if="activeView === 'pending'"
                size="small"
                color="primary"
                variant="tonal"
                :loading="itemOperation(item).loading"
                :disabled="item.requires_superuser"
                @click="respond(item, 'confirm')"
              >{{ item.item_type === 'proposal' ? '确认采纳' : '确认执行' }}</VBtn>
              <template v-else-if="activeView === 'resolved' && item.item_type === 'question'">
                <VBtn
                  size="small"
                  variant="text"
                  :loading="itemOperation(item).loading"
                  @click="reopenQuestion(item)"
                >{{ item.status === 'answered' ? '撤销回答' : '重新打开' }}</VBtn>
                <VBtn
                  v-if="item.status === 'answered'"
                  size="small"
                  color="primary"
                  variant="tonal"
                  :loading="itemOperation(item).loading"
                  @click="answerQuestion(item)"
                >更新回答</VBtn>
              </template>
            </div>
          </section>
        </div>
      </VCardText>
    </VCard>
  </VDialog>
</template>

<style scoped>
.ar-pending { height: min(760px, calc(100dvh - 32px)); display: flex; flex-direction: column; border-radius: 10px; }
.ar-pending__toolbar { flex: 0 0 auto; background: rgb(var(--v-theme-surface)); }
.ar-pending__title { font-size: 15px; font-weight: 700; }
.ar-pending__subtitle { color: rgba(var(--v-theme-on-surface), .58); font-size: 11px; }
.ar-pending__body { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 16px; }
.ar-pending__state { min-height: 300px; display: grid; place-items: center; }
.ar-pending__list { display: grid; gap: 10px; }
.ar-pending__item { padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; background: transparent; }
.ar-pending__item-head { display: flex; align-items: center; gap: 8px; color: rgba(var(--v-theme-on-surface), .5); font-size: 10px; }
.ar-pending__item-title { margin-top: 9px; font-size: 14px; font-weight: 700; }
.ar-pending__summary { margin-top: 4px; overflow-wrap: anywhere; font-size: 13px; line-height: 1.55; }
.ar-pending__details { margin: 7px 0 0; padding-left: 20px; color: rgba(var(--v-theme-on-surface), .65); font-size: 12px; line-height: 1.55; }
.ar-pending__answer { margin-top: 10px; padding: 8px 10px; border-left: 3px solid rgba(var(--v-theme-primary), .38); background: rgba(var(--v-theme-primary), .035); }
.ar-pending__actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 4px; margin-top: 10px; }
@media (max-width: 760px) {
  .ar-pending { width: 100%; height: 100dvh; max-height: none; border-radius: 0; }
  .ar-pending__body { padding: 12px; }
}
</style>
