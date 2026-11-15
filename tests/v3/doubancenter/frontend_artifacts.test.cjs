const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { pathToFileURL } = require('node:url')

const root = path.resolve(__dirname, '../../../plugins.v3/doubancenter')
const packer = import(pathToFileURL(path.join(root, 'build/federationArtifacts.js')).href)

function payload(folder, extra = {}) {
  const files = {
    'remoteEntry.js': "export const init = () => {}; export const get = () => import('./view.js');\n",
    'view.js': "export const image = new URL('./images/film.svg', import.meta.url);\n",
    'view.css': "a { background: url('./images/film.svg'); }\n",
    'images/film.svg': '<svg></svg>', ...extra,
  }
  for (const [name, text] of Object.entries(files)) {
    const target = path.join(folder, 'assets', name)
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.writeFileSync(target, text)
  }
  return Object.keys(files).map(name => 'assets/' + name)
}

test('同payload在独立目录/发射顺序打包得到同revision，变更图片内容改变入口', async () => {
  const { packageFederationAssets } = await packer
  const first = fs.mkdtempSync(path.join(process.env.TEMP, 'dc-pack-one-'))
  const second = fs.mkdtempSync(path.join(process.env.TEMP, 'dc-pack-two-'))
  const changed = fs.mkdtempSync(path.join(process.env.TEMP, 'dc-pack-changed-'))
  const left = packageFederationAssets(first, payload(first))
  const right = packageFederationAssets(second, payload(second).reverse())
  assert.deepEqual(left, right)
  assert.equal(fs.readFileSync(path.join(first, 'federation.json'), 'utf8'), fs.readFileSync(path.join(second, 'federation.json'), 'utf8'))
  const next = packageFederationAssets(changed, payload(changed, { 'images/film.svg': '<svg>changed</svg>' }))
  assert.notEqual(left.revision, next.revision)
  const revision = 'r' + left.revision
  assert.match(fs.readFileSync(path.join(first, 'assets/remoteEntry.js'), 'utf8'), new RegExp(revision))
  assert(fs.existsSync(path.join(first, 'assets', revision, 'images/film.svg')))
  assert(!fs.existsSync(path.join(first, 'assets/view.js')))
})

test('引用缺失拒绝发布清单，旧指针与资产保留', async () => {
  const { packageFederationAssets } = await packer
  const output = fs.mkdtempSync(path.join(process.env.TEMP, 'dc-pack-invalid-'))
  const names = payload(output)
  fs.writeFileSync(path.join(output, 'federation.json'), 'prior manifest')
  fs.writeFileSync(path.join(output, 'assets/view.css'), "a { background: url('./missing.png'); }")
  assert.throws(() => packageFederationAssets(output, names), /Missing federation asset/)
  assert.equal(fs.readFileSync(path.join(output, 'federation.json'), 'utf8'), 'prior manifest')
  assert(fs.existsSync(path.join(output, 'assets/view.js')))
})

test('只打包本次发射文件，旧文件不改变摘要、不被误删', async () => {
  const { packageFederationAssets } = await packer
  const output = fs.mkdtempSync(path.join(process.env.TEMP, 'dc-pack-existing-'))
  const clean = fs.mkdtempSync(path.join(process.env.TEMP, 'dc-pack-clean-'))
  const names = payload(output)
  fs.writeFileSync(path.join(output, 'assets/unrelated.js'), 'previous output')
  const actual = packageFederationAssets(output, names)
  const expected = packageFederationAssets(clean, payload(clean))
  assert.deepEqual(actual, expected)
  assert.equal(fs.readFileSync(path.join(output, 'assets/unrelated.js'), 'utf8'), 'previous output')
})

test('发射路径越界不能进入构建清单', async () => {
  const { packageFederationAssets } = await packer
  const output = fs.mkdtempSync(path.join(process.env.TEMP, 'dc-pack-path-'))
  assert.throws(() => packageFederationAssets(output, ['assets/../outside.js']), /Invalid federation asset path/)
  assert.throws(() => packageFederationAssets(output, ['assets\\outside.js']), /Invalid federation asset path/)
})
