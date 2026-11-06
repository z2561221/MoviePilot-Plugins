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

const {toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,createVNode:_createVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "dm-sync" };
const _hoisted_2 = { class: "dm-sync-heading" };
const _hoisted_3 = { class: "dm-sync-switches" };
const _hoisted_4 = {
  key: 1,
  class: "my-4"
};
const _hoisted_5 = {
  key: 3,
  class: "my-4"
};
const _hoisted_6 = {
  key: 4,
  class: "dm-sync-preview mt-4"
};
const _hoisted_7 = { class: "mb-2" };
const _hoisted_8 = { class: "dm-sync-heading mb-3" };
const _hoisted_9 = { class: "text-caption text-medium-emphasis" };
const _hoisted_10 = {
  key: 1,
  class: "text-medium-emphasis pa-6 text-center"
};
const _hoisted_11 = { class: "dm-sync-heading" };
const _hoisted_12 = { class: "text-caption text-medium-emphasis mt-1" };
const _hoisted_13 = {
  key: 0,
  class: "text-warning mt-2"
};
const _hoisted_14 = { class: "mt-3" };
const _hoisted_15 = { class: "text-caption mt-2" };

const {computed,onBeforeUnmount,ref,watch} = await importShared('vue');


const _sfc_main = {
  __name: 'SyncDeletePane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, required: true },
  form: { type: Object, default: null },
  mode: { type: String, default: 'history' },
},
  setup(__props, { expose: __expose }) {

const props = __props;
const servers = ref([]);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const enabled = ref(false);
const loading = ref(false);
const previewLoading = ref(false);
const error = ref('');
const notice = ref('');
const previewPath = ref('');
const previewPlan = ref(null);
const retryId = ref('');
const mappingMode = ref('text');
const cloudMappings = computed(() => String(props.form?.sync_delete_cloud_paths || '').split('\n').filter(Boolean).map(line => line.split('#')));
const localMappings = computed(() => String(props.form?.sync_delete_local_paths || '').split('\n').filter(Boolean).map(line => line.split('#')));
function editMapping(field, index, column, value) {
  const rows = String(props.form[field] || '').split('\n').filter(Boolean).map(line => line.split('#'));
  rows[index][column] = String(value || '');
  props.form[field] = rows.map(row => row.join('#')).join('\n');
}
function addMapping(field, columns) {
  const rows = String(props.form[field] || '').split('\n').filter(Boolean);
  rows.push(Array(columns).fill('').join('#'));
  props.form[field] = rows.join('\n');
}
function removeMapping(field, index) {
  props.form[field] = String(props.form[field] || '').split('\n').filter(Boolean).filter((_, i) => i !== index).join('\n');
}
let revision = 0;
let loadRevision = 0;
let previewRevision = 0;
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

async function preview() {
  const ticket = revision;
  const request = ++previewRevision;
  const id = props.pluginId;
  const owns = () => current(ticket, id) && request === previewRevision;
  previewLoading.value = true;
  error.value = '';
  previewPlan.value = null;
  try {
    const result = await postPluginJsonApi(props.api, id, 'sync_delete/preview', {
      path: previewPath.value.trim(), server: props.form?.sync_delete_servers?.[0] || '',
    }, { feedback: 'silent' });
    if (owns()) previewPlan.value = result?.plan || null;
  } catch (cause) {
    if (owns() && !isApiRequestCancellation(cause)) error.value = cause?.message || '无法匹配该路径';
  } finally {
    if (owns()) previewLoading.value = false;
  }
}

async function retry(job) {
  if (retryId.value) return
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
  previewPlan.value = null;
  previewLoading.value = false;
  notice.value = '';
  retryId.value = '';
  load();
}, { immediate: true, flush: 'sync' });
watch(() => [props.form, previewPath.value], () => {
  previewRevision++;
  previewLoading.value = false;
  previewPlan.value = null;
}, { deep: true, flush: 'sync' });
onBeforeUnmount(() => { disposed = true; revision++; });
__expose({ refresh: load });

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VBtnToggle = _resolveComponent("VBtnToggle");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VDivider = _resolveComponent("VDivider");
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
            _cache[19] || (_cache[19] = _createElementVNode("div", null, [
              _createElementVNode("strong", null, "同步删除"),
              _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "在 Emby 删除媒体后，联动网盘、源文件、整理记录和关联种子。")
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
            default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
              _createTextVNode("使用现有神医深度删除通知。合集仅删除部分文件时，关联种子保持暂停，其余集数保留。相同目录请只启用一个同步删除功能。", -1)
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
          _cache[28] || (_cache[28] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mt-2" }, "删除下载源文件同时清理下方明确映射的本地整理副本；关闭时两者均保留。", -1)),
          _createVNode(_component_VBtnToggle, {
            modelValue: mappingMode.value,
            "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((mappingMode).value = $event)),
            mandatory: "",
            density: "compact",
            color: "primary",
            class: "my-4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VBtn, {
                value: "text",
                size: "small"
              }, {
                default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                  _createTextVNode("批量填写", -1)
                ]))]),
                _: 1
              }),
              _createVNode(_component_VBtn, {
                value: "fields",
                size: "small"
              }, {
                default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                  _createTextVNode("分列填写", -1)
                ]))]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"]),
          (mappingMode.value === 'text')
            ? (_openBlock(), _createBlock(_component_VTextarea, {
                key: 0,
                modelValue: __props.form.sync_delete_local_paths,
                "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((__props.form.sync_delete_local_paths) = $event)),
                label: "本地媒体库路径映射",
                rows: "2",
                "auto-grow": "",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                class: "my-4",
                placeholder: "Emby路径#MP媒体库路径（一行一条）"
              }, null, 8, ["modelValue"]))
            : (_openBlock(), _createElementBlock("div", _hoisted_4, [
                _cache[24] || (_cache[24] = _createElementVNode("strong", null, "本地媒体库路径映射", -1)),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(localMappings.value, (row, index) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: index,
                    class: "dm-sync-mapping mt-3"
                  }, [
                    _createVNode(_component_VTextField, {
                      "model-value": row[0],
                      label: "Emby 路径",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      "onUpdate:modelValue": $event => (editMapping('sync_delete_local_paths', index, 0, $event))
                    }, null, 8, ["model-value", "onUpdate:modelValue"]),
                    _createVNode(_component_VTextField, {
                      "model-value": row[1],
                      label: "MP 媒体库路径",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      "onUpdate:modelValue": $event => (editMapping('sync_delete_local_paths', index, 1, $event))
                    }, null, 8, ["model-value", "onUpdate:modelValue"]),
                    _createVNode(_component_VBtn, {
                      icon: "mdi-close",
                      size: "small",
                      variant: "text",
                      "aria-label": "移除此映射",
                      onClick: $event => (removeMapping('sync_delete_local_paths', index))
                    }, null, 8, ["onClick"])
                  ]))
                }), 128)),
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  "prepend-icon": "mdi-plus",
                  class: "mt-2",
                  onClick: _cache[9] || (_cache[9] = $event => (addMapping('sync_delete_local_paths', 2)))
                }, {
                  default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                    _createTextVNode("添加本地映射", -1)
                  ]))]),
                  _: 1
                })
              ])),
          _createVNode(_component_VSelect, {
            modelValue: __props.form.sync_delete_storage,
            "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((__props.form.sync_delete_storage) = $event)),
            items: ['115网盘Plus'],
            label: "网盘存储",
            density: "compact",
            variant: "outlined",
            "hide-details": ""
          }, null, 8, ["modelValue"]),
          (mappingMode.value === 'text')
            ? (_openBlock(), _createBlock(_component_VTextarea, {
                key: 2,
                modelValue: __props.form.sync_delete_cloud_paths,
                "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((__props.form.sync_delete_cloud_paths) = $event)),
                label: "网盘媒体库路径映射",
                rows: "3",
                "auto-grow": "",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                class: "my-4",
                placeholder: "Emby路径#MP本地STRM路径#网盘目录#本地整理目录（最后一段可选，一行一条）"
              }, null, 8, ["modelValue"]))
            : (_openBlock(), _createElementBlock("div", _hoisted_5, [
                _cache[26] || (_cache[26] = _createElementVNode("strong", null, "网盘媒体库路径映射", -1)),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cloudMappings.value, (row, index) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: index,
                    class: "dm-sync-mapping dm-sync-mapping-cloud mt-3"
                  }, [
                    _createVNode(_component_VTextField, {
                      "model-value": row[0],
                      label: "Emby 路径",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      "onUpdate:modelValue": $event => (editMapping('sync_delete_cloud_paths', index, 0, $event))
                    }, null, 8, ["model-value", "onUpdate:modelValue"]),
                    _createVNode(_component_VTextField, {
                      "model-value": row[1],
                      label: "MP STRM 路径",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      "onUpdate:modelValue": $event => (editMapping('sync_delete_cloud_paths', index, 1, $event))
                    }, null, 8, ["model-value", "onUpdate:modelValue"]),
                    _createVNode(_component_VTextField, {
                      "model-value": row[2],
                      label: "网盘目录",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      "onUpdate:modelValue": $event => (editMapping('sync_delete_cloud_paths', index, 2, $event))
                    }, null, 8, ["model-value", "onUpdate:modelValue"]),
                    _createVNode(_component_VTextField, {
                      "model-value": row[3],
                      label: "本地整理目录（可选）",
                      density: "compact",
                      variant: "outlined",
                      "hide-details": "",
                      "onUpdate:modelValue": $event => (editMapping('sync_delete_cloud_paths', index, 3, $event))
                    }, null, 8, ["model-value", "onUpdate:modelValue"]),
                    _createVNode(_component_VBtn, {
                      icon: "mdi-close",
                      size: "small",
                      variant: "text",
                      "aria-label": "移除此映射",
                      onClick: $event => (removeMapping('sync_delete_cloud_paths', index))
                    }, null, 8, ["onClick"])
                  ]))
                }), 128)),
                _createVNode(_component_VBtn, {
                  size: "small",
                  variant: "text",
                  "prepend-icon": "mdi-plus",
                  class: "mt-2",
                  onClick: _cache[12] || (_cache[12] = $event => (addMapping('sync_delete_cloud_paths', 4)))
                }, {
                  default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                    _createTextVNode("添加网盘映射", -1)
                  ]))]),
                  _: 1
                })
              ])),
          _cache[29] || (_cache[29] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-3" }, "先整理到本地再上传网盘时，可填写对应的本地整理目录以关联整理记录和下载源；三段映射仍可继续使用。", -1)),
          _createVNode(_component_VTextarea, {
            modelValue: __props.form.sync_delete_source_paths,
            "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((__props.form.sync_delete_source_paths) = $event)),
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
            "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((__props.form.sync_delete_exclude_paths) = $event)),
            label: "保护目录（可选）",
            rows: "2",
            density: "compact",
            variant: "outlined",
            "hide-details": "",
            class: "my-4",
            placeholder: "一行一个路径，匹配到的文件保留"
          }, null, 8, ["modelValue"]),
          _createVNode(_component_VSwitch, {
            modelValue: __props.form.sync_delete_force_cloud,
            "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((__props.form.sync_delete_force_cloud) = $event)),
            color: "warning",
            inset: "",
            "hide-details": "",
            label: "没有整理记录时，也按映射删除网盘文件"
          }, null, 8, ["modelValue"]),
          _cache[30] || (_cache[30] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-3" }, "仍需唯一确认网盘实体；不会凭片名猜测下载器任务。", -1)),
          _createVNode(_component_VSwitch, {
            modelValue: __props.form.sync_delete_library_deleted,
            "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((__props.form.sync_delete_library_deleted) = $event)),
            color: "warning",
            inset: "",
            "hide-details": "",
            label: "同时处理普通 Emby 删除通知"
          }, null, 8, ["modelValue"]),
          _createVNode(_component_VDivider, { class: "my-4" }),
          _cache[31] || (_cache[31] = _createElementVNode("strong", null, "匹配预览", -1)),
          _cache[32] || (_cache[32] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-3" }, "先保存配置，再填写 Emby 中某个媒体文件的完整路径。预览只读取关联，不执行清理。", -1)),
          _createVNode(_component_VTextField, {
            modelValue: previewPath.value,
            "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((previewPath).value = $event)),
            label: "Emby 媒体路径",
            density: "compact",
            variant: "outlined",
            "hide-details": ""
          }, null, 8, ["modelValue"]),
          _createVNode(_component_VBtn, {
            class: "mt-3",
            color: "primary",
            variant: "tonal",
            "prepend-icon": "mdi-eye-outline",
            loading: previewLoading.value,
            disabled: !previewPath.value.trim(),
            onClick: preview
          }, {
            default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
              _createTextVNode("预览关联", -1)
            ]))]),
            _: 1
          }, 8, ["loading", "disabled"]),
          (previewPlan.value)
            ? (_openBlock(), _createElementBlock("div", _hoisted_6, [
                _createElementVNode("div", _hoisted_7, "网盘文件 " + _toDisplayString(previewPlan.value.cloud_files.length) + " · 源文件 " + _toDisplayString(previewPlan.value.source_files.length) + " · 关联种子 " + _toDisplayString(previewPlan.value.tasks.length) + " · 整理记录 " + _toDisplayString(previewPlan.value.records.length), 1),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList([...previewPlan.value.cloud_files, ...previewPlan.value.source_files], (file) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: `${file.storage}:${file.path}`,
                    class: "dm-sync-path"
                  }, _toDisplayString(file.storage) + " · " + _toDisplayString(file.path), 1))
                }), 128)),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(previewPlan.value.tasks, (task) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: `${task.downloader}:${task.id}`,
                    class: "dm-sync-path"
                  }, _toDisplayString(task.downloader) + " · " + _toDisplayString(task.id) + " · " + _toDisplayString(task.action === 'remove' ? '移除任务' : `暂停，保留 ${task.remaining} 个媒体文件`), 1))
                }), 128))
              ]))
            : _createCommentVNode("", true)
        ], 64))
      : (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
          _createElementVNode("div", _hoisted_8, [
            _createElementVNode("div", null, [
              _cache[33] || (_cache[33] = _createElementVNode("strong", null, "同步删除历史", -1)),
              _createElementVNode("div", _hoisted_9, _toDisplayString(enabled.value ? '同步删除已启用' : '同步删除未启用') + " · 共 " + _toDisplayString(total.value) + " 条", 1)
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
            ? (_openBlock(), _createElementBlock("div", _hoisted_10, "暂无同步删除记录"))
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
                    _createElementVNode("div", _hoisted_11, [
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
                    _createElementVNode("div", _hoisted_12, _toDisplayString(dateText(job.updated_at)), 1),
                    (job.error)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_13, _toDisplayString(job.error), 1))
                      : _createCommentVNode("", true),
                    _createElementVNode("details", _hoisted_14, [
                      _cache[34] || (_cache[34] = _createElementVNode("summary", null, "查看关联明细", -1)),
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
                      _createElementVNode("div", _hoisted_15, "整理记录已处理 " + _toDisplayString(job.records_done?.length || 0) + " / " + _toDisplayString(job.plan?.records?.length || 0), 1)
                    ]),
                    (job.state === 'failed')
                      ? (_openBlock(), _createBlock(_component_VBtn, {
                          key: 1,
                          class: "mt-3",
                          color: "warning",
                          variant: "tonal",
                          size: "small",
                          loading: retryId.value === job.id,
                          disabled: !enabled.value || Boolean(retryId.value),
                          onClick: $event => (retry(job))
                        }, {
                          default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
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
                  _cache[18] || (_cache[18] = $event => ((page).value = $event)),
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
const SyncDeletePane = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-ae90afb1"]]);

export { SyncDeletePane as S, _export_sfc as _, postPluginApi as a, getPluginApi as g, isApiRequestCancellation as i, postPluginJsonApi as p };
