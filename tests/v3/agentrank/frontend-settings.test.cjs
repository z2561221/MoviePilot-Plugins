/* Mount the production settings button and its actual host prop declaration. */
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { createRequire } = require('node:module')

const plugin = path.basename(__dirname)
const root = path.resolve(__dirname, '../../../plugins.v3', plugin)
const frontend = plugin === 'doubancenter' ? root : path.join(root, 'frontend')
const requireFrontend = createRequire(path.join(frontend, 'package.json'))
const vue = requireFrontend('vue')
const compiler = requireFrontend('vue/compiler-sfc')
const source = fs.readFileSync(path.join(frontend, 'src/components/Page.vue'), 'utf8')
const parsed = compiler.parse(source)
assert.deepEqual(parsed.errors, [])
const completeScript = compiler.compileScript(parsed.descriptor, { id: 'settings-contract' })
assert.deepEqual(compiler.compileTemplate({ source: parsed.descriptor.template.content,
  filename: 'Page.vue', id: 'settings-contract',
  compilerOptions: { bindingMetadata: completeScript.bindings } }).errors, [])

// Keep the production expression/event intact; isolate unrelated data panes and requests.
const propDeclaration = parsed.descriptor.scriptSetup.content.match(/const props = defineProps\(\{[\s\S]*?\n\}\)/)[0]
const settingsButton = parsed.descriptor.template.content.match(/<VBtn\b[^>]*@click="emit\('switch'[^>]*?(?:\/>|>[\s\S]*?<\/VBtn>)/)[0]
const focused = compiler.parse(`<script setup>${propDeclaration}
const emit = defineEmits(['switch'])
const canManage = permission
const state = { options: { value: { config: { retained: true } } } }
</script><template>${settingsButton}</template>`).descriptor
const compiled = compiler.compileScript(focused, { id: 'settings-button', inlineTemplate: true }).content
  .replace(/import\s*\{([\s\S]*?)\}\s*from\s*["']vue["'];?/g,
    (_match, names) => `const { ${names.replace(/\bas\b/g, ':')} } = vue`)
  .replace('export default', 'return')

function fixture(input = {}, permission = true) {
  const element = type => ({ type, props: {}, children: [], parent: null })
  const renderer = vue.createRenderer({
    createElement: element, createText: text => ({ ...element('#text'), text }),
    createComment: text => ({ ...element('#comment'), text }),
    insert(node, parent, anchor) {
      if (node.parent) this.remove(node)
      const index = anchor ? parent.children.indexOf(anchor) : -1
      parent.children.splice(index < 0 ? parent.children.length : index, 0, node)
      node.parent = parent
    },
    remove(node) {
      if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
      node.parent = null
    },
    setText(node, text) { node.text = text },
    setElementText(node, text) { node.text = text; node.children = [] },
    patchProp(node, key, _old, value) { node.props[key] = value },
    parentNode: node => node.parent,
    nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
  })
  const component = new Function('vue', 'permission', compiled)(vue, permission)
  const props = vue.reactive(input), events = [], container = element('root')
  const app = renderer.createApp({ render: () => vue.h(component, {
    ...props, onSwitch: (...args) => events.push(args),
  }) })
  app.component('VBtn', { props: ['disabled'], setup(button, { attrs, slots }) {
    return () => vue.h('button', { ...attrs, disabled: button.disabled }, slots.default?.())
  } })
  app.component('VIcon', { render: () => null })
  app.mount(container)
  function buttons(node = container) {
    return [...(node.type === 'button' ? [node] : []), ...node.children.flatMap(buttons)]
  }
  return { props, events, buttons, unmount: () => app.unmount() }
}

test('host shortcut hides settings while normal/legacy entry keeps its switch event', async () => {
  for (const input of [{ show_switch: false }, { show_switch: true }, {}]) {
    const view = fixture(input)
    try {
      assert.equal(view.buttons().length, input.show_switch === false ? 0 : 1)
      if (view.buttons().length) {
        view.buttons()[0].props.onClick()
        assert.equal(view.events.length, 1)
        if (plugin === 'agentrank') assert.deepEqual(view.events[0], [{ retained: true }])
      }
      view.props.show_switch = false
      await vue.nextTick()
      assert.equal(view.buttons().length, 0)
      view.props.show_switch = true
      await vue.nextTick()
      assert.equal(view.buttons().length, 1)
    } finally { view.unmount() }
  }
})

if (['downloadmanagerlocal', 'doubancenter'].includes(plugin)) {
  test('normal settings entry retains the existing management permission boundary', () => {
    for (const permission of [false, true]) {
      const view = fixture({ show_switch: true }, permission)
      try { assert.equal(view.buttons()[0].props.disabled, !permission) }
      finally { view.unmount() }
    }
  })
}

if (plugin === 'doubancenter') {
  test('sidebar settings opt-in remains required and cannot override host switch=false', () => {
    for (const [input, count] of [
      [{ appPage: true }, 0],
      [{ appPage: true, showSettings: true }, 1],
      [{ appPage: true, showSettings: true, show_switch: false }, 0],
      [{ appPage: false, showSettings: false }, 1],
    ]) {
      const view = fixture(input)
      try { assert.equal(view.buttons().length, count) }
      finally { view.unmount() }
    }
  })
}
