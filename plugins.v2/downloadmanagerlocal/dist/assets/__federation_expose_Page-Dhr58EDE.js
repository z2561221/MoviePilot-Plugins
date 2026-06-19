import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, g as getPluginApi, p as postPluginApi } from './_plugin-vue_export-helper-DyVawm7J.js';

const { h, ref, onMounted, computed, resolveComponent } = await importShared('vue');

const pageSize = 15;

const _sfc_main = {
  __name: 'Page',
  props: { api: { type: [Object, Function], default: null } },
  emits: ['close', 'switch'],
  setup(props, { emit }) {
    const records = ref([]);
    const total = ref(0);
    const page = ref(1);
    const activeTab = ref('history');
    const loading = ref(true);
    const retrying = ref(false);
    const retryingHash = ref('');
    const diagnostics = ref(null);
    const diagnosticsLoading = ref(false);
    const diagnosticsError = ref('');
    const error = ref('');
    const actionMsg = ref('');
    const actionOk = ref(false);

    const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize)));

    async function loadHistory() {
      loading.value = true;
      error.value = '';
      try {
        const resp = await getPluginApi(props.api, `rename_history?page=${page.value}&page_size=${pageSize}`);
        records.value = Array.isArray(resp?.items) ? resp.items : [];
        total.value = resp?.total || 0;
      } catch (e) {
        error.value = e?.message || '加载失败';
      } finally {
        loading.value = false;
      }
    }

    async function loadDiagnostics() {
      activeTab.value = 'diagnostics';
      diagnosticsLoading.value = true;
      diagnosticsError.value = '';
      try {
        const resp = await getPluginApi(props.api, 'diagnostics');
        if (resp?.code && resp.code !== 0) {
          diagnosticsError.value = resp?.msg || '诊断失败';
          return;
        }
        diagnostics.value = resp;
      } catch (e) {
        diagnosticsError.value = e?.message || '诊断失败';
      } finally {
        diagnosticsLoading.value = false;
      }
    }

    function checkColor(status) {
      if (status === 'ok') return 'success';
      if (status === 'warn') return 'warning';
      return 'default';
    }

    async function doRecovery(hash) {
      actionMsg.value = '';
      actionOk.value = false;
      try {
        const resp = await postPluginApi(props.api, 'recovery_torrent', { hash });
        actionMsg.value = resp?.msg || (resp?.code === 0 ? '恢复成功' : '恢复失败');
        actionOk.value = resp?.code === 0;
        if (resp?.code === 0) await loadHistory();
      } catch (e) {
        actionMsg.value = e?.message || '恢复失败';
      }
    }

    async function doDelete(hash) {
      actionMsg.value = '';
      actionOk.value = false;
      try {
        const resp = await postPluginApi(props.api, 'delete_rename_history', { hash });
        actionOk.value = resp?.code === 0;
        actionMsg.value = resp?.msg || '已删除';
        if (resp?.code === 0) await loadHistory();
      } catch (e) {
        actionMsg.value = e?.message || '删除失败';
      }
    }

    async function doRetryRenames() {
      actionMsg.value = '';
      actionOk.value = false;
      retrying.value = true;
      try {
        const resp = await postPluginApi(props.api, 'retry_renames', {});
        actionMsg.value = resp?.msg || (resp?.code === 0 ? '补刀完成' : '补刀失败');
        actionOk.value = resp?.code === 0;
        if (resp?.code === 0) await loadHistory();
      } catch (e) {
        actionOk.value = false;
        actionMsg.value = e?.message || '补刀失败';
      } finally {
        retrying.value = false;
      }
    }

    async function doRetryRename(hash) {
      actionMsg.value = '';
      actionOk.value = false;
      retryingHash.value = hash;
      try {
        const resp = await postPluginApi(props.api, 'retry_rename', { hash });
        actionMsg.value = resp?.msg || (resp?.code === 0 ? '补刀完成' : '补刀失败');
        actionOk.value = resp?.code === 0;
        if (resp?.code === 0) await loadHistory();
      } catch (e) {
        actionOk.value = false;
        actionMsg.value = e?.message || '补刀失败';
      } finally {
        retryingHash.value = '';
      }
    }

    function prevPage() {
      if (page.value > 1) {
        page.value -= 1;
        loadHistory();
      }
    }

    function nextPage() {
      if (page.value < totalPages.value) {
        page.value += 1;
        loadHistory();
      }
    }

    onMounted(loadHistory);

    return () => {
      const VIcon = resolveComponent('VIcon');
      const VSpacer = resolveComponent('VSpacer');
      const VBtn = resolveComponent('VBtn');
      const VToolbar = resolveComponent('VToolbar');
      const VDivider = resolveComponent('VDivider');
      const VAlert = resolveComponent('VAlert');
      const VProgressCircular = resolveComponent('VProgressCircular');
      const VChip = resolveComponent('VChip');
      const VTable = resolveComponent('VTable');

      const chip = (text, color = 'default') => h(VChip, {
        size: 'x-small',
        color,
        variant: 'tonal',
      }, () => text || '');

      const stat = (title, main, extra) => h('div', { class: 'dm-stat' }, [
        h('div', { class: 'text-caption text-medium-emphasis' }, title),
        h('div', { class: 'text-subtitle-2' }, main || ''),
        extra || null,
      ]);

      const toolbar = h(VToolbar, {
        density: 'comfortable',
        class: 'dm-toolbar',
      }, () => [
        h(VIcon, { icon: 'mdi-rename-box', class: 'ms-3 me-2', color: 'primary' }),
        h('div', { class: 'text-h6' }, '下载管理'),
        h(VSpacer),
        h(VBtn, {
          value: 'history',
          variant: activeTab.value === 'history' ? 'tonal' : 'text',
          size: 'small',
          class: 'text-none me-1',
          onClick: () => { activeTab.value = 'history'; },
        }, () => '重命名历史'),
        h(VBtn, {
          value: 'diagnostics',
          variant: activeTab.value === 'diagnostics' ? 'tonal' : 'text',
          size: 'small',
          class: 'text-none me-2',
          onClick: loadDiagnostics,
        }, () => '诊断'),
        activeTab.value === 'history'
          ? h(VBtn, {
              variant: 'tonal',
              size: 'small',
              'prepend-icon': 'mdi-auto-fix',
              class: 'text-none me-2',
              onClick: doRetryRenames,
              loading: retrying.value,
            }, () => '补刀')
          : h(VBtn, {
              variant: 'text',
              size: 'small',
              'prepend-icon': 'mdi-refresh',
              class: 'text-none me-2',
              onClick: loadDiagnostics,
              loading: diagnosticsLoading.value,
            }, () => '刷新诊断'),
        activeTab.value === 'history'
          ? h(VBtn, {
              variant: 'text',
              size: 'small',
              'prepend-icon': 'mdi-refresh',
              class: 'text-none me-2',
              onClick: loadHistory,
              loading: loading.value,
            }, () => '刷新')
          : null,
        h(VBtn, {
          variant: 'text',
          'prepend-icon': 'mdi-cog-outline',
          class: 'text-none',
          onClick: () => emit('switch'),
        }, () => '设置'),
        h(VBtn, {
          icon: 'mdi-close',
          variant: 'text',
          onClick: () => emit('close'),
        }),
      ]);

      const historyBody = h('div', { class: 'pa-3' }, [
        actionMsg.value ? h(VAlert, {
          type: actionOk.value ? 'success' : 'error',
          variant: 'tonal',
          class: 'mb-3',
          closable: true,
          density: 'compact',
        }, () => actionMsg.value) : null,
        error.value ? h(VAlert, {
          type: 'error',
          variant: 'tonal',
          class: 'mb-3',
          density: 'compact',
        }, () => error.value) : null,
        loading.value
          ? h(VProgressCircular, { indeterminate: true, color: 'primary', class: 'd-block mx-auto my-8' })
          : records.value.length === 0
            ? h('div', { class: 'text-center text-medium-emphasis py-8' }, [
                h(VIcon, { icon: 'mdi-history', size: '48', color: 'grey-lighten-1', class: 'mb-2' }),
                h('div', '暂无重命名记录'),
              ])
            : h(VTable, { density: 'compact', class: 'dm-table' }, () => [
                h('thead', [
                  h('tr', [
                    h('th', { class: 'text-caption' }, '时间'),
                    h('th', { class: 'text-caption' }, '原始名称'),
                    h('th', { class: 'text-caption' }, '重命名后'),
                    h('th', { class: 'text-caption' }, '状态'),
                    h('th', { class: 'text-caption' }, '操作'),
                  ]),
                ]),
                h('tbody', records.value.map((r) => h('tr', { key: r.hash }, [
                  h('td', { class: 'text-caption text-no-wrap' }, r.time || ''),
                  h('td', {
                    class: 'text-caption',
                    style: 'max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap',
                    title: r.original_name,
                  }, r.original_name || ''),
                  h('td', {
                    class: 'text-caption',
                    style: 'max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap',
                    title: r.after_name,
                  }, r.after_name || ''),
                  h('td', [
                    chip(r.success ? '成功' : (r.reason || '失败'), r.success ? 'success' : 'error'),
                  ]),
                  h('td', [
                    h('div', { class: 'd-flex ga-1' }, [
                      h(VBtn, {
                        size: 'x-small',
                        variant: 'tonal',
                        color: 'primary',
                        onClick: () => doRetryRename(r.hash),
                        loading: retryingHash.value === r.hash,
                      }, () => '补刀'),
                      r.success ? h(VBtn, {
                        size: 'x-small',
                        variant: 'tonal',
                        color: 'warning',
                        onClick: () => doRecovery(r.hash),
                      }, () => '恢复') : null,
                      h(VBtn, {
                        size: 'x-small',
                        variant: 'text',
                        color: 'error',
                        onClick: () => doDelete(r.hash),
                      }, () => '删除'),
                    ]),
                  ]),
                ]))),
              ]),
        total.value > pageSize ? h('div', { class: 'd-flex align-center justify-center pa-3' }, [
          h(VBtn, {
            size: 'x-small',
            variant: 'tonal',
            icon: 'mdi-chevron-left',
            disabled: page.value <= 1,
            onClick: prevPage,
            class: 'mr-2',
          }),
          h('span', { class: 'text-caption mx-1' }, `${page.value} / ${totalPages.value}（共 ${total.value} 条）`),
          h(VBtn, {
            size: 'x-small',
            variant: 'tonal',
            icon: 'mdi-chevron-right',
            disabled: page.value >= totalPages.value,
            onClick: nextPage,
            class: 'ml-2',
          }),
        ]) : null,
      ]);

      const diagnosticsBody = h('div', { class: 'pa-3' }, [
        diagnosticsError.value ? h(VAlert, {
          type: 'error',
          variant: 'tonal',
          class: 'mb-3',
          density: 'compact',
        }, () => diagnosticsError.value) : null,
        diagnosticsLoading.value
          ? h(VProgressCircular, { indeterminate: true, color: 'primary', class: 'd-block mx-auto my-8' })
          : diagnostics.value
            ? h('div', { class: 'dm-diagnostics' }, [
                h('div', { class: 'dm-stat-grid mb-3' }, [
                  stat('版本', diagnostics.value?.plugin?.version),
                  stat('源下载器', diagnostics.value?.downloaders?.from?.name || '未配置',
                    chip(diagnostics.value?.downloaders?.from?.message, diagnostics.value?.downloaders?.from?.available ? 'success' : 'warning')),
                  stat('目标下载器', diagnostics.value?.downloaders?.to?.name || '未配置',
                    chip(diagnostics.value?.downloaders?.to?.message, diagnostics.value?.downloaders?.to?.available ? 'success' : 'warning')),
                  stat('重命名历史', `${diagnostics.value?.rename_history?.total || 0} 条`,
                    h('div', { class: 'text-caption' }, `失败 ${diagnostics.value?.rename_history?.failed || 0} · 脏名 ${diagnostics.value?.rename_history?.dirty || 0}`)),
                ]),
                h('div', { class: 'dm-checks mb-3' }, (diagnostics.value?.checks || []).map((item) => h('div', {
                  class: 'dm-check-row',
                  key: item.label,
                }, [
                  h('div', { class: 'text-body-2' }, item.label),
                  h('div', { class: 'd-flex align-center ga-2' }, [
                    h('span', { class: 'text-caption text-medium-emphasis' }, item.detail),
                    chip(item.status, checkColor(item.status)),
                  ]),
                ]))),
                h('div', [
                  h('div', { class: 'text-subtitle-2 mb-2' }, '最近失败'),
                  !(diagnostics.value?.rename_history?.recent_failures || []).length
                    ? h('div', { class: 'text-caption text-medium-emphasis py-2' }, '暂无失败记录')
                    : h(VTable, { density: 'compact', class: 'dm-table' }, () => [
                        h('thead', [
                          h('tr', [
                            h('th', { class: 'text-caption' }, '时间'),
                            h('th', { class: 'text-caption' }, '名称'),
                            h('th', { class: 'text-caption' }, '原因'),
                          ]),
                        ]),
                        h('tbody', diagnostics.value.rename_history.recent_failures.map((item) => h('tr', { key: item.hash }, [
                          h('td', { class: 'text-caption text-no-wrap' }, item.time || ''),
                          h('td', {
                            class: 'text-caption',
                            style: 'max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap',
                            title: item.name,
                          }, item.name || ''),
                          h('td', { class: 'text-caption' }, item.reason || ''),
                        ]))),
                      ]),
                ]),
              ])
            : h('div', { class: 'text-center text-medium-emphasis py-8' }, [
                h(VIcon, { icon: 'mdi-stethoscope', size: '48', color: 'grey-lighten-1', class: 'mb-2' }),
                h('div', '点击刷新诊断'),
              ]),
      ]);

      return h('div', { class: 'dm-page' }, [
        toolbar,
        h(VDivider),
        activeTab.value === 'history' ? historyBody : diagnosticsBody,
      ]);
    };
  },
};

const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId', 'data-v-42e2ccd0']]);

export { Page as default };
