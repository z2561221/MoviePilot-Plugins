<script setup>
import { computed, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  state: { type: Object, required: true },
  item: { type: Object, default: null },
  judgment: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'submitted'])
const { smAndDown } = useDisplay()
const comment = ref('')
const localError = ref('')

const candidateId = computed(() => String(props.item?.candidate_id || ''))
const operation = computed(() => props.state.operationState(`analysis-comment:${candidateId.value}`))
const canSubmit = computed(() => comment.value.trim().length >= 2 && !operation.value.loading)

watch(
  () => [props.modelValue, props.judgment?.label, props.item?.candidate_id],
  ([open]) => {
    if (!open) return
    comment.value = ''
    localError.value = ''
    props.state.clearOperationError(`analysis-comment:${candidateId.value}`)
  },
)

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  const value = comment.value.trim()
  if (value.length < 2) {
    localError.value = '请写下需要纠正的具体内容'
    return
  }
  const label = String(props.judgment?.label || 'Agent判断')
  try {
    const result = await props.state.commentOnAnalysis(candidateId.value, `【${label}】${value}`)
    emit('submitted', result)
    close()
  } catch (error) {
    localError.value = error?.message || '评论提交失败'
  }
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    :fullscreen="smAndDown"
    max-width="620"
    @update:model-value="value => emit('update:modelValue', value)"
  >
    <VCard class="ar-comment">
      <VToolbar density="compact" class="ar-comment__toolbar">
        <VIcon icon="mdi-comment-edit-outline" color="primary" class="ms-4 me-3" />
        <div class="ar-comment__heading">
          <div class="ar-comment__title">评论 Agent 判断</div>
          <div class="ar-comment__subtitle">{{ item?.title || '当前推荐' }}</div>
        </div>
        <VSpacer />
        <VBtn icon="mdi-close" variant="text" aria-label="关闭评论窗口" @click="close" />
      </VToolbar>
      <VDivider />
      <VCardText class="ar-comment__body">
        <div class="ar-comment__label">{{ judgment?.label || 'Agent判断' }}</div>
        <div class="ar-comment__judgment">{{ judgment?.content || '当前判断内容未返回' }}</div>
        <VTextarea
          v-model="comment"
          label="你的评论"
          placeholder="指出哪里不准确，并写下你真实的偏好或原因"
          density="compact"
          variant="outlined"
          rows="4"
          auto-grow
          maxlength="1000"
          counter
          class="mt-4"
          @keydown.ctrl.enter.prevent="submit"
        />
        <VAlert v-if="localError || operation.error" type="error" variant="tonal" density="compact" class="mt-2">
          {{ localError || operation.error?.message }}
        </VAlert>
      </VCardText>
      <VDivider />
      <VCardActions class="ar-comment__actions">
        <VSpacer />
        <VBtn variant="text" @click="close">取消</VBtn>
        <VBtn color="primary" variant="flat" prepend-icon="mdi-send-outline" :loading="operation.loading" :disabled="!canSubmit" @click="submit">提交评论</VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>

<style scoped>
.ar-comment { border-radius: 10px; }
.ar-comment__toolbar { background: rgb(var(--v-theme-surface)); }
.ar-comment__heading { min-width: 0; }
.ar-comment__title { font-size: 15px; font-weight: 700; }
.ar-comment__subtitle { max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: rgba(var(--v-theme-on-surface), .58); font-size: 11px; }
.ar-comment__body { padding: 18px; }
.ar-comment__label { color: rgb(var(--v-theme-primary)); font-size: 12px; font-weight: 700; }
.ar-comment__judgment { margin-top: 5px; padding: 10px 12px; border-left: 3px solid rgba(var(--v-theme-primary), .48); background: rgba(var(--v-theme-primary), .045); overflow-wrap: anywhere; font-size: 13px; line-height: 1.55; }
.ar-comment__actions { padding: 10px 16px; }
@media (max-width: 760px) {
  .ar-comment { width: 100%; height: 100dvh; display: flex; flex-direction: column; border-radius: 0; }
  .ar-comment__body { flex: 1 1 auto; overflow-y: auto; padding: 14px; }
  .ar-comment__subtitle { max-width: min(54vw, 300px); }
}
</style>
