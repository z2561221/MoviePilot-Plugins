const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { resolve } = require('node:path')
const { createRequire } = require('node:module')

const frontend = resolve(__dirname, '../../../plugins.v3/downloadmanagerlocal/frontend')
const requireFrontend = createRequire(resolve(frontend, 'package.json'))
const vue = requireFrontend('vue')
const compiler = requireFrontend('vue/compiler-sfc')
const nativePermission = requireFrontend('./src/components/api.js').getManagementPermission
const settle = async () => { await vue.nextTick(); await new Promise(resolve => setImmediate(resolve)); await vue.nextTick() }
const defaults = () => ({ enabled: false, schedule_type: 'interval', interval_minutes: 5, cron: '', sample_minutes: 5,
  max_tasks: 20, source_paths: [], exclude_paths: [], notify: false, history_days: 30, rules: [] })

function compiledComponent(name, api, components) {
  const descriptor = compiler.parse(readFileSync(resolve(frontend, `src/components/${name}.vue`), 'utf8')).descriptor
  const script = compiler.compileScript(descriptor, { id: `layout-${name}`, inlineTemplate: true }).content
    .replace(/import\s*\{([\s\S]*?)\}\s*from\s*["']vue["'];?/g,
      (_match, names) => `const { ${names.replace(/\bas\b/g, ':')} } = vue`)
    .replace(/import\s*\{([^}]+)\}\s*from\s*['"]\.\/api['"];?/g, (_match, names) => `const { ${names} } = api`)
    .replace(/import (\w+) from ['"]\.\/(\w+)\.vue['"];?/g, (_match, local, target) => `const ${local} = components.${target}`)
    .replace(/^import ['"]\.\/form-layout\.css['"];?$/gm, '')
    .replace(/^import ['"]\.\/history-layout\.css['"];?$/gm, '')
    .replace('export default', 'return')
  return new Function('vue', 'api', 'components', script)(vue, api, components)
}

function fixture(name, input = {}, options = {}) {
  const reads = [], writes = [], timers = [], events = []
  let stored = structuredClone(options.stored || input.initialConfig || {})
  const client = {
    async put(path, body) {
      writes.push({ path, body: structuredClone(body) })
      if (options.put) return options.put(path, body)
      stored = { ...structuredClone(body), onlyonce: false, iyuu_onlyonce: false }
      return { success: true }
    },
  }
  const api = {
    getManagementPermission: (_client, optionsArg) => nativePermission({ get: async (path, requestOptions) => {
      reads.push(path)
      const permission = options.permissions ? await options.permissions(_client, props.pluginId, requestOptions) : { can_manage: true }
      return { is_active: true, is_superuser: permission.can_manage }
    } }, { ...optionsArg, timeoutMs: options.permissionTimeoutMs || 8000 }),
    getPluginApi: async (_client, _id, path, requestOptions) => {
      reads.push(path)
      if (options.get && Object.hasOwn(options.get, path)) return options.get[path](requestOptions)
      if (path === '') return structuredClone(stored)
      if (path === 'permissions') return options.permissions ? options.permissions(_client, _id) : { can_manage: true }
      if (path === 'auto_delete/config') return { settings: structuredClone(options.settings || defaults()), revision: 1 }
      if (path === 'auto_delete/status') return { state: 'disabled', enabled: false, active: false }
      if (path === 'reseed/status') return { status: 'idle', phase: '尚未运行' }
      if (path.startsWith('auto_delete/history')) return { items: [{ id: 'job', rule_name: '旧规则', name: '旧任务', downloader: 'QB', created_at: 1, state: 'removed' }], total: 1 }
      if (path.startsWith('rename_history')) return { items: options.renameRecords || [], total: options.renameTotal || (options.renameRecords || []).length }
      if (path.startsWith('rename_archive')) return { items: options.archiveRecords || [], total: options.archiveTotal || (options.archiveRecords || []).length }
      if (path === 'sync_delete/options') return { servers: [] }
      if (path === 'overview') return options.overview || { cards: {}, modules: options.modules || [] }
      if (path.startsWith('sync_delete/history')) {
        const jobs = (options.jobs || []).filter(job => !path.includes('pending_only=true') || job.state === 'failed')
        return { items: jobs, total: jobs.length, enabled: true }
      }
      return []
    },
    postPluginJsonApi: async (_client, _id, path, body) => {
      writes.push({ path, body })
      if (options.post) return options.post(path, body)
      if (path === 'auto_delete/config') {
        for (const [key, value] of Object.entries(body.settings)) stored['auto_delete_' + key] = structuredClone(value)
      }
      return path === 'sync_delete/dismiss' ? { job_id: body.job_id, state: 'dismissed' } : path === 'sync_delete/retry' ? { accepted: true } : { settings: body.settings, revision: 2 }
    },
    postPluginApi: async () => ({}), isApiRequestCancellation: requireFrontend('./src/components/api.js').isApiRequestCancellation,
  }
  const components = {}
  for (const component of ['HistoryRow', 'AutoDeleteCron', 'AutoDeletePane', 'SyncDeleteDetails', 'SyncDeletePane', 'ReseedTask', 'Page', 'Config']) {
    components[component] = compiledComponent(component, api, components)
  }
  const element = type => ({ type, props: {}, children: [], parent: null, style: {} })
  const renderer = vue.createRenderer({
    createElement: element,
    createText: text => ({ ...element('#text'), text }), createComment: text => ({ ...element('#comment'), text }),
    insert(node, parent, anchor) {
      if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
      const index = anchor ? parent.children.indexOf(anchor) : -1
      parent.children.splice(index < 0 ? parent.children.length : index, 0, node)
      node.parent = parent
    },
    remove(node) { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = null },
    setText(node, text) { node.text = text }, setElementText(node, text) { node.text = text; node.children = [] },
    patchProp(node, key, _old, value) { node.props[key] = value; if (key === 'style' && value) Object.assign(node.style, value) },
    parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
  })
  const props = vue.reactive({ api: client, pluginId: 'ScopedInstance', canManage: true, mode: 'config', section: 'basic', active: true, ...input })
  const container = element('root')
  const app = renderer.createApp({ render: () => vue.h(components[name], { ...props, canManage: props.canManage, onSave: value => events.push(value), onClose: () => events.push('close'), onReview: value => events.push({ review: value }) }) })
  const uiNames = new Set()
  for (const component of ['HistoryRow', 'AutoDeleteCron', 'AutoDeletePane', 'SyncDeleteDetails', 'SyncDeletePane', 'ReseedTask', 'Config', 'Page']) {
    for (const match of readFileSync(resolve(frontend, `src/components/${component}.vue`), 'utf8').matchAll(/<(V\w+)\b/g)) uiNames.add(match[1])
  }
  for (const component of uiNames) app.component(component, {
    inheritAttrs: false,
    setup(_props, { attrs, slots }) {
      return () => vue.h(component, attrs, component === 'VDialog' && !(attrs.modelValue ?? attrs['model-value']) ? []
        : [attrs.label || '', ...Object.values(slots).flatMap(slot => slot())])
    },
  })
  const savedGlobals = { document: global.document, window: global.window, setInterval: global.setInterval, clearInterval: global.clearInterval }
  global.document = { visibilityState: 'visible', addEventListener() {}, removeEventListener() {} }
  global.window = { setInterval: callback => (timers.push(callback), timers.length), clearInterval() {} }
  global.setInterval = callback => (timers.push(callback), timers.length)
  global.clearInterval = () => {}
  const warnings = [], errors = []
  app.config.warnHandler = message => warnings.push(message)
  app.config.errorHandler = error => errors.push(String(error))
  app.mount(container)
  const visible = node => node.style.display !== 'none' && (!node.parent || visible(node.parent))
  const all = (predicate, node = container) => [...(predicate(node) ? [node] : []), ...node.children.flatMap(child => all(predicate, child))]
  const text = (node = container) => node.type === '#comment' ? '' : String(node.text || '') + node.children.map(text).join('')
  return { props, reads, writes, events, warnings, errors, all, text, visible, close() {
    app.unmount()
    Object.assign(global, savedGlobals)
  } }
}

test('configuration restores all six original chains and only appends the two missing delete chains', async () => {
  const view = fixture('Config', { initialConfig: {} })
  try {
    await settle()
    const hasClass = (node, name) => String(node.props.class || '').split(' ').includes(name)
    const flows = view.all(node => hasClass(node, 'dm-flow-block') && view.visible(node))
    assert.equal(flows.length, 8)
    const labels = flows.map(node => view.text(view.all(child => hasClass(child, 'dm-flow-label'), node)[0]))
    assert.deepEqual(labels, ['速度监控', '转移做种', 'IYUU铺种', '公共链路', '上传限速', '兜底补刀', '同步删除', '自动删除'])
    const steps = flows.map(node => view.all(child => hasClass(child, 'dm-flow-step'), node).map(child => view.text(child)))
    assert.deepEqual(steps.slice(0, 6), [
      ['下载任务', '监控会话', '有效采样', '阈值判定', '告警通知', '异常处置'],
      ['下载完成', '延迟等待', '目标转移', '公共链路'],
      ['任务触发', '资源查询', '辅种下载', '公共链路'],
      ['命名处理', '站点标签', '做种校验'],
      ['全局限速', '站点识别', '按需设限', '合计限速', '动态调速', '停用恢复'],
      ['异常命名', '兜底补刀', '失败计数', '归档恢复'],
    ])
    assert(!view.text().includes('当前状态见链路旁'))
    assert(!view.text().includes('当前状态与模块指标'))
    assert(!view.text().includes('恢复机制'))
    assert.equal(view.all(node => node.props['data-module']).length, 0)
    assert.deepEqual(view.errors, [])
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
})

test('detail overview starts with its original four statistics and runtime panels, with new cards appended', async () => {
  const modules = [
    { key: 'transfer', state: 'idle' },
    { key: 'tag', title: '站点标签', state: 'idle', metrics: { 'Tracker 映射': 3 } },
    { key: 'sync_delete', title: '同步删除', state: 'attention', pending: 2, metrics: { '已完成': 11 } },
    { key: 'auto_delete', title: '自动删除', state: 'idle', pending: 0 },
  ]
  const view = fixture('Page', {}, { modules, overview: {
    cards: { transfer: { active: true, today_success: 2, today_fallback: 1, success_total: 10 }, iyuu: { enabled: true },
      pieces: { configured: true, enabled: true, today_success: 3, today_fail: 2, success_total: 11 }, seed: { autostart: true } },
    modules, archive: {}, speed_monitor: { service_status: 'idle' }, upload_limit: { service_status: 'running' },
    auto_delete: { debug_rules: 1, delete_rules: 0 },
  } })
  try {
    await settle()
    const hasClass = (node, name) => String(node.props.class || '').split(' ').includes(name)
    const pane = view.all(node => hasClass(node, 'dm-overview-pane'))[0]
    const sections = pane.children.filter(node => node.type !== '#comment').map(node => String(node.props.class || ''))
    assert.match(sections[0], /dm-overview-stat-grid/)
    assert.match(sections[1], /dm-attention-panel/)
    assert.match(sections[2], /dm-section-heading/)
    assert.match(sections[3], /dm-runtime-section/)
    assert.match(sections[4], /dm-runtime-section/)
    assert.match(sections[5], /dm-feature-section/)
    assert.equal(sections.length, 6)
    assert.deepEqual(view.all(node => hasClass(node, 'dm-overview-stat-label')).map(node => view.text(node)), ['速度监控', '上传限速', '待关注', '异常数量'])
    assert.deepEqual(view.all(node => node.props['data-runtime-section']).map(node => node.props['data-runtime-section']), ['speed-monitor', 'upload-limit'])
    const features = view.all(node => hasClass(node, 'dm-feature-head'))
    assert.deepEqual(features.map(node => view.text(node.children[0])), ['转移做种', 'IYUU铺种', '辅助铺种', '命名补刀', '做种校验', '站点标签', '同步删除', '自动删除'])
    assert.equal(view.text(features[2].children[1]), '随 IYUU')
    assert(view.text(features[2].parent).includes('成功 3 · 失败 2 · 累计 8'))
    assert(view.text().includes('今日 2 · 兜底 1 · 累计 8'))
    assert(view.text().includes('调试 1 · 正式 0 · 待处理 0'))
    assert(!view.text().includes('运行链路'))
    assert(!view.text().includes('当前状态与模块指标'))
    const attention = view.all(node => hasClass(node, 'dm-attention-item'))[0]
    view.all(node => node.type === 'VBtn' && view.text(node) === '查看', attention)[0].props.onClick()
    await settle()
    assert(view.reads.some(path => path.startsWith('sync_delete/history') && path.includes('pending_only=true')))
    assert.deepEqual(view.writes, [])
    assert.deepEqual(view.errors, [])
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
})

test('actual history table exists only on the detail surface', async () => {
  const view = fixture('AutoDeletePane')
  try {
    await settle()
    assert.equal(view.all(node => node.props['data-execution-history'] !== undefined).length, 0)
    assert(!view.reads.some(path => path.startsWith('auto_delete/history')))
    view.props.mode = 'history'
    await settle()
    assert.equal(view.all(node => node.props['data-execution-history'] !== undefined).length, 1)
    assert(view.text().includes('旧任务'))
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
})

test('populated rule keeps matching fields in filters and confirmation controls in advanced options', async () => {
  const conditions = Object.fromEntries(['name_include', 'name_exclude', 'path_include', 'path_exclude', 'tracker_include', 'tracker_exclude', 'tracker_error', 'category', 'tag_include', 'tag_exclude'].map(key => [key, '']))
  Object.assign(conditions, Object.fromEntries(['ratio_min', 'ratio_max', 'seed_hours_min', 'added_hours_min', 'size_gib_min', 'size_gib_max', 'upload_kib_max'].map(key => [key, null])))
  const settings = { ...defaults(), rules: [{ id: 'rule', name: '冷种检查', revision: 1, enabled: true, mode: 'debug', action: 'torrent', downloaders: ['QB'], ignore_case: true, consecutive: 2, conditions }] }
  const view = fixture('AutoDeletePane', { section: 'filter' }, { settings })
  try {
    await settle()
    const shownField = label => view.all(node => node.props.label === label && view.visible(node))
    const confirmation = () => view.all(node => node.type === 'VBtn' && view.text(node) === '确认并正式启用' && view.visible(node))
    assert.equal(shownField('种子名称包含正则').length, 1)
    assert.equal(shownField('正式删除动作').length, 0)
    assert.equal(shownField('连续有效采样次数').length, 0)
    assert.equal(confirmation().length, 0)
    shownField('种子名称包含正则')[0].props['onUpdate:modelValue']('Movie')
    view.props.section = 'advanced'
    await settle()
    assert.equal(shownField('种子名称包含正则').length, 0)
    assert.equal(shownField('正式删除动作').length, 1)
    assert.equal(shownField('连续有效采样次数').length, 1)
    assert.equal(confirmation().length, 1)
    assert.equal(confirmation()[0].props.disabled, true)
    view.props.section = 'filter'
    await settle()
    assert.equal(shownField('种子名称包含正则')[0].props.modelValue, 'Movie')
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
})

test('basic settings lead to rule confirmation; missing data directory is identified on selection and cross-tab save', async () => {
  const rule = { id: 'sample', name: '调试规则', enabled: true, mode: 'debug', action: 'torrent', consecutive: 2, downloaders: ['QB'], conditions: {} }
  const view = fixture('Config', {}, { settings: { ...defaults(), rules: [rule] } })
  try {
    const find = (type, text) => view.all(n => n.type === type && view.text(n) === text && view.visible(n))[0]
    const field = label => view.all(n => n.props.label === label && view.visible(n))[0]
    await settle()
    find('VListItem', '自动删除').props.onClick()
    await settle()
    assert(view.text().includes('成功完成一次调试扫描'))
    await find('VBtn', '前往规则处置与确认').props.onClick()
    await settle()
    assert.equal(view.writes.length, 0)
    assert(find('h3', '规则处置与确认'))
    field('正式删除动作').props['onUpdate:modelValue']('data')
    await settle()
    assert.match(field('正式删除动作').props.errorMessages || field('正式删除动作').props['error-messages'], /删除数据范围/)
    const allowed = () => field('允许删除的下载目录')
    const errorText = () => allowed().props.errorMessages ?? allowed().props['error-messages']
    assert.match(errorText(), /请填写/)
    find('VListItem', '运行总览').props.onClick()
    await settle()
    await find('VBtn', '保存配置').props.onClick()
    await settle()
    assert.match(view.text(view.all(n => n.props.role === 'status')[0]), /请填写「允许删除的下载目录」/)
    assert.equal(view.writes.length, 0)
    allowed().props['onUpdate:modelValue']('/downloads/test')
    await settle()
    assert.equal(errorText(), '')
    assert.equal(view.all(n => n.props.role === 'status').length, 0)
    assert.equal(view.errors.length, 0)
    assert.equal(view.writes.length, 0)
  } finally { view.close() }
})

test('host validation details reach the shared save notice', async () => {
  const view = fixture('Config', {}, { post() { throw { message: '请求参数不正确', response: { data: {
    success: false, message: '请求参数不正确', data: [{ location: ['body', 'settings'], message: 'Value error, Cron 表达式无效' }],
  } } } } })
  try {
    await settle()
    view.all(n => n.type === 'VListItem' && view.text(n) === '自动删除')[0].props.onClick()
    await settle()
    view.all(n => n.props.label === '扫描间隔（分钟）')[0].props['onUpdate:modelValue'](11)
    await view.all(n => n.type === 'VBtn' && view.text(n) === '保存配置')[0].props.onClick()
    await settle()
    assert.equal(view.text(view.all(n => n.props.role === 'status')[0]), 'Cron 表达式无效')
    assert.deepEqual(view.writes.map(item => item.path), ['auto_delete/config'])
  } finally { view.close() }
})

test('Pieces-hash passkey lines select generic sites without a separate site picker', async () => {
  const view = fixture('Config', { initialConfig: { pieces_enabled: false, pieces_sites: [7], pieces_site_keys: '青蛙:/custom/path,old-test-key' } }, { get: {
    sites: () => [{ title: '青蛙', value: 7 }, { title: 'Example tracker', value: 8 }],
  } })
  try {
    await settle()
    const find = (type, text) => view.all(node => node.type === type && view.text(node) === text && view.visible(node))[0]
    const field = label => view.all(node => node.props.label === label && view.visible(node))
    await find('VListItem', 'IYUU铺种').props.onClick()
    await settle()
    await find('button', '基础设置').props.onClick()
    await settle()

    assert(!view.reads.includes('reseed/status'))
    assert.equal(view.text().includes('本轮完成'), false)
    assert.equal(view.text().includes('目标任务已存在'), false)
    assert.equal(view.text().includes('已扫描 100'), false)
    assert(view.text().includes('辅助铺种'))
    assert.equal(field('匹配方式').length, 0)
    assert.equal(field('IYUU Token').length, 1)
    assert.equal(find('VBtn', '匹配预览'), undefined)
    assert.equal(find('VBtn', '运行辅助铺种'), undefined)
    assert.equal(view.text().includes('Pieces-hash 通用配置'), false)
    assert.equal(field('辅种站点').length, 0)
    assert.equal(field('辅助铺种配置').length, 0)
    assert(!view.text().includes('old-test-key'))
    await find('VBtn', '编辑接口与凭据').props.onClick()
    await settle()
    const passkeyField = field('辅助铺种配置')[0]
    assert.equal(passkeyField.props.modelValue, '青蛙:/custom/path,old-test-key')
    const pane = passkeyField.parent.parent.parent
    const help = view.all(node => node.type === 'VAlert' && view.visible(node), pane)
    assert.equal(help.length, 1)
    const paneNodes = view.all(() => true, pane)
    assert(paneNodes.indexOf(passkeyField) < paneNodes.indexOf(help[0]))
    assert(view.text(help[0]).includes('站点管理'))
    assert(view.text(help[0]).includes('站名:/查询路径,Passkey'))
    assert(passkeyField.props.placeholder.includes('青蛙:/api/pieces-hash,你的Passkey'))
    assert(passkeyField.props.placeholder.includes('憨憨:/nexusapi/pieces-hash,你的Passkey'))
    assert(view.text(help[0]).includes('先启用 IYUU 铺种、填写 IYUU Token'))
    assert(view.text(help[0]).includes('「条件筛选」选择辅种下载器'))
    assert(view.text(help[0]).includes('「站点管理」中启用，名称一致且唯一'))
    assert(view.text(help[0]).includes('请求间隔可省略，默认 1 秒'))
    assert(view.text(help[0]).includes('勾选「立即运行一次」并保存'))
    assert.equal(view.text(help[0]).includes('/api/'), false)
    assert(view.text(help[0]).includes('路径由你填写，不内置、不自动探测'))
    assert(view.text(help[0]).includes('fxo_'))
    assert(view.text(help[0]).includes('crossseed 查询和下载权限'))
    assert.equal(view.text(help[0]).includes('定时辅种周期'), false)
    assert.equal(view.text(help[0]).includes('不要同时配置 IYUU'), false)
    assert.equal(view.text().includes('仅保存设置'), false)
    assert.equal(view.text().includes('青蛙、AGSVPT'), false)
    assert.equal(field('API 路径').length, 0)
    assert.equal(field('站点请求间隔（秒）').length, 0)
    assert.equal(field('每批指纹数量').length, 0)
    assert.equal(field('源 qB 下载器').length, 0)
    assert.equal(field('已完成源种子').length, 0)
    assert.equal(field('选择种子').length, 0)
    assert.equal(find('VBtn', '只查青蛙匹配'), undefined)

    passkeyField.props['onUpdate:modelValue']('Example tracker:/lookup,test-passkey\n青蛙:/other/query,another-key,3')
    await find('VBtn', '隐藏凭据').props.onClick()
    await settle()
    assert.equal(field('辅助铺种配置').length, 0)
    await find('VBtn', '保存配置').props.onClick()
    await settle()

    const saved = view.writes.find(item => item.path === 'plugin/ScopedInstance')?.body
    assert.equal(saved.pieces_site_keys, 'Example tracker:/lookup,test-passkey\n青蛙:/other/query,another-key,3')
    assert.equal('pieces_sites' in saved, false)
    assert.equal('pieces_enabled' in saved, false)
    assert.equal('pieces_site_configs' in saved, false)
    assert.equal('pieces_site_passkeys' in saved, false)
    assert.equal('pieces_batch_size' in saved, false)
    assert(!view.reads.some(path => path.startsWith('pieces/')))
    assert(!view.writes.some(item => String(item.path).includes('pieces/preview')))
  } finally { view.close() }
})

test('reseed displays progress from the existing IYUU task without a separate start', async () => {
  const task = { task_id: 'iyuu', status: 'running', phase: '查询 IYUU', scanned: 100, result_count: 0 }
  const view = fixture('ReseedTask', {}, {
    get: { 'reseed/status': () => task },
  })
  try {
    await settle()
    assert.equal(view.writes.length, 0)
    assert(view.text().includes('查询 IYUU'))
    assert(!view.text().includes('匹配预览'))
    assert(!view.text().includes('运行辅助铺种'))
    assert.deepEqual(view.errors, [])
  } finally { view.close() }
})

test('reseed stop addresses the current task and preserves failure feedback', async () => {
  const view = fixture('ReseedTask', {}, {
    get: { 'reseed/status': () => ({ task_id: 'iyuu-current', status: 'running', phase: '查询 IYUU' }) },
    post: async () => { throw new Error('504 回执超时') },
  })
  try {
    await settle()
    const button = () => view.all(node => node.type === 'VBtn' && view.text(node) === '停止')[0]
    await button().props.onClick()
    await settle()
    assert(view.text().includes('504 回执超时'))
    assert.equal(view.writes[0].path, 'reseed/stop')
    assert.equal(view.writes[0].body.task_id, 'iyuu-current')
  } finally { view.close() }
})

test('reseed late response cannot overwrite another plugin instance', async () => {
  let resolveOld
  let reads = 0
  const old = new Promise(resolve => { resolveOld = resolve })
  const view = fixture('ReseedTask', {}, {
    get: { 'reseed/status': () => ++reads === 1 ? old : { status: 'idle', phase: '新实例' } },
  })
  try {
    await settle()
    view.props.pluginId = 'AnotherInstance'
    await settle()
    resolveOld({ status: 'completed', phase: '旧实例完成', result_count: 0 })
    await settle()
    assert(view.text().includes('新实例'))
    assert(!view.text().includes('旧实例完成'))
  } finally { view.close() }
})

test('reseed stop requires management permission', async () => {
  const view = fixture('ReseedTask', {}, {
    get: { 'reseed/status': () => ({ task_id: 'iyuu-current', status: 'running', phase: '查询 IYUU' }) },
  })
  try {
    await settle()
    const button = view.all(node => node.type === 'VBtn' && view.text(node) === '停止')[0]
    view.props.canManage = false
    await settle()
    await button.props.onClick()
    assert.equal(view.writes.length, 0)
  } finally { view.close() }
})

test('tag completion submits background tasks, restores status, and keeps the preview confirmation step', async () => {
  const scan = { code: 0, msg: '扫描完成', errors: [], downloaders: [{
    name: 'QB2', type: 'qbittorrent', task_count: 2, missing_count: 2, unmatched_tracker_count: 0,
    tags: [{ kind: 'site', tag: '🏠站点A', hashes: ['hash-1', 'hash-2'], count: 2, samples: ['种子A'] }],
  }] }
  const tasks = new Map()
  const results = new Map()
  let taskIndex = 0
  let statusReads = 0
  const view = fixture('Config', { initialConfig: {} }, {
    post: async (path, body) => {
      if (path === 'tag_completion_scan') {
        const taskId = `task-${++taskIndex}`
        const task = { found: true, code: 0, task_id: taskId, operation: 'scan', status: 'queued', phase: '等待后台任务', can_cancel: true }
        tasks.set(taskId, task)
        results.set(taskId, scan)
        return task
      }
      if (path === 'tag_completion_execute') {
        assert.equal(body.scan_task_id, 'task-1')
        assert.deepEqual(body.repairs, [{ downloader: 'QB2', kind: 'site', tag: '🏠站点A' }])
        const taskId = `task-${++taskIndex}`
        const task = { found: true, code: 0, task_id: taskId, operation: 'execute', status: 'queued', phase: '等待后台任务', can_cancel: true }
        tasks.set(taskId, task)
        results.set(taskId, { code: 0, msg: '补全完成：新增 1 条标签关联，失败 0 个任务' })
        return task
      }
      if (path === 'tag_completion_cancel') {
        const task = tasks.get(body.task_id)
        return { ...task, status: 'cancelled', can_cancel: false, msg: '任务已取消' }
      }
      return {}
    },
    get: {
      downloaders: () => [{ title: 'QB2', value: 'QB2', type: 'qbittorrent' }],
      tag_completion_task: requestOptions => {
        statusReads += 1
        const taskId = requestOptions?.params?.task_id
        const task = taskId ? tasks.get(taskId) : null
        return task ? { ...task, status: task.operation === 'scan' ? 'completed' : 'completed', can_cancel: false }
          : { found: false, msg: '没有可查询的标签补全任务' }
      },
      tag_completion_result: requestOptions => {
        const taskId = requestOptions?.params?.task_id
        const stored = results.get(taskId)
        const offset = requestOptions?.params?.offset || 0
        if (taskId === 'task-1') {
          const page = structuredClone(stored)
          page.downloaders[0].tags[0].hashes = [stored.downloaders[0].tags[0].hashes[offset]]
          return { code: 0, result: page, offset, next_offset: offset + 1, total: 2, complete: offset === 1 }
        }
        return { code: 0, result: stored, offset: 0, next_offset: 0, total: 0, complete: true }
      },
    },
  })
  try {
    await settle()
    await new Promise(resolve => setTimeout(resolve, 5))
    await settle()
    const find = (type, text) => view.all(node => node.type === type && view.text(node) === text && view.visible(node))[0]
    const field = label => view.all(node => node.props.label === label && view.visible(node))
    find('VListItem', '站点标签').props.onClick()
    await settle()
    find('button', '补全标签').props.onClick()
    await settle()
    field('下载器')[0].props['onUpdate:modelValue'](['QB2'])
    await find('VBtn', '扫描待补标签').props.onClick()
    await new Promise(resolve => setTimeout(resolve, 5))
    await settle()
    assert.equal(view.writes.filter(item => item.path === 'tag_completion_scan').length, 1)
    assert.equal(view.text().includes('扫描结果'), true)
    assert(view.text().includes('待补 2 条标签关联'))
    assert.equal(statusReads > 0, true)
    await find('VBtn', '预览补全').props.onClick()
    await settle()
    await find('VBtn', '确认补全').props.onClick()
    await new Promise(resolve => setTimeout(resolve, 5))
    await settle()
    assert.deepEqual(view.writes.filter(item => item.path.startsWith('tag_completion_')).map(item => item.path), [
      'tag_completion_scan', 'tag_completion_execute',
    ])
    assert(view.text().includes('请重新扫描核对剩余标签'))
    assert.equal(view.text().includes('扫描结果'), false)
    assert.equal(view.writes.find(item => item.path === 'tag_completion_execute').body.repairs[0].hashes, undefined)
  } finally { view.close() }
})

test('configuration navigation preserves drafts and places settings in their functional sections', async () => {
  const view = fixture('Config', { initialConfig: {} })
  try {
    await settle()
    const nav = async title => {
      const item = view.all(node => node.type === 'VListItem' && view.text(node) === title)[0]
      assert(item, `missing navigation ${title}`)
      item.props.onClick()
      await settle()
    }
    const sub = async title => {
      const button = view.all(node => node.type === 'button' && view.text(node) === title)[0]
      assert(button, `missing sub-tab ${title}`)
      button.props.onClick()
      await settle()
    }
    const shownField = field => view.all(node => node.props.label === field && view.visible(node))
    assert.equal(view.all(node => node.type === 'VTable').length, 0)
    await nav('自动删除')
    assert.equal(shownField('运行方式').length, 1)
    const interval = shownField('扫描间隔（分钟）')[0]
    interval.props['onUpdate:modelValue'](17)
    await sub('条件筛选')
    assert.equal(shownField('运行方式').length, 0)
    await nav('运行总览')
    await nav('自动删除')
    assert.equal(shownField('扫描间隔（分钟）')[0].props.modelValue, 17)
    assert(!view.reads.some(path => path.startsWith('auto_delete/history')))
    const save = view.all(node => node.type === 'VBtn' && view.text(node) === '保存配置')[0]
    assert(save)
    for (const section of ['基础设置', '条件筛选', '高级选项']) {
      await sub(section)
      assert.deepEqual(view.all(n => n.type === 'VBtn' && /^(保存自动删除设置|保存配置)$/.test(view.text(n))).map(n => view.text(n)), ['保存配置'])
    }
    await nav('运行总览')
    save.props.onClick()
    await settle()
    assert.equal(view.writes[0].path, 'auto_delete/config')
    assert.equal(view.writes[0].body.settings.interval_minutes, 17)
    assert.deepEqual(view.writes.map(item => item.path), ['auto_delete/config'])
    assert.deepEqual(view.events, [])
    assert(view.text().includes('配置已保存'))
    assert(view.all(n => n.props.class === 'dm-flow').length)
    await nav('自动删除')
    assert.equal(shownField('扫描间隔（分钟）')[0].props.modelValue, 17)
    await sub('高级选项')
    assert.equal(shownField('允许删除的下载目录').length, 1)
    assert.equal(shownField('扫描间隔（分钟）').length, 0)

    await nav('IYUU铺种')
    assert.equal(shownField('辅种下载器').length, 0)
    await sub('条件筛选')
    assert.equal(shownField('辅种下载器').length, 1)
    assert.equal(shownField('最小辅种体积（GB）').length, 1)
    assert.equal(shownField('辅种后增加标签').length, 0)
    await sub('高级选项')
    assert.equal(shownField('辅种后增加标签').length, 1)
    assert.equal(shownField('清除缓存后运行').length, 1)

    await nav('同步删除')
    assert.equal(shownField('Emby 服务器').length, 1)
    assert.equal(shownField('删除网盘文件').length, 0)
    await sub('高级选项')
    assert.equal(shownField('删除网盘文件').length, 1)
    assert.equal(shownField('Emby 服务器').length, 0)
    assert.equal(view.all(node => node.props['data-execution-history'] !== undefined).length, 0)

    await nav('转移做种')
    assert.equal(shownField('源下载器').length, 1)
    assert.equal(shownField('转移种子标签（逗号分隔）').length, 0)
    await sub('条件筛选')
    assert.equal(shownField('转移种子标签（逗号分隔）').length, 1)
    assert.equal(shownField('转移做种兜底服务').length, 0)
    await sub('高级选项')
    assert.equal(shownField('转移做种兜底服务').length, 1)

    await nav('速度监控')
    assert.equal(shownField('活跃扫描间隔（秒）').length, 1)
    assert.equal(shownField('连续异常次数').length, 0)
    await sub('条件筛选')
    assert.equal(shownField('连续异常次数').length, 1)
    assert.equal(shownField('排除分类关键词').length, 1)

    await nav('命名补刀')
    assert.equal(shownField('电影命名格式 (Jinja2)').length, 1)
    assert.equal(shownField('排除目录（每行一个）').length, 0)
    await sub('条件筛选')
    assert.equal(shownField('排除目录（每行一个）').length, 1)

    await nav('站点标签')
    assert.equal(shownField('Tracker 映射（域名 -> 映射域名）').length, 1)
    assert.equal(view.all(node => node.type === 'VSelect' && node.props.label === '下载器' && view.visible(node)).length, 0)
    const completionShortcut = view.all(node => node.type === 'VBtn' && view.text(node) === '补全标签' && view.visible(node))[0]
    assert(completionShortcut)
    completionShortcut.props.onClick()
    await settle()
    assert.equal(view.all(node => node.type === 'VSelect' && node.props.label === '下载器' && view.visible(node)).length, 1)
    assert.equal(view.text().includes('扫描待补标签'), true)
    await sub('基础设置')
    await sub('补全标签')
    assert.equal(view.all(node => node.type === 'VSelect' && node.props.label === '下载器' && view.visible(node)).length, 1)
    await sub('标签清理')
    assert.equal(view.all(node => node.type === 'VSelect' && node.props.label === '下载器' && view.visible(node)).length, 1)

    await nav('做种校验')
    assert.equal(shownField('启用自动开始做种').length, 1)
    assert.equal(shownField('跳过校验（qBittorrent 有效）').length, 0)
    await sub('高级选项')
    assert.equal(shownField('跳过校验（qBittorrent 有效）').length, 1)

    await nav('上传限速')
    assert.equal(view.all(node => node.type === 'div' && String(node.props.class || '').includes('dm-upload-config-row') && view.visible(node)).length, 0)
    await sub('条件筛选')
    assert.equal(view.text().includes('站点限速'), true)
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
})

test('overview mounts only its own panel and downloader options arrive independently', async () => {
  let finishOverview
  const view = fixture('Config', {}, { get: {
    overview: () => new Promise(resolve => { finishOverview = resolve }),
    downloaders: () => [{ title: 'Local QB', value: 'qb', type: 'qbittorrent' }],
  } })
  try {
    await settle()
    const panes = () => view.all(n => String(n.props.class || '').split(' ').includes('dm-pane'))
    assert.equal(panes().length, 1)
    assert.equal(view.all(n => n.type === 'VTextField' || n.type === 'VSelect').length, 0)
    view.all(n => n.type === 'VListItem' && view.text(n) === '转移做种')[0].props.onClick()
    await settle()
    assert.equal(panes().length, 1)
    assert.equal(view.all(n => n.props.label === '源下载器')[0].props.items[0].value, 'qb')
    finishOverview({ cards: {}, modules: [] })
    await settle()
    assert.deepEqual(view.errors, [])
  } finally { view.close() }
})

test('official and tracker mapping fields each get a full-width row', async () => {
  const view = fixture('Config')
  try {
    await settle()
    view.all(node => node.type === 'VListItem' && view.text(node) === '站点标签')[0].props.onClick()
    await settle()
    const rowFor = label => view.all(node => node.props.label === label && view.visible(node))[0].parent.parent
    for (const label of ['Tracker 映射（域名 -> 映射域名）', '官种映射（站点:制作组|制作组）']) {
      const row = rowFor(label)
      assert.match(row.props.class, /\bdm-form-grid--one\b/, label)
      assert.equal(row.children.filter(node => node.type === 'VCol').length, 1, label)
    }
    assert.equal(rowFor('启用官种标签'), rowFor('官种标签前缀'))
  } finally { view.close() }
})

test('official tag settings show real defaults and persist explicit blanks independently', async () => {
  const view = fixture('Config', { initialConfig: { tag_enabled: false } })
  try {
    await settle()
    view.all(node => node.type === 'VListItem' && view.text(node) === '站点标签')[0].props.onClick()
    await settle()
    const field = label => view.all(node => node.props.label === label && view.visible(node))[0].props
    const mappings = '官种映射（站点:制作组|制作组）'
    assert.equal(field('启用官种标签').modelValue, false)
    assert.equal(field('官种标签前缀').modelValue, '🏅')
    assert.deepEqual(field(mappings).modelValue.split('\n'), [
      '观众:Audies|ADE|ADWeb|ADAudio|ADeBook|ADMusic', '憨憨:HHWEB', '青蛙:FROG|FROGE|FROGWeb|CatEDU',
      '我堡:OurBits|OurTV', '猫站:PTerWEB|PTer|PTerMV|PTerTV', '高清杜比:QHstudIo|Dream', '朋友:FRDS',
      '猪猪:PigoWeb|PigoHD|PigoNF|PigoAD', 'Sunny:Sunny', '馒头:MTeam|MWEB',
    ])
    field('启用官种标签')['onUpdate:modelValue'](true)
    field('官种标签前缀')['onUpdate:modelValue']('')
    field(mappings)['onUpdate:modelValue']('')
    await view.all(node => node.type === 'VBtn' && view.text(node) === '保存配置')[0].props.onClick()
    assert.equal(view.writes[0].body.tag_enabled, false)
    assert.equal(view.writes[0].body.tag_official_enabled, true)
    assert.equal(view.writes[0].body.tag_official_prefix, '')
    assert.equal(view.writes[0].body.tag_official_mappings, '')
  } finally { view.close() }
})

test('saving twice uses the same instance and tab, preserves live fields and consumes one-shot actions', async () => {
  const view = fixture('Config', { initialConfig: { legacy: 'old' } }, { stored: { legacy: 'new', extra: 19 } })
  try {
    await settle()
    view.all(n => n.type === 'VListItem' && view.text(n) === '转移做种')[0].props.onClick()
    await settle()
    const once = () => view.all(n => n.props.label === '立即运行一次')[0]
    once().props['onUpdate:modelValue'](true)
    const save = () => view.all(n => n.type === 'VBtn' && view.text(n) === '保存配置')[0].props.onClick()
    const first = save()
    await save()
    await first
    await settle()
    assert.equal(view.writes.length, 1)
    assert.equal(view.writes[0].body.onlyonce, true)
    assert.equal(view.writes[0].body.legacy, 'new')
    assert.equal(view.writes[0].body.extra, 19)
    assert.equal(once().props.modelValue, false)
    await save()
    assert.equal(view.writes.length, 1)
    assert.deepEqual(view.events, [])
    view.all(n => n.type === 'VBtn' && view.text(n) === '关闭')[0].props.onClick()
    assert.deepEqual(view.events, ['close'])
  } finally { view.close() }
})

test('failed host save leaves the active draft editable and permits retry', async () => {
  let reject = true
  const view = fixture('Config', {}, { put() {
    if (reject) return { success: false, message: '测试拒绝保存' }
    return { success: true }
  } })
  try {
    await settle()
    view.all(n => n.type === 'VListItem' && view.text(n) === '速度监控')[0].props.onClick()
    await settle()
    const interval = () => view.all(n => n.props.label === '活跃扫描间隔（秒）')[0]
    interval().props['onUpdate:modelValue'](52)
    const save = () => view.all(n => n.type === 'VBtn' && view.text(n) === '保存配置')[0].props.onClick()
    await save()
    await settle()
    assert(view.text().includes('测试拒绝保存'))
    assert.equal(interval().props.modelValue, 52)
    reject = false
    await save()
    assert.equal(view.writes[1].body.speed_monitor_interval_seconds, 52)
    assert.deepEqual(view.events, [])
  } finally { view.close() }
})

test('overview opens pending detail without losing a monitor draft or issuing actions', async () => {
  const view = fixture('Config', { initialConfig: {} }, {
    modules: [{ key: 'sync_delete', title: '同步删除', state: 'attention', pending: 2 }],
  })
  try {
    await settle()
    const nav = async title => {
      view.all(node => node.type === 'VListItem' && view.text(node) === title && view.visible(node))[0].props.onClick()
      await settle()
    }
    await nav('速度监控')
    const interval = () => view.all(node => node.props.label === '活跃扫描间隔（秒）' && view.visible(node))[0]
    interval().props['onUpdate:modelValue'](71)
    await nav('运行总览')
    const review = view.all(node => node.props['data-review-module'] === 'sync_delete')[0]
    assert(review)
    review.props.onClick()
    await settle()
    assert(view.reads.some(path => path.startsWith('sync_delete/history') && path.includes('pending_only=true')))
    assert(view.text().includes('暂无待处理记录'))
    const close = view.all(node => node.type === 'VBtn' && node.props.icon === 'mdi-close' && view.visible(node))[0]
    assert(close)
    close.props.onClick()
    await settle()
    await nav('速度监控')
    assert.equal(interval().props.modelValue, 71)
    assert.deepEqual(view.writes, [])
    assert.deepEqual(view.errors, [])
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
})

test('all four sampling fields share one four-column row; same-group controls and hints stay aligned', async () => {
  const view = fixture('Config', { initialConfig: { speed_monitor_grace_minutes: 5, speed_monitor_tolerance: 2.4,
    speed_monitor_consecutive_abnormal_samples: 2, speed_monitor_min_samples: 5 } })
  try {
    await settle()
    const nav = async title => {
      view.all(node => node.type === 'VListItem' && view.text(node) === title && view.visible(node))[0].props.onClick()
      await settle()
    }
    const sub = async title => {
      view.all(node => node.type === 'button' && view.text(node) === title && view.visible(node))[0].props.onClick()
      await settle()
    }
    await nav('速度监控')
    await sub('条件筛选')
    const names = ['启动宽限（分钟）', '允许时长倍数', '连续异常次数', '可信样本门槛']
    const fields = names.map(name => view.all(node => node.props.label === name && view.visible(node))[0])
    const row = fields[0].parent.parent
    assert.equal(row.type, 'VRow')
    assert.match(String(row.props.class), /dm-form-grid--four/)
    assert.equal(row.children.filter(node => node.type === 'VCol').length, 4)
    assert(fields.every(node => node.parent.parent === row))
    assert.deepEqual(fields.map(node => node.props.modelValue), [5, 2.4, 2, 5])
    assert(fields.every(node => node.props.density === 'compact' && node.props.variant === 'outlined'))
    assert(fields.every(node => Object.hasOwn(node.props, 'hide-details')))
    assert(names.every(name => view.text(row).includes(name)))
    for (const hint of ['范围 0–1440', '必须大于 1', '范围 1–10', '范围 1–100，默认 5']) assert(view.text(row).includes(hint))
    fields[3].props['onUpdate:modelValue'](9)
    await sub('基础设置')
    await sub('条件筛选')
    assert.equal(view.all(node => node.props.label === '可信样本门槛' && view.visible(node))[0].props.modelValue, 9)
    await nav('转移做种')
    await sub('高级选项')
    const switches = ['删除源种子', '删除重复种子', '保留原分类', '保留原标签'].map(name => view.all(node => node.props.label === name && view.visible(node))[0])
    assert(switches.every(node => node.parent.parent === switches[0].parent.parent))
    assert.match(String(switches[0].parent.parent.props.class), /dm-form-grid--four/)
    assert(view.all(node => node.type === 'VRow').every(node => String(node.props.class || '').includes('dm-form-grid')))
    assert.deepEqual(view.writes, [])
    assert.deepEqual(view.errors, [])
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
})

async function openHistoryRow(view, index = 0) {
  const buttons = view.all(node => node.type === 'VBtn' && view.text(node) === '明细' && view.visible(node))
  assert(buttons[index])
  buttons[index].props.onClick()
  await settle()
}

test('history surfaces share headings, status and pagination while preserving their own records and operations', async () => {
  const renamed = { hash: 'hash', time: '2026-11-18', original_name: '原名', after_name: '新名', success: true }
  const archived = { hash: 'archived', archived_at: '2026-11-18', name: '归档任务', category: 'failed', category_label: '命名失败', fail_count: 3, reason: '旧失败原因' }
  const view = fixture('Page', {}, { renameRecords: [renamed], renameTotal: 45, archiveRecords: [archived], archiveTotal: 30 })
  try {
    await settle()
    const nav = async title => {
      view.all(node => node.type === 'VListItem' && view.text(node) === title && view.visible(node))[0].props.onClick()
      await settle()
    }
    for (const [tab, expected, length, route] of [['命名历史', '新名', 3, 'rename_history'], ['归档记录', '归档任务', 2, 'rename_archive']]) {
      await nav(tab)
      assert(view.text().includes(expected))
      const pagination = view.all(node => node.type === 'VPagination' && view.visible(node))[0]
      assert.equal(pagination.props.length, length)
      const handlers = pagination.props['onUpdate:modelValue']
      for (const handler of Array.isArray(handlers) ? handlers : [handlers]) handler(2)
      await settle()
      assert(view.reads.some(path => path.startsWith(route) && path.includes('page=2')))
      assert(view.all(node => node.type === 'h3' && String(node.props.class).includes('dm-history-title')).length)
      assert(view.all(node => node.type === 'VChip' && String(node.props.class).includes('dm-history-status')).length)
    }
    assert.deepEqual(view.writes, [])
    assert.deepEqual(view.errors, [])
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
  const auto = fixture('AutoDeletePane', { mode: 'history' })
  try {
    await settle()
    assert.equal(auto.all(node => node.props.class === 'dm-history-summary').length, 1)
    assert(!auto.text().includes('旧规则'))
    await openHistoryRow(auto)
    assert(auto.text().includes('旧任务') && auto.text().includes('旧规则'))
    const evidence = auto.all(node => node.type === 'VBtn' && auto.text(node) === '依据')[0]
    evidence.props.onClick()
    await settle()
    assert(auto.text().includes('命中依据'))
    assert.deepEqual(auto.writes, [])
    assert.deepEqual(auto.errors, [])
  } finally { auto.close() }
})

test('sync deletion renders one compact row per job; expanded details preserve targets and issue no writes', async () => {
  const job = { ...unstartedJob(), event: { name: '旧媒体', paths: ['/library/episode.strm'], original_paths: ['/old-library/episode.strm'] },
    plan: { source_files: [{ storage: 'local', path: '/downloads/episode.mkv', status: 'absent' }],
      cloud_files: [{ storage: 'cloud', path: '/cloud/episode.mkv', status: 'deleted' }],
      tasks: [{ downloader: 'QB', id: 'old-hash', status: 'paused' }], records: [{ id: 1 }], download_records: [{ id: 2 }] },
    records_done: [1], download_records_done: [2], review: { retry_allowed: false, dismiss_allowed: false, retry_reason: '旧快照不可重试' },
  }
  const view = fixture('SyncDeletePane', { mode: 'history' }, { jobs: [job] })
  try {
    await settle()
    const row = view.all(node => node.props['data-sync-record'] === 'old')[0]
    assert.equal(view.all(node => node.props.class === 'dm-history-summary', row).length, 1)
    assert(view.text(row).includes('旧媒体'))
    assert(!view.text(row).includes('关联任务已不存在，无需删除'))
    const details = view.all(node => node.type === 'VBtn' && view.text(node) === '明细', row)[0]
    details.props.onClick()
    await settle()
    const expanded = view.all(node => node.props['data-sync-detail'] === 'old')[0]
    assert(expanded)
    for (const text of ['事件路径 · /library/episode.strm', '历史源路径 · /old-library/episode.strm',
      '已不存在 · local · /downloads/episode.mkv', '已删除 · cloud · /cloud/episode.mkv',
      '保留并暂停 · QB · old-hash', '整理记录已处理 1 / 1', '旧下载记录已标记 1 / 1']) assert(view.text(expanded).includes(text), text)
    assert(view.text(row).includes('关联任务已不存在，无需删除'))
    view.all(node => node.type === 'VBtn' && view.text(node) === '收起', row)[0].props.onClick()
    await settle()
    assert(!view.all(node => node.props['data-sync-detail'] === 'old').length)
    assert.deepEqual(view.writes, [])
    assert.deepEqual(view.errors, [])
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
})

test('long names and failure reasons remain readable in the selected row across history tabs', async () => {
  const reason = '这是不能挤进状态标签的完整失败原因，需要保持可以阅读'
  const name = 'Twisted.Tie.'.repeat(24) + '.mkv'
  const view = fixture('Page', {}, {
    renameRecords: [{ hash: 'first', original_name: '短名', success: true }, { hash: 'second', original_name: name, success: false, reason }],
    archiveRecords: [{ hash: 'second', name, category_label: '未归类异常', fail_count: 3, reason }],
    get: { diagnostics: () => ({ rename_history: { recent_failures: [{ hash: 'second', name, reason }] } }) },
  })
  try {
    await settle()
    for (const [tab, status, count] of [['命名历史', '失败', 2], ['归档记录', '未归类异常', 1], ['运行诊断', '失败', 1]]) {
      view.all(node => node.type === 'VListItem' && view.text(node) === tab && view.visible(node))[0].props.onClick()
      await settle()
      const rows = view.all(node => node.props.class === 'dm-history-summary' && view.visible(node))
      assert.equal(rows.length, count)
      const row = rows[count - 1]
      assert.equal(view.all(node => node.props.class === 'dm-history-name', row)[0].props.title, name)
      assert.equal(view.text(view.all(node => node.type === 'VChip', row)[0]), status)
      assert(!view.text().includes(reason))
      await openHistoryRow(view, count - 1)
      const expanded = view.all(node => node.props.class === 'dm-history-expanded')
      assert.equal(expanded.length, 1)
      assert(view.text(expanded[0]).includes(name))
      assert(view.text(expanded[0]).includes(reason))
    }
    assert.deepEqual(view.writes, [])
    assert.deepEqual(view.errors, [])
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
})

const unstartedJob = () => ({ id: 'old', state: 'failed', event: { name: '旧媒体', paths: ['/emby/old.strm'] },
  error: '关联任务已不存在，无需删除', plan: null,
  review: { revision: 'a'.repeat(64), retry_allowed: false, retry_reason: '旧配置已变化', dismiss_allowed: true } })

test('ignore immediately removes the reminder without a reason or dialog; read-only access writes nothing', async () => {
  const jobs = [unstartedJob()]
  const view = fixture('SyncDeletePane', { mode: 'history', initialPendingOnly: true }, { jobs,
    post: async (_path, body) => { jobs[0].state = 'dismissed'; return { job_id: body.job_id, state: 'dismissed' } },
  })
  try {
    await settle()
    const button = title => view.all(node => node.type === 'VBtn' && view.text(node) === title && view.visible(node))[0]
    await openHistoryRow(view)
    assert.equal(button('核验后重试').props.disabled, true)
    assert(view.text().includes('无法重试：旧配置已变化'))
    assert(!view.text().includes('结束处理'))
    assert(!view.all(node => node.props.label === '结束原因').length)
    await button('忽略').props.onClick()
    await settle()
    assert.deepEqual(view.writes, [{ path: 'sync_delete/dismiss', body: {
      job_id: 'old', expected_revision: 'a'.repeat(64),
    } }])
    assert(view.text().includes('暂无待处理记录'))
    assert(view.text().includes('已忽略，历史记录保留'))
    assert(!button('确认重试'))
    const filter = view.all(node => node.props.label === '仅待处理' && view.visible(node))[0]
    const filterHandlers = filter.props['onUpdate:modelValue']
    for (const handler of Array.isArray(filterHandlers) ? filterHandlers : [filterHandlers]) handler(false)
    await settle()
    assert(view.text().includes('已忽略'))
    await openHistoryRow(view)
    assert(view.text().includes('原失败原因：关联任务已不存在，无需删除'))
    assert(!button('忽略'))
    assert.deepEqual(view.errors, [])
    assert.deepEqual(view.warnings, [])
  } finally { view.close() }
  const readonly = fixture('SyncDeletePane', { mode: 'history', canManage: false }, { jobs: [unstartedJob()] })
  try {
    await settle()
    await openHistoryRow(readonly)
    const end = readonly.all(node => node.type === 'VBtn' && readonly.text(node) === '忽略')[0]
    assert.equal(end.props.disabled, true)
    end.props.onClick()
    await settle()
    assert.deepEqual(readonly.writes, [])
    assert(!readonly.text().includes('确认结束'))
  } finally { readonly.close() }
})

test('duplicate ignore cannot send a second request and late result cannot report success in a new instance', async () => {
  let resolveAction
  const view = fixture('SyncDeletePane', { mode: 'history' }, { jobs: [unstartedJob()],
    post: () => new Promise(resolve => { resolveAction = resolve }),
  })
  try {
    await settle()
    const button = title => view.all(node => node.type === 'VBtn' && view.text(node) === title && view.visible(node))[0]
    await openHistoryRow(view)
    const ignore = button('忽略')
    const action = ignore.props.onClick()
    await ignore.props.onClick()
    await settle()
    assert.equal(view.writes.length, 1)
    view.props.pluginId = 'NewInstance'
    await settle()
    assert.equal(view.all(node => node.props.class === 'dm-history-expanded').length, 0)
    resolveAction({ job_id: 'old', state: 'dismissed' })
    await action
    await settle()
    assert(!view.text().includes('已忽略，历史记录保留'))
    assert(!view.text().includes('确认结束'))
    assert.deepEqual(view.errors, [])
  } finally { view.close() }
})

test('rejected ignore keeps the reminder visible and exposes the failure', async () => {
  const view = fixture('SyncDeletePane', { mode: 'history', initialPendingOnly: true }, { jobs: [unstartedJob()],
    post: async () => { throw new Error('记录已变化，请刷新后重试') },
  })
  try {
    await settle()
    await openHistoryRow(view)
    const button = view.all(node => node.type === 'VBtn' && view.text(node) === '忽略' && view.visible(node))[0]
    await button.props.onClick()
    await settle()
    assert(view.text().includes('记录已变化，请刷新后重试'))
    assert(view.text().includes('旧媒体'))
    assert(!view.text().includes('已忽略，历史记录保留'))
    assert.equal(button.props.disabled, false)
    assert.deepEqual(view.errors, [])
  } finally { view.close() }
})

for (const name of ['Config', 'Page']) {
  test(`${name} waits for permission evidence and only shows read-only after an explicit denial`, async () => {
    const pending = []
    const view = fixture(name, { initialConfig: {} }, { permissions: () => new Promise(resolve => pending.push(resolve)) })
    try {
      const status = () => view.all(node => node.props['data-permission-status'] && view.visible(node))[0]
      assert.equal(status().props['data-permission-status'], 'loading')
      assert(view.text().includes('正在核验管理权限'))
      assert(!view.text().includes('当前登录身份没有管理权限'))
      pending.shift()({ can_manage: false })
      await settle()
      assert.equal(status().props['data-permission-status'], 'denied')
      assert(view.text().includes('当前登录身份没有管理权限'))
      const retry = view.all(node => node.type === 'VBtn' && view.text(node) === '重新检查' && view.visible(node))[0]
      const request = retry.props.onClick()
      await settle()
      assert.equal(status().props['data-permission-status'], 'loading')
      pending.shift()({ can_manage: true })
      await request
      await settle()
      assert.equal(status(), undefined)
      assert(!view.text().includes('只读模式'))
      assert.deepEqual(view.writes, [])
      assert.deepEqual(view.errors, [])
    } finally { view.close() }
  })

  test(`${name} treats cancellation and malformed permission response as errors and ignores old grants`, async () => {
    const pending = []
    const view = fixture(name, { initialConfig: {} }, { permissions: (_client, id) => new Promise((resolve, reject) => pending.push({ id, resolve, reject })) })
    try {
      const status = () => view.all(node => node.props['data-permission-status'] && view.visible(node))[0]
      view.props.pluginId = 'NewInstance'
      await settle()
      pending.shift().resolve({ can_manage: true })
      await settle()
      assert.equal(status().props['data-permission-status'], 'loading')
      const cancellation = new Error('cancelled')
      cancellation.name = 'AbortError'
      pending.shift().reject(cancellation)
      await settle()
      assert.equal(status().props['data-permission-status'], 'error')
      assert(view.text().includes('权限核验'))
      assert(!view.text().includes('当前登录身份没有管理权限'))
      const retry = () => view.all(node => node.type === 'VBtn' && view.text(node) === '重新检查' && view.visible(node))[0]
      const invalid = retry().props.onClick()
      pending.shift().resolve({ can_manage: 'true' })
      await invalid
      await settle()
      assert.equal(status().props['data-permission-status'], 'error')
      assert(view.text().includes('身份核验失败'))
      const success = retry().props.onClick()
      pending.shift().resolve({ can_manage: true })
      await success
      await settle()
      assert.equal(status(), undefined)
      assert.deepEqual(view.writes, [])
      assert.deepEqual(view.errors, [])
    } finally { view.close() }
  })

  test(`${name} exits loading when its permission request never returns and can retry`, async () => {
    let responds = false
    const view = fixture(name, { initialConfig: {} }, { permissionTimeoutMs: 15,
      permissions: () => responds ? Promise.resolve({ can_manage: true }) : new Promise(() => {}),
    })
    try {
      await new Promise(resolve => setTimeout(resolve, 35))
      await settle()
      const status = view.all(node => node.props['data-permission-status'] && view.visible(node))[0]
      assert.equal(status.props['data-permission-status'], 'error')
      assert(view.text().includes('权限核验超时'))
      assert(!view.text().includes('正在核验管理权限'))
      responds = true
      await view.all(node => node.type === 'VBtn' && view.text(node) === '重新检查' && view.visible(node))[0].props.onClick()
      await settle()
      assert(!view.all(node => node.props['data-permission-status'] && view.visible(node)).length)
      assert(view.reads.filter(path => path === 'user/current').length >= 2)
      assert(!view.reads.some(path => path === 'permissions'))
      assert.deepEqual(view.writes, [])
    } finally { view.close() }
  })
}


test('configuration arrives before slow status and shares the parent downloader request', async () => {
  let finishStatus
  const view = fixture('Config', {}, { get: {
    'auto_delete/status': () => new Promise(resolve => { finishStatus = resolve }),
  } })
  try {
    await settle()
    view.all(n => n.type === 'VListItem' && view.text(n) === '自动删除')[0].props.onClick()
    await settle()
    assert.equal(view.all(n => n.props.label === '扫描间隔（分钟）')[0].props.modelValue, 5)
    assert.equal(view.reads.filter(path => path === 'downloaders').length, 1)
    finishStatus({ active: false })
    await settle()
  } finally { view.close() }
})

test('edits typed during a host save survive its readback and can be saved again', async () => {
  let release
  let stored = {}
  const view = fixture('Config', {}, { get: { '': () => structuredClone(stored) },
    async put(_path, body) {
      await new Promise(resolve => { release = resolve })
      stored = structuredClone(body)
      return { success: true }
    } })
  try {
    await settle()
    view.all(n => n.type === 'VListItem' && view.text(n) === '速度监控')[0].props.onClick()
    await settle()
    const field = () => view.all(n => n.props.label === '活跃扫描间隔（秒）')[0]
    const save = () => view.all(n => n.type === 'VBtn' && view.text(n) === '保存配置')[0].props.onClick()
    field().props['onUpdate:modelValue'](52)
    const saving = save()
    await settle()
    field().props['onUpdate:modelValue'](61)
    release()
    await saving
    await settle()
    assert.equal(stored.speed_monitor_interval_seconds, 52)
    assert.equal(field().props.modelValue, 61)
    assert(view.text().includes('还有新修改待保存'))
    const savingAgain = save()
    await settle()
    release()
    await savingAgain
    assert.equal(stored.speed_monitor_interval_seconds, 61)
  } finally { view.close() }
})
