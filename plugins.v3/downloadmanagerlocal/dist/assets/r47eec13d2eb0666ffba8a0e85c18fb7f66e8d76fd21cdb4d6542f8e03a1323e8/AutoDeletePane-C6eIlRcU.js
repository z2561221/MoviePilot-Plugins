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

const permissionSessions = new WeakMap();

function permissionSession(api) {
  let session = permissionSessions.get(api);
  if (!session) {
    session = { entry: null };
    permissionSessions.set(api, session);
    api.interceptors?.response?.use(value => value, error => {
      if ([401, 403].includes(error?.response?.status)) session.entry = null;
      return Promise.reject(error)
    });
  }
  return session
}

async function getManagementPermission(api, { signal, timeoutMs = 8000, refresh = false } = {}) {
  if (!api?.get) throw new Error('MoviePilot 登录接口未就绪')
  const session = permissionSession(api);
  if (refresh) session.entry = null;
  const controller = new AbortController();
  let timer;
  let rejectWait;
  let entry;
  let ownsEntry = false;
  const interrupted = new Promise((_resolve, reject) => { rejectWait = reject; });
  const cancel = () => {
    const error = new Error('权限核验被中断');
    error.name = 'AbortError';
    rejectWait(error);
    controller.abort();
  };
  try {
    if (signal?.aborted) cancel();
    else signal?.addEventListener('abort', cancel, { once: true });
    timer = setTimeout(() => {
      const error = new Error('权限核验超时，请重新检查。');
      error.name = 'PermissionTimeoutError';
      rejectWait(error);
      controller.abort();
    }, timeoutMs);
    const request = signal?.aborted ? interrupted : api.get('user/current', {
      feedback: 'silent', signal: controller.signal, timeout: timeoutMs,
      transformRequest: [function (data, headers) {
        // Axios此阶段已执行宿主认证拦截器；只比较当前会话，不读取持久登录存储。
        const identity = typeof headers?.get === 'function' ? headers.get('Authorization') : headers?.Authorization || headers?.authorization;
        if (!identity) { session.entry = null; return data }
        const scope = String(this.baseURL || '') + '\n' + String(identity);
        const cached = session.entry;
        if (cached?.scope === scope) {
          entry = cached;
          this.adapter = async config => ({ data: await cached.result, status: 200, statusText: 'OK', headers: {}, config });
        } else {
          let resolve, reject;
          const result = new Promise((yes, no) => { resolve = yes; reject = no; });
          result.catch(() => {});
          entry = { scope, result, resolve, reject };
          session.entry = entry;
          ownsEntry = true;
        }
        return data
      }],
    });
    const user = unwrapResponse(await Promise.race([request, interrupted]));
    if (typeof user?.is_superuser !== 'boolean' || typeof user?.is_active !== 'boolean') {
      throw new Error('当前用户接口未返回明确权限')
    }
    if (ownsEntry) entry.resolve({ is_active: user.is_active, is_superuser: user.is_superuser });
    return { can_manage: user.is_active && user.is_superuser }
  } catch (error) {
    if (ownsEntry) {
      entry.reject(error);
      if (session.entry === entry) session.entry = null;
    }
    throw error
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}

const {toDisplayString:_toDisplayString$3,createElementVNode:_createElementVNode$3,createTextVNode:_createTextVNode$3,resolveComponent:_resolveComponent$3,withCtx:_withCtx$2,createVNode:_createVNode$3,renderSlot:_renderSlot,openBlock:_openBlock$4,createElementBlock:_createElementBlock$4,createCommentVNode:_createCommentVNode$4} = await importShared('vue');


const _hoisted_1$4 = { class: "dm-history-row" };
const _hoisted_2$4 = { class: "dm-history-summary" };
const _hoisted_3$3 = ["title"];
const _hoisted_4$3 = ["title"];
const _hoisted_5$3 = {
  key: 0,
  class: "dm-history-expanded"
};
const _hoisted_6$3 = { class: "dm-history-entry-meta" };

const {ref: ref$3} = await importShared('vue');



const _sfc_main$4 = {
  __name: 'HistoryRow',
  props: {
  time: String,
  name: String,
  status: String,
  color: String,
},
  setup(__props) {


const expanded = ref$3(false);

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$3("VChip");
  const _component_VBtn = _resolveComponent$3("VBtn");

  return (_openBlock$4(), _createElementBlock$4("article", _hoisted_1$4, [
    _createElementVNode$3("div", _hoisted_2$4, [
      _createElementVNode$3("span", {
        class: "dm-history-time",
        title: __props.time
      }, _toDisplayString$3(__props.time || '—'), 9 /* TEXT, PROPS */, _hoisted_3$3),
      _createElementVNode$3("strong", {
        class: "dm-history-name",
        title: __props.name
      }, _toDisplayString$3(__props.name || '—'), 9 /* TEXT, PROPS */, _hoisted_4$3),
      _createVNode$3(_component_VChip, {
        class: "dm-history-status",
        size: "x-small",
        variant: "tonal",
        color: __props.color,
        title: __props.status
      }, {
        default: _withCtx$2(() => [
          _createTextVNode$3(_toDisplayString$3(__props.status || '—'), 1 /* TEXT */)
        ]),
        _: 1 /* STABLE */
      }, 8 /* PROPS */, ["color", "title"]),
      _createVNode$3(_component_VBtn, {
        class: "dm-history-toggle",
        size: "small",
        variant: "text",
        color: "primary",
        "aria-expanded": expanded.value,
        "aria-label": (expanded.value ? '收起明细 · ' : '查看明细 · ') + (__props.name || '记录'),
        onClick: _cache[0] || (_cache[0] = $event => (expanded.value = !expanded.value))
      }, {
        default: _withCtx$2(() => [
          _createTextVNode$3(_toDisplayString$3(expanded.value ? '收起' : '明细'), 1 /* TEXT */)
        ]),
        _: 1 /* STABLE */
      }, 8 /* PROPS */, ["aria-expanded", "aria-label"])
    ]),
    (expanded.value)
      ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_5$3, [
          _createElementVNode$3("strong", null, _toDisplayString$3(__props.name || '—'), 1 /* TEXT */),
          _createElementVNode$3("div", _hoisted_6$3, _toDisplayString$3(__props.time || '—') + " · " + _toDisplayString$3(__props.status || '—'), 1 /* TEXT */),
          _renderSlot(_ctx.$slots, "default")
        ]))
      : _createCommentVNode$4("v-if", true)
  ]))
}
}

};

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {toDisplayString:_toDisplayString$2,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3,createCommentVNode:_createCommentVNode$3,createTextVNode:_createTextVNode$2,renderList:_renderList$2,Fragment:_Fragment$2,createElementVNode:_createElementVNode$2} = await importShared('vue');


const _hoisted_1$3 = { class: "dm-sync-details dm-history-detail" };
const _hoisted_2$3 = {
  key: 0,
  class: "dm-history-entry-meta"
};
const _hoisted_3$2 = { key: 0 };
const _hoisted_4$2 = { class: "dm-sync-detail-path mt-2" };
const _hoisted_5$2 = {
  key: 0,
  class: "dm-sync-detail-path mt-2"
};
const _hoisted_6$2 = { class: "text-caption mt-2" };
const _hoisted_7$2 = {
  key: 1,
  class: "text-caption mt-2"
};


const _sfc_main$3 = {
  __name: 'SyncDeleteDetails',
  props: { job: { type: Object, required: true } },
  setup(__props) {


const labels = { pending: '待执行', deleted: '已删除', absent: '已不存在', removed: '已移除', paused: '保留并暂停' };
const label = state => labels[state] || state;
const dateText = stamp => stamp ? new Date(stamp * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '—';

return (_ctx, _cache) => {
  return (_openBlock$3(), _createElementBlock$3("div", _hoisted_1$3, [
    (__props.job.resolution)
      ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_2$3, [
          _createTextVNode$2(_toDisplayString$2(__props.job.resolution.actor) + " · " + _toDisplayString$2(dateText(__props.job.resolution.resolved_at)), 1 /* TEXT */),
          (__props.job.resolution.reason && __props.job.resolution.reason !== '用户忽略')
            ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_3$2, " · " + _toDisplayString$2(__props.job.resolution.reason), 1 /* TEXT */))
            : _createCommentVNode$3("v-if", true)
        ]))
      : _createCommentVNode$3("v-if", true),
    (_openBlock$3(true), _createElementBlock$3(_Fragment$2, null, _renderList$2(__props.job.event?.paths || [], (path, index) => {
      return (_openBlock$3(), _createElementBlock$3(_Fragment$2, {
        key: `source:${index}`
      }, [
        _createElementVNode$2("div", _hoisted_4$2, "事件路径 · " + _toDisplayString$2(path), 1 /* TEXT */),
        (__props.job.event?.original_paths?.[index] && __props.job.event.original_paths[index] !== path)
          ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_5$2, "历史源路径 · " + _toDisplayString$2(__props.job.event.original_paths[index]) + " → " + _toDisplayString$2(path), 1 /* TEXT */))
          : _createCommentVNode$3("v-if", true)
      ], 64 /* STABLE_FRAGMENT */))
    }), 128 /* KEYED_FRAGMENT */)),
    (_openBlock$3(true), _createElementBlock$3(_Fragment$2, null, _renderList$2([...(__props.job.plan?.cloud_files || []), ...(__props.job.plan?.source_files || [])], (file) => {
      return (_openBlock$3(), _createElementBlock$3("div", {
        key: `${file.storage}:${file.path}`,
        class: "dm-sync-detail-path mt-2"
      }, _toDisplayString$2(label(file.status)) + " · " + _toDisplayString$2(file.storage) + " · " + _toDisplayString$2(file.path), 1 /* TEXT */))
    }), 128 /* KEYED_FRAGMENT */)),
    (_openBlock$3(true), _createElementBlock$3(_Fragment$2, null, _renderList$2(__props.job.plan?.tasks || [], (task) => {
      return (_openBlock$3(), _createElementBlock$3("div", {
        key: `${task.downloader}:${task.id}`,
        class: "dm-sync-detail-path mt-2"
      }, _toDisplayString$2(label(task.status)) + " · " + _toDisplayString$2(task.downloader) + " · " + _toDisplayString$2(task.id), 1 /* TEXT */))
    }), 128 /* KEYED_FRAGMENT */)),
    _createElementVNode$2("div", _hoisted_6$2, "整理记录已处理 " + _toDisplayString$2(__props.job.records_done?.length || 0) + " / " + _toDisplayString$2(__props.job.plan?.records?.length || 0), 1 /* TEXT */),
    (__props.job.plan?.download_records?.length)
      ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_7$2, "旧下载记录已标记 " + _toDisplayString$2(__props.job.download_records_done?.length || 0) + " / " + _toDisplayString$2(__props.job.plan.download_records.length), 1 /* TEXT */))
      : _createCommentVNode$3("v-if", true)
  ]))
}
}

};
const SyncDeleteDetails = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-5d56c94e"]]);

const {toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$2,withCtx:_withCtx$1,openBlock:_openBlock$2,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2,createElementVNode:_createElementVNode$1,createVNode:_createVNode$2,createElementBlock:_createElementBlock$2,renderList:_renderList$1,Fragment:_Fragment$1,withModifiers:_withModifiers,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1$2 = {
  key: 0,
  "data-config-section": "basic"
};
const _hoisted_2$2 = { class: "dm-sync-heading" };
const _hoisted_3$1 = {
  key: 1,
  "data-config-section": "filter"
};
const _hoisted_4$1 = { class: "dm-sync-group-head" };
const _hoisted_5$1 = { class: "dm-sync-group-title" };
const _hoisted_6$1 = { class: "dm-sync-count" };
const _hoisted_7$1 = {
  key: 0,
  class: "dm-sync-empty"
};
const _hoisted_8$1 = {
  key: 1,
  class: "dm-sync-mapping-list"
};
const _hoisted_9$1 = ["open"];
const _hoisted_10$1 = ["onClick"];
const _hoisted_11$1 = { class: "dm-sync-index" };
const _hoisted_12$1 = { class: "dm-sync-mapping-label" };
const _hoisted_13$1 = ["title"];
const _hoisted_14$1 = ["title"];
const _hoisted_15$1 = {
  key: 0,
  class: "dm-sync-mapping-editor"
};
const _hoisted_16$1 = { class: "dm-sync-editor-footer" };
const _hoisted_17$1 = {
  key: 2,
  "data-config-section": "advanced"
};
const _hoisted_18$1 = { class: "dm-sync-switches" };
const _hoisted_19$1 = {
  open: "",
  class: "my-4"
};
const _hoisted_20$1 = { key: 0 };
const _hoisted_21$1 = {
  key: 1,
  class: "text-warning"
};
const _hoisted_22$1 = { class: "dm-history-toolbar" };
const _hoisted_23$1 = { class: "dm-history-title" };
const _hoisted_24$1 = { class: "dm-history-count" };
const _hoisted_25$1 = { class: "dm-history-entry-meta" };
const _hoisted_26$1 = { class: "dm-sync-history-tools dm-history-tools" };
const _hoisted_27$1 = {
  key: 1,
  class: "dm-history-empty"
};
const _hoisted_28$1 = {
  key: 1,
  class: "text-medium-emphasis"
};
const _hoisted_29$1 = {
  key: 2,
  class: "mt-3"
};
const _hoisted_30$1 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_31$1 = {
  key: 1,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_32 = {
  key: 2,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_33 = { class: "dm-sync-actions dm-history-actions" };
const _hoisted_34 = {
  key: 2,
  class: "dm-history-pagination"
};
const _hoisted_35 = { class: "dm-history-count" };
const _hoisted_36 = { class: "font-weight-medium mb-3" };
const {computed: computed$1,onBeforeUnmount: onBeforeUnmount$1,ref: ref$2,watch: watch$2} = await importShared('vue');


const _sfc_main$2 = {
  __name: 'SyncDeletePane',
  props: {
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, required: true },
  form: { type: Object, default: null },
  mode: { type: String, default: 'history' },
  section: { type: String, default: 'basic' },
  canManage: { type: Boolean, default: false },
  initialPendingOnly: { type: Boolean, default: false },
},
  setup(__props, { expose: __expose }) {

const props = __props;
const servers = ref$2([]);
const rows = ref$2([]);
const total = ref$2(0);
const page = ref$2(1);
const enabled = ref$2(false);
const loading = ref$2(false);
const error = ref$2('');
const notice = ref$2('');
const retryId = ref$2('');
const pendingOnly = ref$2(Boolean(props.initialPendingOnly));
const actionDialog = ref$2(false);
const actionKind = ref$2('');
const actionJob = ref$2(null);
const actionError = ref$2('');
const expandedMappings = ref$2({});
const mappingRows = value => String(value || '').split('\n').filter(line => line.trim()).map(line => line.split('#'));
const cloudMappings = computed$1(() => mappingRows(props.form?.sync_delete_cloud_paths));
const localMappings = computed$1(() => mappingRows(props.form?.sync_delete_local_paths));
const mappingGroups = computed$1(() => [
  { field: 'sync_delete_local_paths', title: '本地媒体库', icon: 'mdi-folder-outline', columns: 2, rows: localMappings.value,
    inputs: [{ column: 0, label: 'Emby 媒体目录' }, { column: 1, label: 'MP 本地媒体目录' }] },
  { field: 'sync_delete_cloud_paths', title: 'STRM 媒体库', icon: 'mdi-cloud-outline', columns: 4, rows: cloudMappings.value,
    inputs: [{ column: 0, label: 'Emby STRM 目录' }, { column: 1, label: 'MP STRM 目录' },
      { column: 3, label: '本地整理目录（可选）' }, { column: 2, label: '网盘目录' }] },
]);
const sourceRoots = computed$1(() => String(props.form?.sync_delete_source_paths || '').split('\n').map(line => line.trim()).filter(Boolean));
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
const pages = computed$1(() => Math.max(1, Math.ceil(total.value / 15)));
const labels = { queued: '等待执行', running: '处理中', failed: '待处理', completed: '完成', skipped: '无需处理', dismissed: '已忽略', pending: '待执行', deleted: '已删除', absent: '已不存在', removed: '已移除', paused: '保留并暂停' };
const label = state => labels[state] || state;
const color = state => ['completed', 'skipped'].includes(state) ? 'success' : state === 'failed' ? 'warning' : state === 'dismissed' ? 'default' : 'info';
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
      const result = await getPluginApi(props.api, id, `sync_delete/history?page=${page.value}&page_size=15&pending_only=${pendingOnly.value}`, { feedback: 'silent' });
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
  if (!props.canManage || !enabled.value || retryId.value || job.review?.retry_allowed === false) return false
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
      return owns()
    }
    if (owns()) error.value = '重试未受理，请刷新记录后再试。';
  } catch (cause) {
    if (owns() && !isApiRequestCancellation(cause)) error.value = cause?.message || '重试未受理';
  } finally {
    if (owns()) retryId.value = '';
  }
  return false
}

function filterHistory() {
  page.value = 1;
  void load();
}

function requestAction(kind, job) {
  if (!props.canManage || retryId.value) return
  if (!enabled.value || job.review?.retry_allowed === false) return
  actionKind.value = kind;
  actionJob.value = job;
  actionError.value = '';
  actionDialog.value = true;
}

async function confirmAction() {
  const job = actionJob.value;
  if (!props.canManage || !job || retryId.value) return
  const ticket = revision, id = props.pluginId;
  const accepted = await retry(job);
  if (current(ticket, id) && accepted) actionDialog.value = false;
  else if (current(ticket, id)) actionError.value = error.value || '重试未受理';
}

async function ignore(job) {
  if (!props.canManage || retryId.value || !job.review?.dismiss_allowed) return
  const ticket = revision, id = props.pluginId;
  const request = ++retryRevision;
  const owns = () => current(ticket, id) && request === retryRevision;
  retryId.value = job.id;
  actionKind.value = 'ignore';
  error.value = '';
  notice.value = '';
  try {
    const result = await postPluginJsonApi(props.api, id, 'sync_delete/dismiss', {
      job_id: job.id, expected_revision: job.review.revision,
    }, { feedback: 'silent' });
    if (owns()) {
      if (result?.state !== 'dismissed') throw new Error('忽略未确认，请刷新记录')
      notice.value = '已忽略，历史记录保留。';
      await load();
    }
  } catch (cause) {
    if (owns() && !isApiRequestCancellation(cause)) error.value = cause?.message || '忽略失败，请刷新后重试';
  } finally { if (owns()) retryId.value = ''; }
}

watch$2(() => [props.pluginId, props.mode, props.api], () => {
  revision++;
  page.value = 1;
  rows.value = [];
  servers.value = [];
  total.value = 0;
  enabled.value = false;
  expandedMappings.value = {};
  notice.value = '';
  retryId.value = '';
  pendingOnly.value = Boolean(props.initialPendingOnly);
  actionDialog.value = false;
  actionJob.value = null;
  actionError.value = '';
  load();
}, { immediate: true, flush: 'sync' });
onBeforeUnmount$1(() => { disposed = true; revision++; });
__expose({ refresh: load, busy: computed$1(() => Boolean(retryId.value)) });

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent$2("VAlert");
  const _component_VSwitch = _resolveComponent$2("VSwitch");
  const _component_VSelect = _resolveComponent$2("VSelect");
  const _component_VIcon = _resolveComponent$2("VIcon");
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VTextarea = _resolveComponent$2("VTextarea");
  const _component_VProgressLinear = _resolveComponent$2("VProgressLinear");
  const _component_VPagination = _resolveComponent$2("VPagination");
  const _component_VCardTitle = _resolveComponent$2("VCardTitle");
  const _component_VCardText = _resolveComponent$2("VCardText");
  const _component_VSpacer = _resolveComponent$2("VSpacer");
  const _component_VCardActions = _resolveComponent$2("VCardActions");
  const _component_VCard = _resolveComponent$2("VCard");
  const _component_VDialog = _resolveComponent$2("VDialog");

  return (_openBlock$2(), _createElementBlock$2("div", {
    class: _normalizeClass(["dm-sync", { 'dm-history-surface': __props.mode === 'history' }])
  }, [
    (error.value)
      ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx$1(() => [
            _createTextVNode$1(_toDisplayString$1(error.value), 1 /* TEXT */)
          ]),
          _: 1 /* STABLE */
        }))
      : _createCommentVNode$2("v-if", true),
    (notice.value)
      ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
          key: 1,
          type: "info",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx$1(() => [
            _createTextVNode$1(_toDisplayString$1(notice.value), 1 /* TEXT */)
          ]),
          _: 1 /* STABLE */
        }))
      : _createCommentVNode$2("v-if", true),
    (__props.mode === 'config' && __props.form)
      ? (_openBlock$2(), _createElementBlock$2(_Fragment$1, { key: 2 }, [
          (__props.section === 'basic')
            ? (_openBlock$2(), _createElementBlock$2("section", _hoisted_1$2, [
                _createElementVNode$1("div", _hoisted_2$2, [
                  _cache[14] || (_cache[14] = _createElementVNode$1("div", null, [
                    _createElementVNode$1("strong", null, "同步删除"),
                    _createElementVNode$1("div", { class: "text-caption text-medium-emphasis" }, "在 Emby 删除本地媒体或 STRM 后，清理关联文件、种子和整理记录。")
                  ], -1 /* CACHED */)),
                  _createVNode$2(_component_VSwitch, {
                    modelValue: __props.form.sync_delete_enabled,
                    "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((__props.form.sync_delete_enabled) = $event)),
                    color: "success",
                    inset: "",
                    "hide-details": "",
                    label: "启用"
                  }, null, 8 /* PROPS */, ["modelValue"])
                ]),
                _createVNode$2(_component_VSelect, {
                  modelValue: __props.form.sync_delete_servers,
                  "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((__props.form.sync_delete_servers) = $event)),
                  items: servers.value,
                  multiple: "",
                  chips: "",
                  "closable-chips": "",
                  label: "Emby 服务器",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  class: "my-4"
                }, null, 8 /* PROPS */, ["modelValue", "items"]),
                _createVNode$2(_component_VSwitch, {
                  modelValue: __props.form.sync_delete_notify,
                  "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((__props.form.sync_delete_notify) = $event)),
                  color: "info",
                  inset: "",
                  "hide-details": "",
                  label: "发送结果通知"
                }, null, 8 /* PROPS */, ["modelValue"]),
                _createVNode$2(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mt-3"
                }, {
                  default: _withCtx$1(() => [...(_cache[15] || (_cache[15] = [
                    _createTextVNode$1("使用现有神医深度删除通知。合集还有其它集数时，种子暂停保留。", -1 /* CACHED */)
                  ]))]),
                  _: 1 /* STABLE */
                })
              ]))
            : _createCommentVNode$2("v-if", true),
          (__props.section === 'filter')
            ? (_openBlock$2(), _createElementBlock$2("section", _hoisted_3$1, [
                _cache[18] || (_cache[18] = _createElementVNode$1("div", { class: "text-caption text-medium-emphasis" }, "路径映射决定哪些媒体库目录能对应到本机或网盘文件；这里只保存对应关系，不直接执行删除。", -1 /* CACHED */)),
                (_openBlock$2(true), _createElementBlock$2(_Fragment$1, null, _renderList$1(mappingGroups.value, (group) => {
                  return (_openBlock$2(), _createElementBlock$2("section", {
                    key: group.field,
                    class: "dm-sync-group"
                  }, [
                    _createElementVNode$1("div", _hoisted_4$1, [
                      _createElementVNode$1("div", _hoisted_5$1, [
                        _createVNode$2(_component_VIcon, {
                          icon: group.icon,
                          size: "19"
                        }, null, 8 /* PROPS */, ["icon"]),
                        _createElementVNode$1("h3", null, _toDisplayString$1(group.title), 1 /* TEXT */),
                        _createElementVNode$1("span", _hoisted_6$1, _toDisplayString$1(group.rows.length), 1 /* TEXT */)
                      ]),
                      _createVNode$2(_component_VBtn, {
                        size: "small",
                        variant: "text",
                        color: "primary",
                        "prepend-icon": "mdi-plus",
                        "aria-label": `添加${group.title}映射`,
                        onClick: $event => (addMapping(group.field, group.columns))
                      }, {
                        default: _withCtx$1(() => [...(_cache[16] || (_cache[16] = [
                          _createTextVNode$1("添加映射", -1 /* CACHED */)
                        ]))]),
                        _: 1 /* STABLE */
                      }, 8 /* PROPS */, ["aria-label", "onClick"])
                    ]),
                    (!group.rows.length)
                      ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_7$1, "尚未配置" + _toDisplayString$1(group.title) + "映射", 1 /* TEXT */))
                      : (_openBlock$2(), _createElementBlock$2("div", _hoisted_8$1, [
                          (_openBlock$2(true), _createElementBlock$2(_Fragment$1, null, _renderList$1(group.rows, (row, index) => {
                            return (_openBlock$2(), _createElementBlock$2("details", {
                              key: index,
                              class: "dm-sync-mapping",
                              open: expandedMappings.value[group.field] === index
                            }, [
                              _createElementVNode$1("summary", {
                                class: "dm-sync-mapping-summary",
                                onClick: _withModifiers($event => (toggleMapping(group.field, index)), ["prevent"])
                              }, [
                                _createElementVNode$1("span", _hoisted_11$1, _toDisplayString$1(String(index + 1).padStart(2, '0')), 1 /* TEXT */),
                                _createElementVNode$1("span", _hoisted_12$1, [
                                  _createElementVNode$1("strong", {
                                    title: mappingTitle(row)
                                  }, _toDisplayString$1(mappingTitle(row)), 9 /* TEXT, PROPS */, _hoisted_13$1),
                                  _createElementVNode$1("span", {
                                    title: row[0]
                                  }, _toDisplayString$1(row[0] || '填写目录，建立路径对应关系'), 9 /* TEXT, PROPS */, _hoisted_14$1)
                                ]),
                                _createVNode$2(_component_VIcon, {
                                  class: "dm-sync-chevron",
                                  icon: "mdi-chevron-down",
                                  size: "20"
                                })
                              ], 8 /* PROPS */, _hoisted_10$1),
                              (expandedMappings.value[group.field] === index)
                                ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_15$1, [
                                    (_openBlock$2(true), _createElementBlock$2(_Fragment$1, null, _renderList$1(group.inputs, (input) => {
                                      return (_openBlock$2(), _createBlock$2(_component_VTextarea, {
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
                                      }, null, 8 /* PROPS */, ["model-value", "label", "onUpdate:modelValue"]))
                                    }), 128 /* KEYED_FRAGMENT */)),
                                    _createElementVNode$1("div", _hoisted_16$1, [
                                      _createVNode$2(_component_VBtn, {
                                        size: "small",
                                        variant: "text",
                                        color: "error",
                                        "prepend-icon": "mdi-delete-outline",
                                        onClick: $event => (removeMapping(group.field, index))
                                      }, {
                                        default: _withCtx$1(() => [...(_cache[17] || (_cache[17] = [
                                          _createTextVNode$1("移除此映射", -1 /* CACHED */)
                                        ]))]),
                                        _: 1 /* STABLE */
                                      }, 8 /* PROPS */, ["onClick"])
                                    ])
                                  ]))
                                : _createCommentVNode$2("v-if", true)
                            ], 8 /* PROPS */, _hoisted_9$1))
                          }), 128 /* KEYED_FRAGMENT */))
                        ]))
                  ]))
                }), 128 /* KEYED_FRAGMENT */))
              ]))
            : _createCommentVNode$2("v-if", true),
          (__props.section === 'advanced')
            ? (_openBlock$2(), _createElementBlock$2("section", _hoisted_17$1, [
                _cache[22] || (_cache[22] = _createElementVNode$1("div", { class: "dm-sync-heading mb-3" }, [
                  _createElementVNode$1("strong", null, "高级选项 · 删除范围与动作")
                ], -1 /* CACHED */)),
                _createElementVNode$1("div", _hoisted_18$1, [
                  _createVNode$2(_component_VSwitch, {
                    modelValue: __props.form.sync_delete_cloud,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((__props.form.sync_delete_cloud) = $event)),
                    color: "error",
                    inset: "",
                    "hide-details": "",
                    label: "删除网盘文件"
                  }, null, 8 /* PROPS */, ["modelValue"]),
                  _createVNode$2(_component_VSwitch, {
                    modelValue: __props.form.sync_delete_source,
                    "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((__props.form.sync_delete_source) = $event)),
                    color: "error",
                    inset: "",
                    "hide-details": "",
                    label: "删除下载源文件"
                  }, null, 8 /* PROPS */, ["modelValue"]),
                  _createVNode$2(_component_VSwitch, {
                    modelValue: __props.form.sync_delete_torrents,
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((__props.form.sync_delete_torrents) = $event)),
                    color: "error",
                    inset: "",
                    "hide-details": "",
                    label: "移除源种、转种和辅种"
                  }, null, 8 /* PROPS */, ["modelValue"]),
                  _createVNode$2(_component_VSwitch, {
                    modelValue: __props.form.sync_delete_records,
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((__props.form.sync_delete_records) = $event)),
                    color: "warning",
                    inset: "",
                    "hide-details": "",
                    label: "清理整理记录"
                  }, null, 8 /* PROPS */, ["modelValue"])
                ]),
                _cache[23] || (_cache[23] = _createElementVNode$1("div", { class: "text-caption text-medium-emphasis mt-2" }, "删除下载源文件时，同时清理明确映射的本地整理副本。", -1 /* CACHED */)),
                _createElementVNode$1("details", _hoisted_19$1, [
                  _createElementVNode$1("summary", null, [
                    _cache[19] || (_cache[19] = _createTextVNode$1("允许删除范围", -1 /* CACHED */)),
                    (sourceRoots.value.length)
                      ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_20$1, "（" + _toDisplayString$1(sourceRoots.value.length) + " 个源目录）", 1 /* TEXT */))
                      : (__props.form.sync_delete_source || __props.form.sync_delete_torrents)
                        ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_21$1, "（请填写源目录）"))
                        : _createCommentVNode$2("v-if", true)
                  ]),
                  _cache[20] || (_cache[20] = _createElementVNode$1("div", { class: "text-caption text-medium-emphasis mt-3" }, "源文件和种子仅在允许的目录内处理，保护目录中的文件保留。", -1 /* CACHED */)),
                  _createVNode$2(_component_VTextarea, {
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
                  }, null, 8 /* PROPS */, ["modelValue"]),
                  _createVNode$2(_component_VTextarea, {
                    modelValue: __props.form.sync_delete_source_aliases,
                    "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((__props.form.sync_delete_source_aliases) = $event)),
                    label: "历史源路径映射（可选）",
                    rows: "3",
                    "auto-grow": "",
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    class: "my-4",
                    placeholder: "历史目录#当前 MP 容器目录，一行一条"
                  }, null, 8 /* PROPS */, ["modelValue"]),
                  _cache[21] || (_cache[21] = _createElementVNode$1("div", { class: "text-caption text-medium-emphasis" }, "目录迁移后，用此映射识别旧下载记录。当前目录须在允许范围内；仍被新下载引用的文件保留。", -1 /* CACHED */)),
                  _createVNode$2(_component_VTextarea, {
                    modelValue: __props.form.sync_delete_exclude_paths,
                    "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((__props.form.sync_delete_exclude_paths) = $event)),
                    label: "保护目录（可选）",
                    rows: "2",
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    class: "my-4",
                    placeholder: "一行一个路径，匹配到的文件保留"
                  }, null, 8 /* PROPS */, ["modelValue"])
                ])
              ]))
            : _createCommentVNode$2("v-if", true)
        ], 64 /* STABLE_FRAGMENT */))
      : (_openBlock$2(), _createElementBlock$2(_Fragment$1, { key: 3 }, [
          _createElementVNode$1("div", _hoisted_22$1, [
            _createElementVNode$1("div", null, [
              _createElementVNode$1("h3", _hoisted_23$1, [
                _cache[24] || (_cache[24] = _createTextVNode$1("同步删除历史", -1 /* CACHED */)),
                _createElementVNode$1("span", _hoisted_24$1, "共 " + _toDisplayString$1(total.value) + " 条", 1 /* TEXT */)
              ]),
              _createElementVNode$1("div", _hoisted_25$1, _toDisplayString$1(enabled.value ? '同步删除已启用' : '同步删除未启用'), 1 /* TEXT */)
            ]),
            _createElementVNode$1("div", _hoisted_26$1, [
              _createVNode$2(_component_VSwitch, {
                modelValue: pendingOnly.value,
                "onUpdate:modelValue": [
                  _cache[10] || (_cache[10] = $event => ((pendingOnly).value = $event)),
                  filterHistory
                ],
                label: "仅待处理",
                density: "compact",
                "hide-details": "",
                inset: ""
              }, null, 8 /* PROPS */, ["modelValue"]),
              _createVNode$2(_component_VBtn, {
                variant: "text",
                icon: "mdi-refresh",
                loading: loading.value,
                "aria-label": "刷新同步删除历史",
                onClick: load
              }, null, 8 /* PROPS */, ["loading"])
            ])
          ]),
          (loading.value)
            ? (_openBlock$2(), _createBlock$2(_component_VProgressLinear, {
                key: 0,
                indeterminate: "",
                color: "primary",
                class: "mb-3"
              }))
            : _createCommentVNode$2("v-if", true),
          (!rows.value.length && !loading.value)
            ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_27$1, _toDisplayString$1(pendingOnly.value ? '暂无待处理记录，可关闭筛选查看历史。' : '暂无同步删除记录'), 1 /* TEXT */))
            : _createCommentVNode$2("v-if", true),
          (_openBlock$2(true), _createElementBlock$2(_Fragment$1, null, _renderList$1(rows.value, (job) => {
            return (_openBlock$2(), _createBlock$2(_sfc_main$4, {
              key: props.pluginId + ':' + job.id,
              "data-sync-record": job.id,
              time: dateText(job.updated_at),
              name: job.event?.name || job.event?.paths?.[0] || '媒体删除',
              status: label(job.state),
              color: color(job.state)
            }, {
              default: _withCtx$1(() => [
                (job.error)
                  ? (_openBlock$2(), _createElementBlock$2("div", {
                      key: 0,
                      class: _normalizeClass(job.state === 'dismissed' ? 'text-medium-emphasis' : 'text-warning')
                    }, _toDisplayString$1(job.state === 'dismissed' ? '原失败原因：' : '') + _toDisplayString$1(job.error), 3 /* TEXT, CLASS */))
                  : _createCommentVNode$2("v-if", true),
                (job.state === 'skipped')
                  ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_28$1, _toDisplayString$1(job.plan?.skip_reason), 1 /* TEXT */))
                  : _createCommentVNode$2("v-if", true),
                _createVNode$2(SyncDeleteDetails, {
                  "data-sync-detail": job.id,
                  job: job
                }, null, 8 /* PROPS */, ["data-sync-detail", "job"]),
                (job.state === 'failed')
                  ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_29$1, [
                      (job.review?.retry_reason)
                        ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_30$1, "无法重试：" + _toDisplayString$1(job.review.retry_reason), 1 /* TEXT */))
                        : _createCommentVNode$2("v-if", true),
                      (job.review?.dismiss_reason)
                        ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_31$1, _toDisplayString$1(job.review.dismiss_reason), 1 /* TEXT */))
                        : _createCommentVNode$2("v-if", true),
                      (job.review?.dismiss_allowed)
                        ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_32, "忽略后不再提醒，历史保留。"))
                        : _createCommentVNode$2("v-if", true),
                      _createElementVNode$1("div", _hoisted_33, [
                        _createVNode$2(_component_VBtn, {
                          color: "warning",
                          variant: "tonal",
                          size: "x-small",
                          loading: retryId.value === job.id && actionKind.value === 'retry',
                          disabled: !props.canManage || !enabled.value || Boolean(retryId.value) || job.review?.retry_allowed === false,
                          onClick: $event => (requestAction('retry', job))
                        }, {
                          default: _withCtx$1(() => [...(_cache[25] || (_cache[25] = [
                            _createTextVNode$1("核验后重试", -1 /* CACHED */)
                          ]))]),
                          _: 1 /* STABLE */
                        }, 8 /* PROPS */, ["loading", "disabled", "onClick"]),
                        (job.review?.dismiss_allowed)
                          ? (_openBlock$2(), _createBlock$2(_component_VBtn, {
                              key: 0,
                              variant: "text",
                              size: "x-small",
                              loading: retryId.value === job.id && actionKind.value === 'ignore',
                              disabled: !props.canManage || Boolean(retryId.value),
                              onClick: $event => (ignore(job))
                            }, {
                              default: _withCtx$1(() => [...(_cache[26] || (_cache[26] = [
                                _createTextVNode$1("忽略", -1 /* CACHED */)
                              ]))]),
                              _: 1 /* STABLE */
                            }, 8 /* PROPS */, ["loading", "disabled", "onClick"]))
                          : _createCommentVNode$2("v-if", true)
                      ])
                    ]))
                  : _createCommentVNode$2("v-if", true)
              ]),
              _: 2 /* DYNAMIC */
            }, 1032 /* PROPS, DYNAMIC_SLOTS */, ["data-sync-record", "time", "name", "status", "color"]))
          }), 128 /* KEYED_FRAGMENT */)),
          (pages.value > 1)
            ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_34, [
                _createVNode$2(_component_VPagination, {
                  modelValue: page.value,
                  "onUpdate:modelValue": [
                    _cache[11] || (_cache[11] = $event => ((page).value = $event)),
                    load
                  ],
                  length: pages.value,
                  "total-visible": 5,
                  density: "compact"
                }, null, 8 /* PROPS */, ["modelValue", "length"]),
                _createElementVNode$1("span", _hoisted_35, "共 " + _toDisplayString$1(total.value) + " 条", 1 /* TEXT */)
              ]))
            : _createCommentVNode$2("v-if", true),
          _createVNode$2(_component_VDialog, {
            modelValue: actionDialog.value,
            "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((actionDialog).value = $event)),
            "max-width": "560",
            persistent: Boolean(retryId.value)
          }, {
            default: _withCtx$1(() => [
              _createVNode$2(_component_VCard, null, {
                default: _withCtx$1(() => [
                  _createVNode$2(_component_VCardTitle, null, {
                    default: _withCtx$1(() => [...(_cache[27] || (_cache[27] = [
                      _createTextVNode$1("确认重新执行", -1 /* CACHED */)
                    ]))]),
                    _: 1 /* STABLE */
                  }),
                  _createVNode$2(_component_VCardText, null, {
                    default: _withCtx$1(() => [
                      _createElementVNode$1("div", _hoisted_36, _toDisplayString$1(actionJob.value?.event?.name || '媒体删除'), 1 /* TEXT */),
                      _cache[28] || (_cache[28] = _createElementVNode$1("div", null, "将按这条记录原有范围重新核验，并可能继续删除文件、移除种子或清理记录。请先确认关联明细及失败原因已经处理。", -1 /* CACHED */)),
                      (actionError.value)
                        ? (_openBlock$2(), _createBlock$2(_component_VAlert, {
                            key: 0,
                            type: "warning",
                            variant: "tonal",
                            class: "mt-3"
                          }, {
                            default: _withCtx$1(() => [
                              _createTextVNode$1(_toDisplayString$1(actionError.value), 1 /* TEXT */)
                            ]),
                            _: 1 /* STABLE */
                          }))
                        : _createCommentVNode$2("v-if", true)
                    ]),
                    _: 1 /* STABLE */
                  }),
                  _createVNode$2(_component_VCardActions, null, {
                    default: _withCtx$1(() => [
                      _createVNode$2(_component_VSpacer),
                      _createVNode$2(_component_VBtn, {
                        disabled: Boolean(retryId.value),
                        onClick: _cache[12] || (_cache[12] = $event => (actionDialog.value = false))
                      }, {
                        default: _withCtx$1(() => [...(_cache[29] || (_cache[29] = [
                          _createTextVNode$1("取消", -1 /* CACHED */)
                        ]))]),
                        _: 1 /* STABLE */
                      }, 8 /* PROPS */, ["disabled"]),
                      _createVNode$2(_component_VBtn, {
                        color: "error",
                        loading: Boolean(retryId.value),
                        disabled: !props.canManage || Boolean(retryId.value),
                        onClick: confirmAction
                      }, {
                        default: _withCtx$1(() => [...(_cache[30] || (_cache[30] = [
                          _createTextVNode$1("确认重试", -1 /* CACHED */)
                        ]))]),
                        _: 1 /* STABLE */
                      }, 8 /* PROPS */, ["loading", "disabled"])
                    ]),
                    _: 1 /* STABLE */
                  })
                ]),
                _: 1 /* STABLE */
              })
            ]),
            _: 1 /* STABLE */
          }, 8 /* PROPS */, ["modelValue", "persistent"])
        ], 64 /* STABLE_FRAGMENT */))
  ], 2 /* CLASS */))
}
}

};
const SyncDeletePane = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-53f6f1b2"]]);

const {resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,createElementBlock:_createElementBlock$1} = await importShared('vue');


const _hoisted_1$1 = { class: "dm-auto-cron" };
const _hoisted_2$1 = {
  key: 0,
  class: "dm-auto-cron-time"
};

const {ref: ref$1,watch: watch$1} = await importShared('vue');


const _sfc_main$1 = {
  __name: 'AutoDeleteCron',
  props: { modelValue: { type: String, default: '' }, disabled: Boolean },
  emits: ['update:modelValue'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const preset = ref$1('custom');
const minute = ref$1(0);
const hour = ref$1(3);
const day = ref$1(0);
const choices = [{ title: '每天指定时间', value: 'daily' }, { title: '每小时', value: 'hourly' }, { title: '每周', value: 'weekly' }, { title: '自定义表达式', value: 'custom' }];
function publish() {
  if (preset.value === 'custom') return
  const min = Math.max(0, Math.min(59, Number(minute.value) || 0));
  const h = Math.max(0, Math.min(23, Number(hour.value) || 0));
  emit('update:modelValue', preset.value === 'hourly' ? `${min} * * * *` : preset.value === 'daily' ? `${min} ${h} * * *` : `${min} ${h} * * ${day.value}`);
}
watch$1(() => props.modelValue, value => {
  const fields = String(value || '').trim().split(/\s+/);
  if (fields.length !== 5 || !/^\d+$/.test(fields[0]) || fields[2] !== '*' || fields[3] !== '*') { preset.value = 'custom'; return }
  minute.value = Number(fields[0]);
  if (fields[1] === '*' && fields[4] === '*') preset.value = 'hourly';
  else if (/^\d+$/.test(fields[1])) { hour.value = Number(fields[1]); preset.value = fields[4] === '*' ? 'daily' : /^\d$/.test(fields[4]) ? 'weekly' : 'custom'; if (preset.value === 'weekly') day.value = Number(fields[4]); }
  else preset.value = 'custom';
}, { immediate: true });

return (_ctx, _cache) => {
  const _component_VSelect = _resolveComponent$1("VSelect");
  const _component_VTextField = _resolveComponent$1("VTextField");

  return (_openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
    _createVNode$1(_component_VSelect, {
      modelValue: preset.value,
      "onUpdate:modelValue": [
        _cache[0] || (_cache[0] = $event => ((preset).value = $event)),
        publish
      ],
      disabled: __props.disabled,
      items: choices,
      label: "Cron 可视化周期",
      variant: "outlined",
      density: "compact",
      "hide-details": ""
    }, null, 8 /* PROPS */, ["modelValue", "disabled"]),
    (preset.value !== 'custom')
      ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_2$1, [
          (preset.value === 'weekly')
            ? (_openBlock$1(), _createBlock$1(_component_VSelect, {
                key: 0,
                modelValue: day.value,
                "onUpdate:modelValue": [
                  _cache[1] || (_cache[1] = $event => ((day).value = $event)),
                  publish
                ],
                disabled: __props.disabled,
                items: ['周一','周二','周三','周四','周五','周六','周日'].map((title, value) => ({title,value})),
                label: "星期",
                variant: "outlined",
                density: "compact",
                "hide-details": ""
              }, null, 8 /* PROPS */, ["modelValue", "disabled", "items"]))
            : _createCommentVNode$1("v-if", true),
          (preset.value !== 'hourly')
            ? (_openBlock$1(), _createBlock$1(_component_VTextField, {
                key: 1,
                modelValue: hour.value,
                "onUpdate:modelValue": [
                  _cache[2] || (_cache[2] = $event => ((hour).value = $event)),
                  publish
                ],
                modelModifiers: { number: true },
                disabled: __props.disabled,
                type: "number",
                min: "0",
                max: "23",
                label: "时",
                variant: "outlined",
                density: "compact",
                "hide-details": ""
              }, null, 8 /* PROPS */, ["modelValue", "disabled"]))
            : _createCommentVNode$1("v-if", true),
          _createVNode$1(_component_VTextField, {
            modelValue: minute.value,
            "onUpdate:modelValue": [
              _cache[3] || (_cache[3] = $event => ((minute).value = $event)),
              publish
            ],
            modelModifiers: { number: true },
            disabled: __props.disabled,
            type: "number",
            min: "0",
            max: "59",
            label: "分",
            variant: "outlined",
            density: "compact",
            "hide-details": ""
          }, null, 8 /* PROPS */, ["modelValue", "disabled"])
        ]))
      : _createCommentVNode$1("v-if", true),
    _createVNode$1(_component_VTextField, {
      "model-value": __props.modelValue,
      disabled: __props.disabled,
      label: "Cron 表达式 · 上海时间",
      density: "compact",
      variant: "outlined",
      hint: "分 时 日 月 周；周一为 0。可直接编辑任意标准五段表达式。",
      "persistent-hint": "",
      "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => (emit('update:modelValue', $event)))
    }, null, 8 /* PROPS */, ["model-value", "disabled"])
  ]))
}
}

};
const AutoDeleteCron = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-9a67e8ca"]]);

const {toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,createBlock:_createBlock,renderList:_renderList,Fragment:_Fragment,unref:_unref} = await importShared('vue');


const _hoisted_1 = { class: "dm-auto-delete" };
const _hoisted_2 = {
  key: 0,
  class: "dm-auto-toolbar"
};
const _hoisted_3 = {
  key: 1,
  class: "text-caption text-medium-emphasis my-3"
};
const _hoisted_4 = {
  key: 3,
  class: "text-caption text-medium-emphasis mb-3"
};
const _hoisted_5 = {
  key: 0,
  "data-config-section": "basic"
};
const _hoisted_6 = {
  key: 1,
  "data-config-section": "advanced"
};
const _hoisted_7 = { class: "dm-auto-toolbar mt-3" };
const _hoisted_8 = {
  key: 2,
  "data-config-section": "filter"
};
const _hoisted_9 = { class: "dm-auto-toolbar mb-2" };
const _hoisted_10 = { class: "dm-auto-toolbar mt-3" };
const _hoisted_11 = {
  key: 1,
  class: "text-caption text-medium-emphasis mt-3"
};
const _hoisted_12 = {
  key: 3,
  class: "dm-auto-toolbar my-3"
};
const _hoisted_13 = {
  key: 1,
  class: "text-caption"
};
const _hoisted_14 = { key: 4 };
const _hoisted_15 = { class: "text-caption" };
const _hoisted_16 = {
  key: 0,
  class: "text-caption text-warning"
};
const _hoisted_17 = {
  key: 1,
  class: "text-caption text-warning"
};
const _hoisted_18 = {
  key: 8,
  "data-execution-history": "",
  class: "dm-history-surface"
};
const _hoisted_19 = { class: "dm-history-toolbar mt-4" };
const _hoisted_20 = { class: "dm-history-title" };
const _hoisted_21 = { class: "dm-history-count" };
const _hoisted_22 = { class: "dm-history-tools" };
const _hoisted_23 = {
  key: 1,
  class: "dm-history-empty"
};
const _hoisted_24 = { key: 2 };
const _hoisted_25 = {
  key: 0,
  class: "text-error"
};
const _hoisted_26 = { class: "dm-history-actions" };
const _hoisted_27 = {
  key: 3,
  class: "dm-history-pagination"
};
const _hoisted_28 = { class: "dm-history-count" };
const _hoisted_29 = { class: "text-caption ml-8 mb-2" };
const _hoisted_30 = { class: "text-caption mt-3" };
const _hoisted_31 = { class: "text-caption" };
const {ref,computed,watch,nextTick,onBeforeUnmount} = await importShared('vue');

const sourcePathMessage = '请填写「允许删除的下载目录」。选择删除下载数据时，至少需要一个 MP 容器内的下载目录。';
const ruleIdMessage = '无法生成规则编号，未添加规则';

const _sfc_main = {
  __name: 'AutoDeletePane',
  props: {
  api: { type: [Object, Function], default: null }, pluginId: { type: String, required: true }, canManage: Boolean,
  mode: { type: String, default: 'history' }, section: { type: String, default: 'basic' },
  active: { type: Boolean, default: true },
  downloaderRequest: { type: Object, default: null },
},
  emits: ['saved', 'show-advanced'],
  setup(__props, { expose: __expose, emit: __emit }) {

const props = __props;
const emit = __emit;
const confirmationHeading = ref(null);
async function showRuleConfirmation() {
  emit('show-advanced');
  await nextTick();
  confirmationHeading.value?.focus?.();
}
const settings = ref(null);
const revision = ref(0);
const saved = ref('');
const downloaders = ref([]);
const downloadersReady = ref(false);
const status = ref({});
const records = ref([]);
const total = ref(0);
const page = ref(1);
const filterState = ref('');
const filterRule = ref('');
const filterDownloader = ref('');
const previewResult = ref(null);
const busy = ref('');
const message = ref('');
const error = ref('');
const confirmRule = ref(null);
const confirmJobs = ref([]);
const confirmPage = ref(1);
const confirmTotal = ref(0);
const confirmEvidence = ref({});
const selectedJobs = ref([]);
const acceptHistory = ref(false);
const detail = ref(null);
const historyLoading = ref(false);
let context = 0;
let loadRevision = 0;
let disposed = false;
let timer = null;
let polling = false;
const dirty = computed(() => settings.value && JSON.stringify(settings.value) !== saved.value);
const needsSourcePaths = computed(() => settings.value?.rules.some(rule => rule.enabled && rule.action === 'data'));
const missingSourcePaths = computed(() => needsSourcePaths.value && !settings.value.source_paths.length);
const regexFields = [
  ['name_include', '种子名称包含正则'], ['name_exclude', '种子名称排除正则'],
  ['path_include', '保存路径包含正则'], ['path_exclude', '保存路径排除正则'],
  ['tracker_include', 'Tracker 包含正则'], ['tracker_exclude', 'Tracker 排除正则'],
  ['tracker_error', 'Tracker 状态/报错正则'], ['category', '分类正则'],
  ['tag_include', '标签包含正则'], ['tag_exclude', '标签排除正则'],
];
const numberFields = [['ratio_min', '最小分享率'], ['ratio_max', '最大分享率'], ['seed_hours_min', '最少做种小时'],
  ['added_hours_min', '最少添加小时'], ['size_gib_min', '最小体积 GiB'], ['size_gib_max', '最大体积 GiB'], ['upload_kib_max', '最大上传 KiB/s']];
const stateItems = [{ title: '全部结果', value: '' }, { title: '已暂停', value: 'paused' }, { title: '等待正式处理', value: 'approved' },
  { title: '待复核', value: 'review' }, { title: '已移除种子', value: 'removed' }, { title: '已删除种子及数据', value: 'deleted' }, { title: '已解除保护', value: 'released' }];
const pages = computed(() => Math.max(1, Math.ceil(total.value / 15)));
const protectedStates = new Set(['paused', 'review', 'approved']);
const getApi = path => getPluginApi(props.api, props.pluginId, path, { feedback: 'silent' });
const postApi = (path, body = {}) => postPluginJsonApi(props.api, props.pluginId, path, body, { feedback: 'silent' });
function copy(value) { return JSON.parse(JSON.stringify(value)) }
function timeText(value) { return value ? new Date(value * 1000).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '暂无记录' }
function stateText(value) { return stateItems.find(item => item.value === value)?.title || ({ prepared: '准备中', removing: '移除中', deleting: '删除文件中', absent: '原任务已不存在' })[value] || value }
function recordColor(value) { return value === 'review' ? 'warning' : ['removed', 'deleted', 'released', 'absent'].includes(value) ? 'success' : 'info' }
function owns(revisionAtStart) { return !disposed && revisionAtStart === context }
function formatError(reason) {
  const payload = reason?.payload ?? reason?.response?.data;
  const issues = Array.isArray(payload?.data) ? payload.data : payload?.detail;
  if (Array.isArray(issues)) {
    const messages = issues.map(issue => {
      const message = issue?.message || issue?.msg;
      if (!message) return ''
      const path = (issue.location || issue.loc || []).filter(part => !['body', 'settings'].includes(part)).join('.');
      const detail = message.replace(/^Value error,\s*/i, '');
      return path ? `${path}：${detail}` : detail
    }).filter(Boolean);
    if (messages.length) return messages.join('；')
  }
  return (typeof issues === 'string' && issues) || payload?.message || reason?.message || '请求失败'
}

async function load({ all = false } = {}) {
  const current = context;
  const request = ++loadRevision;
  if (props.mode === 'history') historyLoading.value = true;
  const query = new URLSearchParams({ page: String(page.value), page_size: '15', state: filterState.value, rule_id: filterRule.value, downloader: filterDownloader.value });
  const tasks = [getApi('auto_delete/status').then(value => {
    if (owns(current) && request === loadRevision) status.value = value;
  })];
  if (props.mode === 'history') tasks.push(getApi(`auto_delete/history?${query}`).then(value => {
    if (!owns(current) || request !== loadRevision) return
    records.value = value.items || [];
    total.value = value.total || 0;
  }));
  if (all) {
    tasks.push(getApi('auto_delete/config').then(value => {
      if (!owns(current) || dirty.value || request !== loadRevision && settings.value) return
      settings.value = copy(value.settings);
      saved.value = JSON.stringify(settings.value);
      revision.value = value.revision;
    }));
    tasks.push((props.downloaderRequest || getApi('downloaders')).then(value => {
      if (owns(current)) {
        downloaders.value = (value || []).filter(item => ['qbittorrent', 'transmission'].includes(item.type));
        downloadersReady.value = true;
      }
    }));
  }
  const results = await Promise.allSettled(tasks);
  if (!owns(current) || request !== loadRevision) return
  const failed = results.find(item => item.status === 'rejected' && !isApiRequestCancellation(item.reason));
  if (failed) error.value = formatError(failed.reason);
  historyLoading.value = false;
}

async function action(name, callback) {
  if (busy.value || !props.canManage) return false
  const current = context;
  busy.value = name;
  error.value = '';
  message.value = '';
  try {
    await callback(current);
    if (owns(current)) await load();
    return owns(current)
  } catch (reason) {
    if (owns(current) && !isApiRequestCancellation(reason)) {
      error.value = formatError(reason);
      if (reason?.payload?.data?.items?.length) await load();
    }
    return false
  } finally { if (owns(current)) busy.value = ''; }
}

function createRuleId() {
  const usedIds = new Set(settings.value.rules.map(rule => rule.id));
  const bytes = new Uint8Array(16);
  for (let attempt = 0; attempt < 5; attempt++) {
    try { globalThis.crypto.getRandomValues(bytes); } catch { return null }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const id = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
    if (!usedIds.has(id)) return id
  }
  return null
}
function appendRule(makeRule) {
  const id = createRuleId();
  if (!id) { error.value = ruleIdMessage; return }
  settings.value.rules.push(makeRule(id));
  if (error.value === ruleIdMessage) error.value = '';
}
function newRule(id) {
  return { id, name: '新规则', revision: 1, enabled: false, mode: 'debug', action: 'torrent',
    downloaders: [], ignore_case: true, consecutive: 2, conditions: Object.fromEntries([...regexFields.map(([key]) => [key, '']), ...numberFields.map(([key]) => [key, null])]) }
}
function addRule() { appendRule(newRule); }
function duplicate(rule) {
  appendRule(id => ({ ...copy(rule), id, name: `${rule.name} 副本`, revision: 1, mode: 'debug', enabled: false }));
}
function numberValue(rule, key, value) {
  rule.conditions[key] = value === '' || value === null ? null : Number(value);
}
function setPaths(key, value) { settings.value[key] = String(value || '').split('\n').map(item => item.trim()).filter(Boolean); }
function checkedDraft() {
  if (missingSourcePaths.value) throw new Error(sourcePathMessage)
  for (const rule of settings.value.rules) {
    for (const [key, label] of numberFields) {
      const value = rule.conditions[key];
      if (value !== null && value !== undefined && (!Number.isFinite(value) || value < 0)) throw new Error(`${rule.name}：${label} 必须是非负数或留空`)
    }
  }
  return copy(settings.value)
}
function publishSettings(response) {
  settings.value = copy(response.settings);
  revision.value = response.revision;
  saved.value = JSON.stringify(settings.value);
  emit('saved', { ...Object.fromEntries(Object.entries(settings.value).map(([key, value]) => ['auto_delete_' + key, copy(value)])), auto_delete_config_revision: response.revision });
}
async function save() {
  const expected = revision.value;
  return action('save', async current => {
    const draft = checkedDraft();
    const response = await postApi('auto_delete/config', { expected_revision: expected, settings: draft });
    if (!owns(current)) return
    if (JSON.stringify(settings.value) === JSON.stringify(draft)) publishSettings(response);
    else {
      revision.value = response.revision;
      saved.value = JSON.stringify(response.settings);
      emit('saved', { ...Object.fromEntries(Object.entries(response.settings).map(([key, value]) => ['auto_delete_' + key, copy(value)])), auto_delete_config_revision: response.revision });
    }
    previewResult.value = null;
    message.value = '设置已保存。修改关键条件后，相关规则自动回到暂停调试。';
  })
}
async function preview() {
  await action('preview', async current => {
    const draft = checkedDraft();
    const response = await postApi('auto_delete/preview', { settings: draft });
    if (owns(current) && JSON.stringify(settings.value) === JSON.stringify(draft)) previewResult.value = response;
  });
}
async function run() { await action('run', async current => { const response = await postApi('auto_delete/run'); if (owns(current)) message.value = response.message || '扫描已受理，请查看执行记录。'; }); }
async function stop() { await action('stop', async current => { const response = await postApi('auto_delete/stop'); if (owns(current)) { publishSettings(response); message.value = '自动删除已停止，原有暂停保护继续保留。'; } }); }
async function beginConfirm(rule) {
  if (dirty.value) { error.value = '请先保存规则，再确认当前生效配置。'; return }
  await action('confirm-load', async current => {
    const response = await getApi(`auto_delete/history?page=1&page_size=100&state=paused,review&rule_id=${encodeURIComponent(rule.id)}`);
    if (!owns(current)) return
    confirmRule.value = rule;
    confirmPage.value = 1;
    confirmTotal.value = response.total || 0;
    confirmJobs.value = (response.items || []).filter(item => ['paused', 'approved'].includes(item.stage) && !item.interfered && !item.files?.some(file => file.deleted));
    confirmEvidence.value = Object.fromEntries(confirmJobs.value.map(item => [item.id, item.evidence_fingerprint]));
    selectedJobs.value = [];
    acceptHistory.value = false;
  });
}
async function loadConfirmPage(value) {
  confirmPage.value = value;
  const ruleId = confirmRule.value?.id;
  if (!ruleId) return
  await action('confirm-load', async current => {
    const response = await getApi(`auto_delete/history?page=${value}&page_size=100&state=paused,review&rule_id=${encodeURIComponent(ruleId)}`);
    if (!owns(current) || confirmRule.value?.id !== ruleId || confirmPage.value !== value) return
    confirmTotal.value = response.total || 0;
    confirmJobs.value = (response.items || []).filter(item => ['paused', 'approved'].includes(item.stage) && !item.interfered && !item.files?.some(file => file.deleted));
    confirmEvidence.value = { ...confirmEvidence.value, ...Object.fromEntries(confirmJobs.value.map(item => [item.id, item.evidence_fingerprint])) };
  });
}
async function activate() {
  const body = { expected_revision: revision.value, rule_id: confirmRule.value.id, job_ids: [...selectedJobs.value],
    evidence_versions: Object.fromEntries(selectedJobs.value.map(id => [id, confirmEvidence.value[id]])),
    accept_history: acceptHistory.value };
  await action('activate', async current => {
    const response = await postApi('auto_delete/activate', body);
    if (owns(current)) { publishSettings(response); confirmRule.value = null; message.value = '规则正式启用。所选暂停任务等下一轮或手动运行处理。'; }
  });
}
async function release(record, restore) {
  await action('release', async current => {
    await postApi('auto_delete/release', { job_ids: [record.id], restore });
    if (owns(current)) message.value = restore ? '已按原运行状态处理恢复；原本暂停的任务保持暂停。' : '已解除本任务保护，任务继续保持原状态。';
  });
}
watch(() => [props.pluginId, props.api, props.mode], async () => {
  context++;
  status.value = {};
  downloaders.value = [];
  downloadersReady.value = false;
  settings.value = null;
  previewResult.value = null;
  error.value = '';
  busy.value = '';
  confirmRule.value = null;
  detail.value = null;
  records.value = [];
  total.value = 0;
  page.value = 1;
  filterState.value = '';
  filterRule.value = '';
  filterDownloader.value = '';
  await load({ all: true });
}, { immediate: true });
watch(() => [filterState.value, filterRule.value, filterDownloader.value], () => {
  if (props.mode !== 'history') return
  if (page.value !== 1) page.value = 1;
  else load();
});
watch(page, () => { if (props.mode === 'history') load(); });
watch(() => props.active, active => { if (!active) { confirmRule.value = null; detail.value = null; } });
watch(settings, () => {
  previewResult.value = null;
  if (error.value === sourcePathMessage && !missingSourcePaths.value) error.value = '';
}, { deep: true });
timer = setInterval(async () => {
  if (disposed || !props.active || busy.value || polling || document.visibilityState !== 'visible') return
  polling = true;
  try { await load(); } finally { polling = false; }
}, 30000);
onBeforeUnmount(() => { disposed = true; context++; clearInterval(timer); });
__expose({ refresh: () => load(), save, dirty, busy, error, missingSourcePaths });

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VExpansionPanelTitle = _resolveComponent("VExpansionPanelTitle");
  const _component_VExpansionPanelText = _resolveComponent("VExpansionPanelText");
  const _component_VExpansionPanel = _resolveComponent("VExpansionPanel");
  const _component_VExpansionPanels = _resolveComponent("VExpansionPanels");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VPagination = _resolveComponent("VPagination");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCheckbox = _resolveComponent("VCheckbox");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createElementBlock("section", _hoisted_1, [
    (__props.mode === 'history' || __props.section === 'basic')
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _createElementVNode("strong", null, "自动删除 · " + _toDisplayString(status.value.debug_rules || 0) + " 条调试 / " + _toDisplayString(status.value.delete_rules || 0) + " 条正式规则", 1 /* TEXT */),
          _createVNode(_component_VBtn, {
            size: "small",
            variant: "text",
            "prepend-icon": "mdi-refresh",
            onClick: _cache[0] || (_cache[0] = $event => (load()))
          }, {
            default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
              _createTextVNode("刷新", -1 /* CACHED */)
            ]))]),
            _: 1 /* STABLE */
          }),
          _createVNode(_component_VBtn, {
            disabled: !__props.canManage || !status.value.active || Boolean(busy.value) || dirty.value,
            size: "small",
            color: "primary",
            variant: "tonal",
            onClick: run
          }, {
            default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
              _createTextVNode("立即运行一次", -1 /* CACHED */)
            ]))]),
            _: 1 /* STABLE */
          }, 8 /* PROPS */, ["disabled"]),
          _createVNode(_component_VBtn, {
            disabled: !__props.canManage || !status.value.enabled || Boolean(busy.value),
            size: "small",
            color: "warning",
            onClick: stop
          }, {
            default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
              _createTextVNode("一键停止", -1 /* CACHED */)
            ]))]),
            _: 1 /* STABLE */
          }, 8 /* PROPS */, ["disabled"])
        ]))
      : _createCommentVNode("v-if", true),
    (__props.mode === 'history' || __props.section === 'basic')
      ? (_openBlock(), _createElementBlock("div", _hoisted_3, "最近扫描 " + _toDisplayString(timeText(status.value.last_scan)) + " · 下次运行 " + _toDisplayString(timeText(status.value.next_run)) + " · 保护 " + _toDisplayString(status.value.protected || 0) + " · 待复核 " + _toDisplayString(status.value.pending || 0), 1 /* TEXT */))
      : _createCommentVNode("v-if", true),
    (['running','accepted'].includes(status.value.state) || status.value.once_pending)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 2,
          type: "info",
          density: "compact",
          variant: "tonal",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode("扫描" + _toDisplayString(status.value.once_pending ? '等待执行' : '正在进行') + " · " + _toDisplayString(status.value.stage) + " · 任务 " + _toDisplayString(status.value.run_id), 1 /* TEXT */)
          ]),
          _: 1 /* STABLE */
        }))
      : _createCommentVNode("v-if", true),
    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(status.value.errors || [], (item) => {
      return (_openBlock(), _createBlock(_component_VAlert, {
        key: item,
        type: "warning",
        density: "compact",
        variant: "tonal",
        class: "mb-2"
      }, {
        default: _withCtx(() => [
          _createTextVNode(_toDisplayString(item), 1 /* TEXT */)
        ]),
        _: 2 /* DYNAMIC */
      }, 1024 /* DYNAMIC_SLOTS */))
    }), 128 /* KEYED_FRAGMENT */)),
    ((__props.mode === 'history' || __props.section === 'advanced') && Object.keys(status.value.capabilities || {}).length)
      ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(status.value.capabilities, (capability, name) => {
            return (_openBlock(), _createElementBlock("div", { key: name }, _toDisplayString(name) + " · 做种时间 " + _toDisplayString(capability.seed_seconds === null ? '尚未确认' : capability.seed_seconds ? '可用' : '部分缺失') + " · 分类 " + _toDisplayString(capability.category === null ? '尚未确认' : capability.category ? '可用' : '不可用或部分缺失') + " · Tracker " + _toDisplayString(capability.trackers === null ? '尚未查询' : capability.trackers ? '可用' : '不可用或部分缺失'), 1 /* TEXT */))
          }), 128 /* KEYED_FRAGMENT */))
        ]))
      : _createCommentVNode("v-if", true),
    (error.value || status.value.error)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 4,
          type: "error",
          variant: "tonal",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(error.value || status.value.error), 1 /* TEXT */)
          ]),
          _: 1 /* STABLE */
        }))
      : _createCommentVNode("v-if", true),
    (message.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 5,
          type: "info",
          variant: "tonal",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(message.value), 1 /* TEXT */)
          ]),
          _: 1 /* STABLE */
        }))
      : _createCommentVNode("v-if", true),
    (!settings.value && !error.value)
      ? (_openBlock(), _createBlock(_component_VProgressLinear, {
          key: 6,
          color: "primary",
          indeterminate: "",
          class: "mb-3"
        }))
      : _createCommentVNode("v-if", true),
    (__props.mode === 'config' && settings.value)
      ? (_openBlock(), _createElementBlock(_Fragment, { key: 7 }, [
          (__props.section === 'basic')
            ? (_openBlock(), _createElementBlock("section", _hoisted_5, [
                _cache[26] || (_cache[26] = _createElementVNode("h3", { class: "dm-auto-section-title" }, "基础设置", -1 /* CACHED */)),
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-3",
                  title: "从暂停调试转为正式删种"
                }, {
                  default: _withCtx(() => [
                    _cache[25] || (_cache[25] = _createTextVNode(" 保存规则并成功完成一次调试扫描后，到「高级选项 → 规则处置与确认」，展开规则，点「确认并正式启用」。 ", -1 /* CACHED */)),
                    _createVNode(_component_VBtn, {
                      size: "small",
                      variant: "tonal",
                      color: "primary",
                      class: "mt-2 d-flex",
                      onClick: showRuleConfirmation
                    }, {
                      default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                        _createTextVNode("前往规则处置与确认", -1 /* CACHED */)
                      ]))]),
                      _: 1 /* STABLE */
                    })
                  ]),
                  _: 1 /* STABLE */
                }),
                _cache[27] || (_cache[27] = _createElementVNode("p", { class: "text-caption text-medium-emphasis mb-3" }, "调试与正式共用扫描周期。手动运行保留原定时，执行记录可在详情页查看。", -1 /* CACHED */)),
                _createVNode(_component_VRow, { class: "dm-form-grid" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6",
                      class: "dm-form-field"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: settings.value.enabled,
                          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((settings.value.enabled) = $event)),
                          disabled: !__props.canManage,
                          label: "启用自动删除模块",
                          "hide-details": "",
                          color: "success",
                          inset: ""
                        }, null, 8 /* PROPS */, ["modelValue", "disabled"])
                      ]),
                      _: 1 /* STABLE */
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6",
                      class: "dm-form-field"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSwitch, {
                          modelValue: settings.value.notify,
                          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((settings.value.notify) = $event)),
                          disabled: !__props.canManage,
                          label: "发送结果通知",
                          "hide-details": "",
                          color: "info",
                          inset: ""
                        }, null, 8 /* PROPS */, ["modelValue", "disabled"])
                      ]),
                      _: 1 /* STABLE */
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6",
                      class: "dm-form-field"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VSelect, {
                          modelValue: settings.value.schedule_type,
                          "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((settings.value.schedule_type) = $event)),
                          disabled: !__props.canManage,
                          label: "运行方式",
                          items: [{title:'固定间隔',value:'interval'},{title:'Cron 定时',value:'cron'}],
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8 /* PROPS */, ["modelValue", "disabled"])
                      ]),
                      _: 1 /* STABLE */
                    }),
                    (settings.value.schedule_type === 'interval')
                      ? (_openBlock(), _createBlock(_component_VCol, {
                          key: 0,
                          cols: "12",
                          md: "6",
                          class: "dm-form-field"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VTextField, {
                              modelValue: settings.value.interval_minutes,
                              "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((settings.value.interval_minutes) = $event)),
                              modelModifiers: { number: true },
                              disabled: !__props.canManage,
                              label: "扫描间隔（分钟）",
                              type: "number",
                              min: "1",
                              density: "compact",
                              variant: "outlined",
                              "hide-details": ""
                            }, null, 8 /* PROPS */, ["modelValue", "disabled"])
                          ]),
                          _: 1 /* STABLE */
                        }))
                      : (_openBlock(), _createBlock(_component_VCol, {
                          key: 1,
                          cols: "12",
                          md: "6",
                          class: "dm-form-field"
                        }, {
                          default: _withCtx(() => [
                            _createVNode(AutoDeleteCron, {
                              modelValue: settings.value.cron,
                              "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((settings.value.cron) = $event)),
                              disabled: !__props.canManage
                            }, null, 8 /* PROPS */, ["modelValue", "disabled"])
                          ]),
                          _: 1 /* STABLE */
                        }))
                  ]),
                  _: 1 /* STABLE */
                })
              ]))
            : _createCommentVNode("v-if", true),
          (__props.section === 'advanced')
            ? (_openBlock(), _createElementBlock("section", _hoisted_6, [
                _cache[32] || (_cache[32] = _createElementVNode("h3", { class: "dm-auto-section-title" }, "高级选项", -1 /* CACHED */)),
                _createVNode(_component_VRow, { class: "dm-form-grid" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6",
                      class: "dm-form-field"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: settings.value.max_tasks,
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((settings.value.max_tasks) = $event)),
                          modelModifiers: { number: true },
                          disabled: !__props.canManage,
                          label: "每轮最多处置任务",
                          type: "number",
                          min: "1",
                          max: "1000",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8 /* PROPS */, ["modelValue", "disabled"])
                      ]),
                      _: 1 /* STABLE */
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6",
                      class: "dm-form-field"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: settings.value.sample_minutes,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((settings.value.sample_minutes) = $event)),
                          modelModifiers: { number: true },
                          disabled: !__props.canManage || settings.value.schedule_type === 'interval',
                          label: "Cron 有效采样间隔（分钟）",
                          type: "number",
                          min: "1",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8 /* PROPS */, ["modelValue", "disabled"])
                      ]),
                      _: 1 /* STABLE */
                    })
                  ]),
                  _: 1 /* STABLE */
                }),
                _cache[33] || (_cache[33] = _createElementVNode("p", { class: "text-caption text-medium-emphasis mt-2" }, "固定间隔模式跟随扫描间隔；手动连点不会增加有效采样次数。", -1 /* CACHED */)),
                _createElementVNode("h3", {
                  ref_key: "confirmationHeading",
                  ref: confirmationHeading,
                  tabindex: "-1",
                  class: "dm-auto-section-title mt-4"
                }, "规则处置与确认", 512 /* NEED_PATCH */),
                (!settings.value.rules.length)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "info",
                      variant: "tonal",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
                        _createTextVNode("请先在条件筛选中添加规则。", -1 /* CACHED */)
                      ]))]),
                      _: 1 /* STABLE */
                    }))
                  : _createCommentVNode("v-if", true),
                _createVNode(_component_VExpansionPanels, { multiple: "" }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(settings.value.rules, (rule) => {
                      return (_openBlock(), _createBlock(_component_VExpansionPanel, {
                        key: rule.id
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VExpansionPanelTitle, null, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(rule.name) + " ", 1 /* TEXT */),
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                class: "ml-2",
                                color: rule.mode === 'delete' ? 'warning' : 'info'
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(rule.enabled ? rule.mode === 'delete' ? '正式删种' : '暂停调试' : '停用'), 1 /* TEXT */)
                                ]),
                                _: 2 /* DYNAMIC */
                              }, 1032 /* PROPS, DYNAMIC_SLOTS */, ["color"])
                            ]),
                            _: 2 /* DYNAMIC */
                          }, 1024 /* DYNAMIC_SLOTS */),
                          _createVNode(_component_VExpansionPanelText, null, {
                            default: _withCtx(() => [
                              _createVNode(_component_VRow, { class: "dm-form-grid" }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VCol, {
                                    cols: "12",
                                    md: "6",
                                    class: "dm-form-field"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VSelect, {
                                        modelValue: rule.action,
                                        "onUpdate:modelValue": $event => ((rule.action) = $event),
                                        disabled: !__props.canManage,
                                        label: "正式删除动作",
                                        items: [{title:'仅删种，保留数据',value:'torrent'},{title:'删除种子及下载数据',value:'data'}],
                                        density: "compact",
                                        variant: "outlined",
                                        "error-messages": rule.enabled && rule.action === 'data' && missingSourcePaths.value ? '请在下方「删除数据范围」填写允许目录' : '',
                                        "hide-details": "auto"
                                      }, null, 8 /* PROPS */, ["modelValue", "onUpdate:modelValue", "disabled", "error-messages"])
                                    ]),
                                    _: 2 /* DYNAMIC */
                                  }, 1024 /* DYNAMIC_SLOTS */),
                                  _createVNode(_component_VCol, {
                                    cols: "12",
                                    md: "6",
                                    class: "dm-form-field"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VTextField, {
                                        modelValue: rule.consecutive,
                                        "onUpdate:modelValue": $event => ((rule.consecutive) = $event),
                                        modelModifiers: { number: true },
                                        disabled: !__props.canManage,
                                        label: "连续有效采样次数",
                                        type: "number",
                                        min: "1",
                                        max: "20",
                                        density: "compact",
                                        variant: "outlined",
                                        "hide-details": ""
                                      }, null, 8 /* PROPS */, ["modelValue", "onUpdate:modelValue", "disabled"])
                                    ]),
                                    _: 2 /* DYNAMIC */
                                  }, 1024 /* DYNAMIC_SLOTS */)
                                ]),
                                _: 2 /* DYNAMIC */
                              }, 1024 /* DYNAMIC_SLOTS */),
                              _cache[30] || (_cache[30] = _createElementVNode("p", { class: "text-caption text-medium-emphasis mt-2" }, "上传低速和 Tracker 故障按有效采样次数判定。先保存并检查详情页中的暂停前依据，再确认正式启用。", -1 /* CACHED */)),
                              _createElementVNode("div", _hoisted_7, [
                                (rule.mode === 'delete')
                                  ? (_openBlock(), _createBlock(_component_VBtn, {
                                      key: 0,
                                      disabled: !__props.canManage || Boolean(busy.value),
                                      color: "info",
                                      variant: "tonal",
                                      size: "small",
                                      onClick: $event => (rule.mode = 'debug')
                                    }, {
                                      default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                                        _createTextVNode("切回暂停调试 · 保存后生效", -1 /* CACHED */)
                                      ]))]),
                                      _: 1 /* STABLE */
                                    }, 8 /* PROPS */, ["disabled", "onClick"]))
                                  : _createCommentVNode("v-if", true),
                                _createVNode(_component_VBtn, {
                                  disabled: !__props.canManage || !rule.enabled || dirty.value || Boolean(busy.value),
                                  color: "warning",
                                  variant: "tonal",
                                  size: "small",
                                  onClick: $event => (beginConfirm(rule))
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(rule.mode === 'delete' ? '确认暂停清单' : '确认并正式启用'), 1 /* TEXT */)
                                  ]),
                                  _: 2 /* DYNAMIC */
                                }, 1032 /* PROPS, DYNAMIC_SLOTS */, ["disabled", "onClick"])
                              ])
                            ]),
                            _: 2 /* DYNAMIC */
                          }, 1024 /* DYNAMIC_SLOTS */)
                        ]),
                        _: 2 /* DYNAMIC */
                      }, 1024 /* DYNAMIC_SLOTS */))
                    }), 128 /* KEYED_FRAGMENT */))
                  ]),
                  _: 1 /* STABLE */
                }),
                _cache[34] || (_cache[34] = _createElementVNode("h3", { class: "dm-auto-section-title mt-4" }, "删除数据范围", -1 /* CACHED */)),
                _createVNode(_component_VAlert, {
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-3"
                }, {
                  default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                    _createTextVNode("只有选择“删除种子及下载数据”的规则会删除文件。允许目录、路径映射或规则关键条件变化后，需要重新调试确认。", -1 /* CACHED */)
                  ]))]),
                  _: 1 /* STABLE */
                }),
                _createVNode(_component_VRow, { class: "dm-form-grid" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6",
                      class: "dm-form-field"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          "model-value": settings.value.source_paths.join('\n'),
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => (setPaths('source_paths', $event))),
                          disabled: !__props.canManage,
                          label: "允许删除的下载目录",
                          required: needsSourcePaths.value,
                          "error-messages": missingSourcePaths.value ? sourcePathMessage : '',
                          rows: "3",
                          "auto-grow": "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "auto"
                        }, null, 8 /* PROPS */, ["model-value", "disabled", "required", "error-messages"])
                      ]),
                      _: 1 /* STABLE */
                    }),
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6",
                      class: "dm-form-field"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextarea, {
                          "model-value": settings.value.exclude_paths.join('\n'),
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => (setPaths('exclude_paths', $event))),
                          disabled: !__props.canManage,
                          label: "保护目录",
                          rows: "3",
                          "auto-grow": "",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8 /* PROPS */, ["model-value", "disabled"])
                      ]),
                      _: 1 /* STABLE */
                    })
                  ]),
                  _: 1 /* STABLE */
                }),
                _cache[35] || (_cache[35] = _createElementVNode("p", { class: "text-caption text-medium-emphasis mt-2" }, "一行一个 MP 容器内绝对目录；删除数据时必须配置允许目录。", -1 /* CACHED */)),
                _cache[36] || (_cache[36] = _createElementVNode("h3", { class: "dm-auto-section-title mt-4" }, "历史保留", -1 /* CACHED */)),
                _createVNode(_component_VRow, { class: "dm-form-grid dm-form-grid--single-number" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VCol, {
                      cols: "12",
                      md: "6",
                      class: "dm-form-field"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VTextField, {
                          modelValue: settings.value.history_days,
                          "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((settings.value.history_days) = $event)),
                          modelModifiers: { number: true },
                          disabled: !__props.canManage,
                          label: "已结束记录保留天数",
                          type: "number",
                          min: "1",
                          density: "compact",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8 /* PROPS */, ["modelValue", "disabled"])
                      ]),
                      _: 1 /* STABLE */
                    })
                  ]),
                  _: 1 /* STABLE */
                }),
                _cache[37] || (_cache[37] = _createElementVNode("p", { class: "text-caption text-medium-emphasis mt-2" }, "待复核记录与活动保护不按日期清除；执行记录只在详情页显示。", -1 /* CACHED */))
              ]))
            : _createCommentVNode("v-if", true),
          (__props.section === 'filter')
            ? (_openBlock(), _createElementBlock("section", _hoisted_8, [
                _createElementVNode("div", _hoisted_9, [
                  _cache[39] || (_cache[39] = _createElementVNode("strong", null, "自动删种规则", -1 /* CACHED */)),
                  _createVNode(_component_VBtn, {
                    disabled: !__props.canManage,
                    size: "small",
                    "prepend-icon": "mdi-plus",
                    onClick: addRule
                  }, {
                    default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                      _createTextVNode("添加规则", -1 /* CACHED */)
                    ]))]),
                    _: 1 /* STABLE */
                  }, 8 /* PROPS */, ["disabled"])
                ]),
                (!settings.value.rules.length)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "info",
                      variant: "tonal",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [...(_cache[40] || (_cache[40] = [
                        _createTextVNode("尚未创建规则。新增规则默认停用、暂停调试。", -1 /* CACHED */)
                      ]))]),
                      _: 1 /* STABLE */
                    }))
                  : _createCommentVNode("v-if", true),
                _createVNode(_component_VExpansionPanels, { multiple: "" }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(settings.value.rules, (rule, index) => {
                      return (_openBlock(), _createBlock(_component_VExpansionPanel, {
                        key: rule.id
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VExpansionPanelTitle, null, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(rule.name) + " ", 1 /* TEXT */),
                              _createVNode(_component_VChip, {
                                size: "x-small",
                                class: "ml-2",
                                color: rule.mode === 'delete' ? 'warning' : 'info'
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(rule.enabled ? rule.mode === 'delete' ? '正式删种' : '暂停调试' : '停用'), 1 /* TEXT */)
                                ]),
                                _: 2 /* DYNAMIC */
                              }, 1032 /* PROPS, DYNAMIC_SLOTS */, ["color"])
                            ]),
                            _: 2 /* DYNAMIC */
                          }, 1024 /* DYNAMIC_SLOTS */),
                          _createVNode(_component_VExpansionPanelText, null, {
                            default: _withCtx(() => [
                              _createVNode(_component_VRow, { class: "dm-form-grid dm-form-grid--three" }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VCol, {
                                    cols: "12",
                                    md: "8",
                                    class: "dm-form-field dm-form-field--wide"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VTextField, {
                                        modelValue: rule.name,
                                        "onUpdate:modelValue": $event => ((rule.name) = $event),
                                        disabled: !__props.canManage,
                                        label: "规则名称",
                                        density: "compact",
                                        variant: "outlined",
                                        "hide-details": ""
                                      }, null, 8 /* PROPS */, ["modelValue", "onUpdate:modelValue", "disabled"])
                                    ]),
                                    _: 2 /* DYNAMIC */
                                  }, 1024 /* DYNAMIC_SLOTS */),
                                  _createVNode(_component_VCol, {
                                    cols: "12",
                                    md: "4",
                                    class: "dm-form-field"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VSwitch, {
                                        modelValue: rule.enabled,
                                        "onUpdate:modelValue": $event => ((rule.enabled) = $event),
                                        disabled: !__props.canManage,
                                        label: "启用规则",
                                        "hide-details": "",
                                        color: "success",
                                        inset: ""
                                      }, null, 8 /* PROPS */, ["modelValue", "onUpdate:modelValue", "disabled"])
                                    ]),
                                    _: 2 /* DYNAMIC */
                                  }, 1024 /* DYNAMIC_SLOTS */),
                                  _createVNode(_component_VCol, {
                                    cols: "12",
                                    md: "8",
                                    class: "dm-form-field dm-form-field--wide"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VSelect, {
                                        modelValue: rule.downloaders,
                                        "onUpdate:modelValue": $event => ((rule.downloaders) = $event),
                                        disabled: !__props.canManage || !downloadersReady.value,
                                        label: "作用下载器 · 可选一个或多个",
                                        items: downloaders.value,
                                        multiple: "",
                                        chips: "",
                                        "closable-chips": "",
                                        clearable: "",
                                        density: "compact",
                                        variant: "outlined",
                                        "hide-details": ""
                                      }, null, 8 /* PROPS */, ["modelValue", "onUpdate:modelValue", "disabled", "items"])
                                    ]),
                                    _: 2 /* DYNAMIC */
                                  }, 1024 /* DYNAMIC_SLOTS */),
                                  _createVNode(_component_VCol, {
                                    cols: "12",
                                    md: "4",
                                    class: "dm-form-field"
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_VSwitch, {
                                        modelValue: rule.ignore_case,
                                        "onUpdate:modelValue": $event => ((rule.ignore_case) = $event),
                                        disabled: !__props.canManage,
                                        label: "忽略大小写",
                                        "hide-details": "",
                                        color: "info",
                                        inset: ""
                                      }, null, 8 /* PROPS */, ["modelValue", "onUpdate:modelValue", "disabled"])
                                    ]),
                                    _: 2 /* DYNAMIC */
                                  }, 1024 /* DYNAMIC_SLOTS */)
                                ]),
                                _: 2 /* DYNAMIC */
                              }, 1024 /* DYNAMIC_SLOTS */),
                              _cache[44] || (_cache[44] = _createElementVNode("div", { class: "dm-auto-section-title mt-4" }, "正则条件 · 排除优先", -1 /* CACHED */)),
                              _createVNode(_component_VRow, { class: "dm-form-grid" }, {
                                default: _withCtx(() => [
                                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(regexFields, ([key, label]) => {
                                    return _createVNode(_component_VCol, {
                                      key: key,
                                      cols: "12",
                                      md: "6",
                                      class: "dm-form-field"
                                    }, {
                                      default: _withCtx(() => [
                                        _createVNode(_component_VTextField, {
                                          modelValue: rule.conditions[key],
                                          "onUpdate:modelValue": $event => ((rule.conditions[key]) = $event),
                                          disabled: !__props.canManage,
                                          label: label,
                                          density: "compact",
                                          variant: "outlined",
                                          "hide-details": ""
                                        }, null, 8 /* PROPS */, ["modelValue", "onUpdate:modelValue", "disabled", "label"])
                                      ]),
                                      _: 2 /* DYNAMIC */
                                    }, 1024 /* DYNAMIC_SLOTS */)
                                  }), 64 /* STABLE_FRAGMENT */))
                                ]),
                                _: 2 /* DYNAMIC */
                              }, 1024 /* DYNAMIC_SLOTS */),
                              _cache[45] || (_cache[45] = _createElementVNode("div", { class: "dm-auto-section-title mt-4" }, "数值达标条件", -1 /* CACHED */)),
                              _createVNode(_component_VRow, { class: "dm-form-grid dm-form-grid--three" }, {
                                default: _withCtx(() => [
                                  (_openBlock(), _createElementBlock(_Fragment, null, _renderList(numberFields, ([key, label]) => {
                                    return _createVNode(_component_VCol, {
                                      key: key,
                                      cols: "12",
                                      sm: "6",
                                      md: "4",
                                      class: "dm-form-field"
                                    }, {
                                      default: _withCtx(() => [
                                        _createVNode(_component_VTextField, {
                                          "model-value": rule.conditions[key],
                                          "onUpdate:modelValue": $event => (numberValue(rule, key, $event)),
                                          disabled: !__props.canManage,
                                          label: label,
                                          type: "number",
                                          min: "0",
                                          step: "any",
                                          density: "compact",
                                          variant: "outlined",
                                          "hide-details": ""
                                        }, null, 8 /* PROPS */, ["model-value", "onUpdate:modelValue", "disabled", "label"])
                                      ]),
                                      _: 2 /* DYNAMIC */
                                    }, 1024 /* DYNAMIC_SLOTS */)
                                  }), 64 /* STABLE_FRAGMENT */))
                                ]),
                                _: 2 /* DYNAMIC */
                              }, 1024 /* DYNAMIC_SLOTS */),
                              _cache[46] || (_cache[46] = _createElementVNode("p", { class: "text-caption text-medium-emphasis mt-2" }, "留空不限，零为有效阈值。暂停后的零上传速度不作为新的低速证据。", -1 /* CACHED */)),
                              _createElementVNode("div", _hoisted_10, [
                                _createVNode(_component_VBtn, {
                                  disabled: !__props.canManage,
                                  size: "small",
                                  variant: "text",
                                  onClick: $event => (duplicate(rule))
                                }, {
                                  default: _withCtx(() => [...(_cache[41] || (_cache[41] = [
                                    _createTextVNode("复制", -1 /* CACHED */)
                                  ]))]),
                                  _: 1 /* STABLE */
                                }, 8 /* PROPS */, ["disabled", "onClick"]),
                                _createVNode(_component_VBtn, {
                                  disabled: !__props.canManage || index === 0,
                                  size: "small",
                                  variant: "text",
                                  onClick: $event => ([settings.value.rules[index - 1], settings.value.rules[index]] = [rule, settings.value.rules[index - 1]])
                                }, {
                                  default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
                                    _createTextVNode("上移", -1 /* CACHED */)
                                  ]))]),
                                  _: 1 /* STABLE */
                                }, 8 /* PROPS */, ["disabled", "onClick"]),
                                _createVNode(_component_VBtn, {
                                  disabled: !__props.canManage,
                                  size: "small",
                                  color: "error",
                                  variant: "text",
                                  onClick: $event => (settings.value.rules.splice(index, 1))
                                }, {
                                  default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
                                    _createTextVNode("删除规则", -1 /* CACHED */)
                                  ]))]),
                                  _: 1 /* STABLE */
                                }, 8 /* PROPS */, ["disabled", "onClick"])
                              ])
                            ]),
                            _: 2 /* DYNAMIC */
                          }, 1024 /* DYNAMIC_SLOTS */)
                        ]),
                        _: 2 /* DYNAMIC */
                      }, 1024 /* DYNAMIC_SLOTS */))
                    }), 128 /* KEYED_FRAGMENT */))
                  ]),
                  _: 1 /* STABLE */
                }),
                (settings.value.rules.length)
                  ? (_openBlock(), _createElementBlock("p", _hoisted_11, "删除动作、连续采样次数和正式启用在高级选项中设置；预览只验证当前匹配条件。"))
                  : _createCommentVNode("v-if", true)
              ]))
            : _createCommentVNode("v-if", true),
          (__props.section === 'filter' || dirty.value)
            ? (_openBlock(), _createElementBlock("div", _hoisted_12, [
                (__props.section === 'filter')
                  ? (_openBlock(), _createBlock(_component_VBtn, {
                      key: 0,
                      disabled: !__props.canManage || Boolean(busy.value),
                      loading: busy.value === 'preview',
                      color: "info",
                      variant: "tonal",
                      onClick: preview
                    }, {
                      default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                        _createTextVNode("仅预览命中", -1 /* CACHED */)
                      ]))]),
                      _: 1 /* STABLE */
                    }, 8 /* PROPS */, ["disabled", "loading"]))
                  : _createCommentVNode("v-if", true),
                (dirty.value)
                  ? (_openBlock(), _createElementBlock("span", _hoisted_13, "有未保存的修改"))
                  : _createCommentVNode("v-if", true)
              ]))
            : _createCommentVNode("v-if", true),
          (__props.section === 'filter')
            ? (_openBlock(), _createElementBlock("section", _hoisted_14, [
                (previewResult.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "info",
                      variant: "tonal",
                      class: "mb-3"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode("本次只读预览：扫描 " + _toDisplayString(previewResult.value.summary?.scanned || 0) + "，条件匹配 " + _toDisplayString(previewResult.value.matches_total || 0) + " 个任务。" + _toDisplayString(previewResult.value.truncated ? '明细仅展示前 500 个候选。' : '') + "预览不暂停、不删除，也不增加连续计数。", 1 /* TEXT */)
                      ]),
                      _: 1 /* STABLE */
                    }))
                  : _createCommentVNode("v-if", true),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(previewResult.value?.errors || [], (item) => {
                  return (_openBlock(), _createBlock(_component_VAlert, {
                    key: item,
                    type: "warning",
                    variant: "tonal",
                    class: "mb-2"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(item), 1 /* TEXT */)
                    ]),
                    _: 2 /* DYNAMIC */
                  }, 1024 /* DYNAMIC_SLOTS */))
                }), 128 /* KEYED_FRAGMENT */)),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList((previewResult.value?.matches || []).filter(row => row.rules.some(rule => rule.status !== 'no_match')), (item) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: item.snapshot.downloader + item.snapshot.hash,
                    class: "dm-auto-preview mb-2"
                  }, [
                    _createElementVNode("strong", null, _toDisplayString(item.snapshot.downloader) + " · " + _toDisplayString(item.snapshot.name), 1 /* TEXT */),
                    _createElementVNode("div", _hoisted_15, _toDisplayString(item.snapshot.save_path) + " · 添加 " + _toDisplayString(timeText(item.snapshot.added_at)), 1 /* TEXT */),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(item.rules.filter(rule => rule.status !== 'no_match'), (rule) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: rule.rule_id,
                        class: "text-caption mt-1"
                      }, _toDisplayString(rule.rule_name) + " · " + _toDisplayString(rule.status === 'match' ? '条件匹配' : '无法判断') + " · 有效采样 " + _toDisplayString(item.samples[rule.rule_id] || 0) + "/" + _toDisplayString(item.required_samples[rule.rule_id] || 1) + "：" + _toDisplayString(rule.reasons.join('；')), 1 /* TEXT */))
                    }), 128 /* KEYED_FRAGMENT */)),
                    (item.protected)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_16, "任务已有保护，正式规则不会越过它。"))
                      : _createCommentVNode("v-if", true),
                    (item.limit_interference?.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_17, "受本插件上传限速影响，低速规则跳过自动处置。"))
                      : _createCommentVNode("v-if", true)
                  ]))
                }), 128 /* KEYED_FRAGMENT */))
              ]))
            : _createCommentVNode("v-if", true)
        ], 64 /* STABLE_FRAGMENT */))
      : _createCommentVNode("v-if", true),
    (__props.mode === 'history')
      ? (_openBlock(), _createElementBlock("section", _hoisted_18, [
          _createElementVNode("div", _hoisted_19, [
            _createElementVNode("h3", _hoisted_20, [
              _cache[48] || (_cache[48] = _createTextVNode("执行记录", -1 /* CACHED */)),
              _createElementVNode("span", _hoisted_21, "共 " + _toDisplayString(total.value) + " 条", 1 /* TEXT */)
            ]),
            _createElementVNode("div", _hoisted_22, [
              _createVNode(_component_VSelect, {
                modelValue: filterState.value,
                "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((filterState).value = $event)),
                items: stateItems,
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                label: "结果",
                class: "dm-auto-filter"
              }, null, 8 /* PROPS */, ["modelValue"]),
              _createVNode(_component_VSelect, {
                modelValue: filterRule.value,
                "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((filterRule).value = $event)),
                items: [{title:'全部规则',value:''}, ...(settings.value?.rules || []).map(rule => ({title:rule.name,value:rule.id}))],
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                label: "规则",
                class: "dm-auto-filter"
              }, null, 8 /* PROPS */, ["modelValue", "items"]),
              _createVNode(_component_VSelect, {
                modelValue: filterDownloader.value,
                "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((filterDownloader).value = $event)),
                items: [{title:'全部下载器',value:''}, ...downloaders.value],
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                label: "下载器",
                class: "dm-auto-filter"
              }, null, 8 /* PROPS */, ["modelValue", "items"])
            ])
          ]),
          (historyLoading.value)
            ? (_openBlock(), _createBlock(_component_VProgressLinear, {
                key: 0,
                color: "primary",
                indeterminate: ""
              }))
            : _createCommentVNode("v-if", true),
          (!records.value.length)
            ? (_openBlock(), _createElementBlock("div", _hoisted_23, _toDisplayString(historyLoading.value ? '正在读取执行记录…' : error.value ? '执行记录读取失败，请刷新重试' : '暂无执行记录'), 1 /* TEXT */))
            : (_openBlock(), _createElementBlock("div", _hoisted_24, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(records.value, (record) => {
                  return (_openBlock(), _createBlock(_sfc_main$4, {
                    key: props.pluginId + ':' + record.id,
                    time: timeText(record.created_at),
                    name: record.name || record.torrent_hash,
                    status: stateText(record.state),
                    color: recordColor(record.state)
                  }, {
                    default: _withCtx(() => [
                      _createElementVNode("div", null, "规则 · " + _toDisplayString(record.rule_name || '—'), 1 /* TEXT */),
                      _createElementVNode("div", null, "下载器 · " + _toDisplayString(record.downloader || '—'), 1 /* TEXT */),
                      (record.error)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_25, _toDisplayString(record.error), 1 /* TEXT */))
                        : _createCommentVNode("v-if", true),
                      _createElementVNode("div", _hoisted_26, [
                        _createVNode(_component_VBtn, {
                          size: "x-small",
                          variant: "text",
                          onClick: $event => (detail.value = record)
                        }, {
                          default: _withCtx(() => [...(_cache[49] || (_cache[49] = [
                            _createTextVNode("依据", -1 /* CACHED */)
                          ]))]),
                          _: 1 /* STABLE */
                        }, 8 /* PROPS */, ["onClick"]),
                        (_unref(protectedStates).has(record.state))
                          ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                              _createVNode(_component_VBtn, {
                                disabled: !__props.canManage || Boolean(busy.value),
                                size: "x-small",
                                color: "warning",
                                variant: "tonal",
                                onClick: $event => (release(record, false))
                              }, {
                                default: _withCtx(() => [...(_cache[50] || (_cache[50] = [
                                  _createTextVNode("解除保护", -1 /* CACHED */)
                                ]))]),
                                _: 1 /* STABLE */
                              }, 8 /* PROPS */, ["disabled", "onClick"]),
                              _createVNode(_component_VBtn, {
                                disabled: !__props.canManage || Boolean(busy.value),
                                size: "x-small",
                                color: "primary",
                                variant: "tonal",
                                onClick: $event => (release(record, true))
                              }, {
                                default: _withCtx(() => [...(_cache[51] || (_cache[51] = [
                                  _createTextVNode("恢复原状态", -1 /* CACHED */)
                                ]))]),
                                _: 1 /* STABLE */
                              }, 8 /* PROPS */, ["disabled", "onClick"])
                            ], 64 /* STABLE_FRAGMENT */))
                          : _createCommentVNode("v-if", true)
                      ])
                    ]),
                    _: 2 /* DYNAMIC */
                  }, 1032 /* PROPS, DYNAMIC_SLOTS */, ["time", "name", "status", "color"]))
                }), 128 /* KEYED_FRAGMENT */))
              ])),
          (pages.value > 1)
            ? (_openBlock(), _createElementBlock("div", _hoisted_27, [
                _createVNode(_component_VPagination, {
                  modelValue: page.value,
                  "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((page).value = $event)),
                  length: pages.value,
                  "total-visible": 5,
                  density: "compact"
                }, null, 8 /* PROPS */, ["modelValue", "length"]),
                _createElementVNode("span", _hoisted_28, "共 " + _toDisplayString(total.value) + " 条", 1 /* TEXT */)
              ]))
            : _createCommentVNode("v-if", true)
        ]))
      : _createCommentVNode("v-if", true),
    _createVNode(_component_VDialog, {
      "model-value": Boolean(confirmRule.value),
      "onUpdate:modelValue": _cache[18] || (_cache[18] = value => { if (!value) confirmRule.value = null; }),
      "max-width": "720",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [
                _createTextVNode("确认正式启用 · " + _toDisplayString(confirmRule.value?.name), 1 /* TEXT */)
              ]),
              _: 1 /* STABLE */
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                (error.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "error",
                      variant: "tonal",
                      class: "mb-3"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(error.value), 1 /* TEXT */)
                      ]),
                      _: 1 /* STABLE */
                    }))
                  : _createCommentVNode("v-if", true),
                _createElementVNode("p", null, "确认已保存规则后，未来命中任务会自动执行 " + _toDisplayString(confirmRule.value?.action === 'data' ? '删除种子及下载数据' : '仅删种、保留数据') + "。此按钮只保存确认，实际处置等下一个周期或手动运行。", 1 /* TEXT */),
                _cache[53] || (_cache[53] = _createElementVNode("p", { class: "text-caption" }, "已有暂停任务可单独勾选。未选任务继续受保护；勾选表示接受暂停前的指标，不把当前零上传速度作为低速依据。", -1 /* CACHED */)),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(confirmJobs.value, (record) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: record.id
                  }, [
                    _createVNode(_component_VCheckbox, {
                      modelValue: selectedJobs.value,
                      "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((selectedJobs).value = $event)),
                      value: record.id,
                      label: `${record.name} · ${timeText(record.created_at)}`,
                      "hide-details": ""
                    }, null, 8 /* PROPS */, ["modelValue", "value", "label"]),
                    _createElementVNode("div", _hoisted_29, _toDisplayString(record.evidence.join('；')), 1 /* TEXT */)
                  ]))
                }), 128 /* KEYED_FRAGMENT */)),
                (confirmTotal.value > 100)
                  ? (_openBlock(), _createBlock(_component_VPagination, {
                      key: 1,
                      "model-value": confirmPage.value,
                      length: Math.ceil(confirmTotal.value / 100),
                      disabled: Boolean(busy.value),
                      density: "compact",
                      "onUpdate:modelValue": loadConfirmPage
                    }, null, 8 /* PROPS */, ["model-value", "length", "disabled"]))
                  : _createCommentVNode("v-if", true),
                (selectedJobs.value.length)
                  ? (_openBlock(), _createBlock(_component_VCheckbox, {
                      key: 2,
                      modelValue: acceptHistory.value,
                      "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((acceptHistory).value = $event)),
                      label: "我已核对所选任务的暂停前采样证据，并接受这批历史命中依据"
                    }, null, 8 /* PROPS */, ["modelValue"]))
                  : _createCommentVNode("v-if", true),
                (!confirmJobs.value.length)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 3,
                      type: "info",
                      variant: "tonal",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [...(_cache[52] || (_cache[52] = [
                        _createTextVNode("本页没有可选暂停任务；只启用后续规则。零命中不等于已有实际命中样本。", -1 /* CACHED */)
                      ]))]),
                      _: 1 /* STABLE */
                    }))
                  : _createCommentVNode("v-if", true)
              ]),
              _: 1 /* STABLE */
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  onClick: _cache[17] || (_cache[17] = $event => (confirmRule.value = null))
                }, {
                  default: _withCtx(() => [...(_cache[54] || (_cache[54] = [
                    _createTextVNode("取消", -1 /* CACHED */)
                  ]))]),
                  _: 1 /* STABLE */
                }),
                _createVNode(_component_VBtn, {
                  disabled: !__props.canManage || Boolean(busy.value) || (selectedJobs.value.length > 0 && !acceptHistory.value),
                  color: "warning",
                  onClick: activate
                }, {
                  default: _withCtx(() => [...(_cache[55] || (_cache[55] = [
                    _createTextVNode("确认正式启用", -1 /* CACHED */)
                  ]))]),
                  _: 1 /* STABLE */
                }, 8 /* PROPS */, ["disabled"])
              ]),
              _: 1 /* STABLE */
            })
          ]),
          _: 1 /* STABLE */
        })
      ]),
      _: 1 /* STABLE */
    }, 8 /* PROPS */, ["model-value"]),
    _createVNode(_component_VDialog, {
      "model-value": Boolean(detail.value),
      "onUpdate:modelValue": _cache[20] || (_cache[20] = value => { if (!value) detail.value = null; }),
      "max-width": "720",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [
                _createTextVNode("命中依据 · " + _toDisplayString(detail.value?.name), 1 /* TEXT */)
              ]),
              _: 1 /* STABLE */
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(detail.value?.evidence || [], (reason) => {
                  return (_openBlock(), _createElementBlock("div", {
                    key: reason,
                    class: "mb-1"
                  }, _toDisplayString(reason), 1 /* TEXT */))
                }), 128 /* KEYED_FRAGMENT */)),
                _createElementVNode("div", _hoisted_30, "采样 " + _toDisplayString(timeText(detail.value?.created_at)) + " · " + _toDisplayString(detail.value?.downloader) + " · " + _toDisplayString(detail.value?.torrent_hash), 1 /* TEXT */),
                _createElementVNode("div", _hoisted_31, "保存路径 " + _toDisplayString(detail.value?.snapshot?.save_path), 1 /* TEXT */),
                (detail.value?.error)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "warning",
                      variant: "tonal",
                      class: "mt-3"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(detail.value.error), 1 /* TEXT */)
                      ]),
                      _: 1 /* STABLE */
                    }))
                  : _createCommentVNode("v-if", true)
              ]),
              _: 1 /* STABLE */
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  onClick: _cache[19] || (_cache[19] = $event => (detail.value = null))
                }, {
                  default: _withCtx(() => [...(_cache[56] || (_cache[56] = [
                    _createTextVNode("关闭", -1 /* CACHED */)
                  ]))]),
                  _: 1 /* STABLE */
                })
              ]),
              _: 1 /* STABLE */
            })
          ]),
          _: 1 /* STABLE */
        })
      ]),
      _: 1 /* STABLE */
    }, 8 /* PROPS */, ["model-value"])
  ]))
}
}

};
const AutoDeletePane = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-1e692ae7"]]);

export { AutoDeletePane as A, SyncDeletePane as S, _export_sfc as _, getPluginApi as a, _sfc_main$4 as b, postPluginApi as c, getManagementPermission as g, isApiRequestCancellation as i, postPluginJsonApi as p };
