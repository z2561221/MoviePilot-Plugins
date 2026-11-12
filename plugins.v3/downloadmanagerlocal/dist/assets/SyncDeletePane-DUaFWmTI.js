import { importShared } from './__federation_fn_import-JrT3xvdd.js';

function isStandardEnvelope(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) return false
  const keys = Object.keys(response).sort();
  return keys.length === 3
    && keys[0] === 'data'
    && keys[1] === 'message'
    && keys[2] === 'success'
    && typeof response.success === 'boolean'
    && typeof response.message === 'string'
}

function pluginPath(pluginId, path = '') {
  const normalizedId = String(pluginId || '').trim();
  if (!normalizedId) throw new Error('缺少 MoviePilot 注入的 pluginId')
  const suffix = String(path || '').replace(/^\/+/, '');
  return suffix ? `plugin/${normalizedId}/${suffix}` : `plugin/${normalizedId}`
}

function unwrapResponse(response) {
  if (!isStandardEnvelope(response)) return response
  if (!response.success) {
    const error = new Error(response.message || '请求失败');
    error.name = 'PluginApiError';
    error.payload = response;
    throw error
  }
  return response.data
}
function isApiRequestCancellation(reason) {
  if (!reason || typeof reason !== 'object') return false
  return Boolean(reason.__CANCEL__) || reason.code === 'ERR_CANCELED'
    || reason.name === 'AbortError' || reason.name === 'CanceledError'
}
async function postPluginApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const params = new URLSearchParams();
  Object.entries(payload || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, value);
  });
  const query = params.toString();
  const url = `${pluginPath(pluginId, path)}${query ? `?${query}` : ''}`;
  const response = await api.post(url, payload, options);
  return unwrapResponse(response)
}
async function postPluginJsonApi(api, pluginId, path, payload = {}, options = {}) {
  if (!api?.post) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.post(pluginPath(pluginId, path), payload, options);
  return unwrapResponse(response)
}
async function getPluginApi(api, pluginId, path, options = {}) {
  if (!api?.get) throw new Error('MoviePilot 插件 API 未就绪')
  const response = await api.get(pluginPath(pluginId, path), options);
  return unwrapResponse(response)
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,createVNode:_createVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,withModifiers:_withModifiers} = await importShared('vue');


const _hoisted_1 = { class: "dm-sync" };
const _hoisted_2 = { class: "dm-sync-heading" };
const _hoisted_3 = { class: "dm-sync-switches" };
const _hoisted_4 = { class: "dm-sync-group-head" };
const _hoisted_5 = { class: "dm-sync-group-title" };
const _hoisted_6 = { class: "dm-sync-count" };
const _hoisted_7 = {
  key: 0,
  class: "dm-sync-empty"
};
const _hoisted_8 = {
  key: 1,
  class: "dm-sync-mapping-list"
};
const _hoisted_9 = ["open"];
const _hoisted_10 = ["onClick"];
const _hoisted_11 = { class: "dm-sync-index" };
const _hoisted_12 = { class: "dm-sync-mapping-label" };
const _hoisted_13 = ["title"];
const _hoisted_14 = ["title"];
const _hoisted_15 = {
  key: 0,
  class: "dm-sync-mapping-editor"
};
const _hoisted_16 = { class: "dm-sync-editor-footer" };
const _hoisted_17 = { class: "my-4" };
const _hoisted_18 = { key: 0 };
const _hoisted_19 = {
  key: 1,
  class: "text-warning"
};
const _hoisted_20 = { class: "dm-sync-heading mb-3" };
const _hoisted_21 = { class: "text-caption text-medium-emphasis" };
const _hoisted_22 = {
  key: 1,
  class: "text-medium-emphasis pa-6 text-center"
};
const _hoisted_23 = { class: "dm-sync-heading" };
const _hoisted_24 = { class: "text-caption text-medium-emphasis mt-1" };
const _hoisted_25 = {
  key: 0,
  class: "text-warning mt-2"
};
const _hoisted_26 = { class: "mt-3" };
const _hoisted_27 = { class: "text-caption mt-2" };

const {computed,onBeforeUnmount,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'SyncDeletePane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, required: true },
  form: { type: Object, default: null },
  mode: { type: String, default: 'history' },
  canManage: { type: Boolean, default: false },
},
  setup(__props, { expose: __expose }) {

const props = __props;
const servers = ref([]);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const enabled = ref(false);
const loading = ref(false);
const error = ref('');
const notice = ref('');
const retryId = ref('');
const expandedMappings = ref({});
const mappingRows = value => String(value || '').split('\n').filter(line => line.trim()).map(line => line.split('#'));
const cloudMappings = computed(() => mappingRows(props.form?.sync_delete_cloud_paths));
const localMappings = computed(() => mappingRows(props.form?.sync_delete_local_paths));
const mappingGroups = computed(() => [
  { field: 'sync_delete_local_paths', title: '本地媒体库', icon: 'mdi-folder-outline', columns: 2, rows: localMappings.value,
    inputs: [{ column: 0, label: 'Emby 媒体目录' }, { column: 1, label: 'MP 本地媒体目录' }] },
  { field: 'sync_delete_cloud_paths', title: 'STRM 媒体库', icon: 'mdi-cloud-outline', columns: 4, rows: cloudMappings.value,
    inputs: [{ column: 0, label: 'Emby STRM 目录' }, { column: 1, label: 'MP STRM 目录' },
      { column: 3, label: '本地整理目录（可选）' }, { column: 2, label: '网盘目录' }] },
]);
const sourceRoots = computed(() => String(props.form?.sync_delete_source_paths || '').split('\n').map(line => line.trim()).filter(Boolean));
const mappingTitle = row => String(row[0] || '').trim().split(/[\\/]/).filter(Boolean).at(-1) || '新映射';
function toggleMapping(field, index) {
  expandedMappings.value = { ...expandedMappings.value, [field]: expandedMappings.value[field] === index ? -1 : index };
}
function editMapping(field, index, column, value) {
  const rows = mappingRows(props.form[field]);
  rows[index] ||= Array(field === 'sync_delete_cloud_paths' ? 4 : 2).fill('');
  rows[index][column] = String(value || '').replace(/[\r\n]/g, '');
  props.form[field] = rows.map(row => row.join('#')).join('\n');
}
function addMapping(field, columns) {
  const rows = mappingRows(props.form[field]);
  rows.push(Array(columns).fill(''));
  props.form[field] = rows.map(row => row.join('#')).join('\n');
  expandedMappings.value = { ...expandedMappings.value, [field]: rows.length - 1 };
}
function removeMapping(field, index) {
  const rows = mappingRows(props.form[field]);
  props.form[field] = rows.filter((_, i) => i !== index).map(row => row.join('#')).join('\n');
  const opened = expandedMappings.value[field] ?? -1;
  expandedMappings.value = { ...expandedMappings.value, [field]: opened === index ? -1 : opened > index ? opened - 1 : opened };
}
let revision = 0;
let loadRevision = 0;
let retryRevision = 0;
let disposed = false;
const pages = computed(() => Math.max(1, Math.ceil(total.value / 15)));
const labels = { queued: '等待执行', running: '处理中', failed: '待处理', completed: '完成', pending: '待执行', deleted: '已删除', absent: '已不存在', removed: '已移除', paused: '保留并暂停' };
const label = state => labels[state] || state;
const color = state => state === 'completed' ? 'success' : state === 'failed' ? 'warning' : 'info';
const dateText = stamp => stamp ? new Date(stamp * 1000).toLocaleString() : '—';
const current = (ticket, id) => !disposed && revision === ticket && props.pluginId === id;

async function load() {
  const ticket = revision;
  const request = ++loadRevision;
  const id = props.pluginId;
  const owns = () => current(ticket, id) && request === loadRevision;
  loading.value = true;
  error.value = '';
  try {
    if (props.mode === 'config') {
      const result = await getPluginApi(props.api, id, 'sync_delete/options', { feedback: 'silent' });
      if (owns()) servers.value = result?.servers || [];
    } else {
      const result = await getPluginApi(props.api, id, `sync_delete/history?page=${page.value}&page_size=15`, { feedback: 'silent' });
      if (owns()) {
        rows.value = result?.items || [];
        total.value = result?.total || 0;
        enabled.value = Boolean(result?.enabled);
      }
    }
  } catch (cause) {
    if (owns() && !isApiRequestCancellation(cause)) error.value = cause?.message || '读取失败，请重试';
  } finally {
    if (owns()) loading.value = false;
  }
}

async function retry(job) {
  if (!props.canManage || retryId.value) return
  const ticket = revision;
  const request = ++retryRevision;
  const id = props.pluginId;
  const owns = () => current(ticket, id) && request === retryRevision;
  retryId.value = job.id;
  error.value = '';
  notice.value = '';
  try {
    const result = await postPluginJsonApi(props.api, id, 'sync_delete/retry', { job_id: job.id }, { feedback: 'silent' });
    if (owns() && result?.accepted) {
      notice.value = '已加入执行队列，请刷新查看实际结果。';
      await load();
    }
  } catch (cause) {
    if (owns() && !isApiRequestCancellation(cause)) error.value = cause?.message || '重试未受理';
  } finally {
    if (owns()) retryId.value = '';
  }
}

watch(() => [props.pluginId, props.mode, props.api], () => {
  revision++;
  page.value = 1;
  rows.value = [];
  servers.value = [];
  total.value = 0;
  enabled.value = false;
  expandedMappings.value = {};
  notice.value = '';
  retryId.value = '';
  load();
}, { immediate: true, flush: 'sync' });
onBeforeUnmount(() => { disposed = true; revision++; });
__expose({ refresh: load });

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VPagination = _resolveComponent("VPagination");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(error.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    (notice.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "info",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(notice.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    (__props.mode === 'config' && __props.form)
      ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
          _createElementVNode("div", _hoisted_2, [
            _cache[10] || (_cache[10] = _createElementVNode("div", null, [
              _createElementVNode("strong", null, "同步删除"),
              _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "在 Emby 删除本地媒体或 STRM 后，清理关联文件、种子和整理记录。")
            ], -1)),
            _createVNode(_component_VSwitch, {
              modelValue: __props.form.sync_delete_enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((__props.form.sync_delete_enabled) = $event)),
              color: "success",
              inset: "",
              "hide-details": "",
              label: "启用"
            }, null, 8, ["modelValue"])
          ]),
          _createVNode(_component_VSelect, {
            modelValue: __props.form.sync_delete_servers,
            "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((__props.form.sync_delete_servers) = $event)),
            items: servers.value,
            multiple: "",
            chips: "",
            label: "Emby 服务器",
            density: "compact",
            variant: "outlined",
            "hide-details": "",
            class: "my-4"
          }, null, 8, ["modelValue", "items"]),
          _createVNode(_component_VAlert, {
            type: "info",
            variant: "tonal",
            density: "compact",
            class: "mb-4"
          }, {
            default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
              _createTextVNode("使用现有神医深度删除通知。合集还有其它集数时，种子暂停保留。", -1)
            ]))]),
            _: 1
          }),
          _createElementVNode("div", _hoisted_3, [
            _createVNode(_component_VSwitch, {
              modelValue: __props.form.sync_delete_cloud,
              "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((__props.form.sync_delete_cloud) = $event)),
              color: "success",
              inset: "",
              "hide-details": "",
              label: "删除网盘文件"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_VSwitch, {
              modelValue: __props.form.sync_delete_source,
              "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((__props.form.sync_delete_source) = $event)),
              color: "success",
              inset: "",
              "hide-details": "",
              label: "删除下载源文件"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_VSwitch, {
              modelValue: __props.form.sync_delete_torrents,
              "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((__props.form.sync_delete_torrents) = $event)),
              color: "success",
              inset: "",
              "hide-details": "",
              label: "移除源种、转种和辅种"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_VSwitch, {
              modelValue: __props.form.sync_delete_records,
              "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((__props.form.sync_delete_records) = $event)),
              color: "success",
              inset: "",
              "hide-details": "",
              label: "清理整理记录"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_VSwitch, {
              modelValue: __props.form.sync_delete_notify,
              "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((__props.form.sync_delete_notify) = $event)),
              color: "success",
              inset: "",
              "hide-details": "",
              label: "发送结果通知"
            }, null, 8, ["modelValue"])
          ]),
          _cache[16] || (_cache[16] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mt-2" }, "删除下载源文件时，同时清理明确映射的本地整理副本。", -1)),
          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(mappingGroups.value, (group) => {
            return (_openBlock(), _createElementBlock("section", {
              key: group.field,
              class: "dm-sync-group"
            }, [
              _createElementVNode("div", _hoisted_4, [
                _createElementVNode("div", _hoisted_5, [
                  _createVNode(_component_VIcon, {
                    icon: group.icon,
                    size: "19"
                  }, null, 8, ["icon"]),
                  _createElementVNode("h3", null, _toDisplayString(group.title), 1),
                  _createElementVNode("span", _hoisted_6, _toDisplayString(group.rows.length), 1)
                ]),
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  color: "primary",
                  "prepend-icon": "mdi-plus",
                  "aria-label": `添加${group.title}映射`,
                  onClick: $event => (addMapping(group.field, group.columns))
                }, {
                  default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
                    _createTextVNode("添加映射", -1)
                  ]))]),
                  _: 1
                }, 8, ["aria-label", "onClick"])
              ]),
              (!group.rows.length)
                ? (_openBlock(), _createElementBlock("div", _hoisted_7, "尚未配置" + _toDisplayString(group.title) + "映射", 1))
                : (_openBlock(), _createElementBlock("div", _hoisted_8, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(group.rows, (row, index) => {
                      return (_openBlock(), _createElementBlock("details", {
                        key: index,
                        class: "dm-sync-mapping",
                        open: expandedMappings.value[group.field] === index
                      }, [
                        _createElementVNode("summary", {
                          class: "dm-sync-mapping-summary",
                          onClick: _withModifiers($event => (toggleMapping(group.field, index)), ["prevent"])
                        }, [
                          _createElementVNode("span", _hoisted_11, _toDisplayString(String(index + 1).padStart(2, '0')), 1),
                          _createElementVNode("span", _hoisted_12, [
                            _createElementVNode("strong", {
                              title: mappingTitle(row)
                            }, _toDisplayString(mappingTitle(row)), 9, _hoisted_13),
                            _createElementVNode("span", {
                              title: row[0]
                            }, _toDisplayString(row[0] || '填写目录，建立路径对应关系'), 9, _hoisted_14)
                          ]),
                          _createVNode(_component_VIcon, {
                            class: "dm-sync-chevron",
                            icon: "mdi-chevron-down",
                            size: "20"
                          })
                        ], 8, _hoisted_10),
                        (expandedMappings.value[group.field] === index)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_15, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(group.inputs, (input) => {
                                return (_openBlock(), _createBlock(_component_VTextarea, {
                                  key: input.column,
                                  "model-value": row[input.column] || '',
                                  label: input.label,
                                  class: "dm-sync-directory",
                                  rows: "2",
                                  "auto-grow": "",
                                  density: "compact",
                                  variant: "outlined",
                                  "hide-details": "",
                                  spellcheck: "false",
                                  "onUpdate:modelValue": $event => (editMapping(group.field, index, input.column, $event))
                                }, null, 8, ["model-value", "label", "onUpdate:modelValue"]))
                              }), 128)),
                              _createElementVNode("div", _hoisted_16, [
                                _createVNode(_component_VBtn, {
                                  size: "small",
                                  variant: "text",
                                  color: "error",
                                  "prepend-icon": "mdi-delete-outline",
                                  onClick: $event => (removeMapping(group.field, index))
                                }, {
                                  default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                                    _createTextVNode("移除此映射", -1)
                                  ]))]),
                                  _: 1
                                }, 8, ["onClick"])
                              ])
                            ]))
                          : _createCommentVNode("", true)
                      ], 8, _hoisted_9))
                    }), 128))
                  ]))
            ]))
          }), 128)),
          _createElementVNode("details", _hoisted_17, [
            _createElementVNode("summary", null, [
              _cache[14] || (_cache[14] = _createTextVNode("高级设置 · 删除范围", -1)),
              (sourceRoots.value.length)
                ? (_openBlock(), _createElementBlock("span", _hoisted_18, "（" + _toDisplayString(sourceRoots.value.length) + " 个源目录）", 1))
                : (__props.form.sync_delete_source || __props.form.sync_delete_torrents)
                  ? (_openBlock(), _createElementBlock("span", _hoisted_19, "（请填写源目录）"))
                  : _createCommentVNode("", true)
            ]),
            _cache[15] || (_cache[15] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mt-3" }, "源文件和种子仅在允许的目录内处理，保护目录中的文件保留。", -1)),
            _createVNode(_component_VTextarea, {
              modelValue: __props.form.sync_delete_source_paths,
              "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((__props.form.sync_delete_source_paths) = $event)),
              label: "允许删除的下载源目录",
              rows: "3",
              "auto-grow": "",
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              class: "my-4",
              placeholder: "填写 MP 容器内的真实下载目录，一行一个"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_VTextarea, {
              modelValue: __props.form.sync_delete_exclude_paths,
              "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((__props.form.sync_delete_exclude_paths) = $event)),
              label: "保护目录（可选）",
              rows: "2",
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              class: "my-4",
              placeholder: "一行一个路径，匹配到的文件保留"
            }, null, 8, ["modelValue"])
          ])
        ], 64))
      : (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
          _createElementVNode("div", _hoisted_20, [
            _createElementVNode("div", null, [
              _cache[17] || (_cache[17] = _createElementVNode("strong", null, "同步删除历史", -1)),
              _createElementVNode("div", _hoisted_21, _toDisplayString(enabled.value ? '同步删除已启用' : '同步删除未启用') + " · 共 " + _toDisplayString(total.value) + " 条", 1)
            ]),
            _createVNode(_component_VBtn, {
              variant: "text",
              icon: "mdi-refresh",
              loading: loading.value,
              "aria-label": "刷新同步删除历史",
              onClick: load
            }, null, 8, ["loading"])
          ]),
          (loading.value)
            ? (_openBlock(), _createBlock(_component_VProgressLinear, {
                key: 0,
                indeterminate: "",
                color: "primary",
                class: "mb-3"
              }))
            : _createCommentVNode("", true),
          (!rows.value.length && !loading.value)
            ? (_openBlock(), _createElementBlock("div", _hoisted_22, "暂无同步删除记录"))
            : _createCommentVNode("", true),
          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(rows.value, (job) => {
            return (_openBlock(), _createBlock(_component_VCard, {
              key: job.id,
              variant: "outlined",
              class: "dm-sync-job mb-3"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VCardText, null, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_23, [
                      _createElementVNode("strong", null, _toDisplayString(job.event?.name || job.event?.paths?.[0] || '媒体删除'), 1),
                      _createVNode(_component_VChip, {
                        color: color(job.state),
                        size: "small",
                        variant: "tonal"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(label(job.state)), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"])
                    ]),
                    _createElementVNode("div", _hoisted_24, _toDisplayString(dateText(job.updated_at)), 1),
                    (job.error)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_25, _toDisplayString(job.error), 1))
                      : _createCommentVNode("", true),
                    _createElementVNode("details", _hoisted_26, [
                      _cache[18] || (_cache[18] = _createElementVNode("summary", null, "查看关联明细", -1)),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList([...(job.plan?.cloud_files || []), ...(job.plan?.source_files || [])], (file) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: `${file.storage}:${file.path}`,
                          class: "dm-sync-path mt-2"
                        }, _toDisplayString(label(file.status)) + " · " + _toDisplayString(file.storage) + " · " + _toDisplayString(file.path), 1))
                      }), 128)),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(job.plan?.tasks || [], (task) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: `${task.downloader}:${task.id}`,
                          class: "dm-sync-path mt-2"
                        }, _toDisplayString(label(task.status)) + " · " + _toDisplayString(task.downloader) + " · " + _toDisplayString(task.id), 1))
                      }), 128)),
                      _createElementVNode("div", _hoisted_27, "整理记录已处理 " + _toDisplayString(job.records_done?.length || 0) + " / " + _toDisplayString(job.plan?.records?.length || 0), 1)
                    ]),
                    (job.state === 'failed')
                      ? (_openBlock(), _createBlock(_component_VBtn, {
                          key: 1,
                          class: "mt-3",
                          color: "warning",
                          variant: "tonal",
                          size: "small",
                          loading: retryId.value === job.id,
                          disabled: !props.canManage || !enabled.value || Boolean(retryId.value),
                          onClick: $event => (retry(job))
                        }, {
                          default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                            _createTextVNode("核验后重试", -1)
                          ]))]),
                          _: 1
                        }, 8, ["loading", "disabled", "onClick"]))
                      : _createCommentVNode("", true)
                  ]),
                  _: 2
                }, 1024)
              ]),
              _: 2
            }, 1024))
          }), 128)),
          (pages.value > 1)
            ? (_openBlock(), _createBlock(_component_VPagination, {
                key: 2,
                modelValue: page.value,
                "onUpdate:modelValue": [
                  _cache[9] || (_cache[9] = $event => ((page).value = $event)),
                  load
                ],
                length: pages.value,
                "total-visible": 5,
                density: "compact"
              }, null, 8, ["modelValue", "length"]))
            : _createCommentVNode("", true)
        ], 64))
  ]))
}
}

};
const SyncDeletePane = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-61ba0169"]]);

export { SyncDeletePane as S, _export_sfc as _, postPluginApi as a, getPluginApi as g, isApiRequestCancellation as i, postPluginJsonApi as p };
