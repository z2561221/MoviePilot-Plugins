const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const { resolve } = require('node:path')
const frontend = resolve(__dirname, '../../../plugins.v3/downloadmanagerlocal/frontend')
const compiler = createRequire(resolve(frontend, 'package.json'))('vue/compiler-sfc')

test('history summaries reserve exactly two lines at every width, clamping only summary text', () => {
  const source = readFileSync(resolve(frontend, 'src/components/history-layout.css'), 'utf8')
  const compiled = compiler.compileStyle({ source, filename: 'history-layout.css', id: 'history-test' })
  assert.deepEqual(compiled.errors, [])
  const rules = []
  compiled.rawResult.root.walkRules(rule => {
    rules.push({ selector: rule.selector, parent: rule.parent, values: Object.fromEntries(rule.nodes.map(node => [node.prop, node.value])) })
  })
  const summary = rules.find(rule => rule.selector === '.dm-history-summary' && rule.parent.type === 'root').values
  assert.equal(summary.display, 'grid')
  assert.equal(summary.height, (2 * Number(summary['line-height'])) + 'em')
  const narrow = rules.find(rule => rule.selector === '.dm-history-summary' && rule.parent.name === 'container').values
  assert(narrow['grid-template-columns'].includes('minmax(0, 1fr)'))
  assert.equal(narrow.height, undefined)
  const name = rules.find(rule => rule.selector.split(', ').includes('.dm-history-name')).values
  assert.equal(name['-webkit-line-clamp'], '2')
  assert.equal(name['-webkit-box-orient'], 'vertical')
  assert.equal(name.overflow, 'hidden')
  assert.equal(name['overflow-wrap'], 'anywhere')
  const details = rules.find(rule => rule.selector === '.dm-history-expanded').values
  assert.equal(details.height, undefined)
  assert.equal(details['overflow-wrap'], 'anywhere')
})
