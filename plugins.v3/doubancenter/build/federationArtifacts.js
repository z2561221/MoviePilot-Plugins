import { createHash } from 'node:crypto'
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, renameSync, unlinkSync, writeFileSync } from 'node:fs'
import { dirname, isAbsolute, posix, relative, resolve } from 'node:path'

const sha256 = value => createHash('sha256').update(value).digest('hex')
const ordered = entries => [...entries].sort(([left], [right]) => Buffer.compare(Buffer.from(left), Buffer.from(right)))

function normalizedPath(name) {
  if (typeof name !== 'string' || !name || name.includes('\\') || name.includes(':') || isAbsolute(name)
      || name.split('/').some(part => !part || part === '.' || part === '..')) {
    throw new Error(`Invalid federation asset path: ${name}`)
  }
  return name
}

function inside(root, name) {
  if (existsSync(root) && lstatSync(root).isSymbolicLink()) throw new Error('Federation output root is a link')
  const path = resolve(root, normalizedPath(name))
  const suffix = relative(root, path)
  if (!suffix || isAbsolute(suffix) || suffix.startsWith('..')) throw new Error('Federation output escaped its root')
  let cursor = root
  for (const part of suffix.split(/[\\/]/)) {
    cursor = resolve(cursor, part)
    if (existsSync(cursor) && lstatSync(cursor).isSymbolicLink()) throw new Error('Federation output contains a link')
  }
  return path
}

function localReference(name, reference, files) {
  if (/^(?:[a-z][\w+.-]*:|\/\/|\/|#)/i.test(reference)) return
  const plain = reference.split(/[?#]/, 1)[0]
  if (!plain) return
  const target = posix.normalize(posix.join(posix.dirname(name), plain))
  normalizedPath(target)
  if (!files.has(target)) throw new Error(`Missing federation asset: ${name} -> ${reference}`)
}

export function validatePayload(files) {
  if (!files.has('remoteEntry.js')) throw new Error('Federation entry is missing')
  for (const [name, bytes] of files) {
    normalizedPath(name)
    const text = bytes.toString('utf8')
    if (name.endsWith('.js') || name.endsWith('.mjs')) {
      for (const match of text.matchAll(/['"](\.\.?\/[^'"]+\.(?:m?js|css|png|jpe?g|gif|svg|webp|avif|woff2?)(?:[?#][^'"]*)?)['"]/g)) {
        localReference(name, match[1], files)
      }
      for (const match of text.matchAll(/dynamicLoadingCss\(\s*(\[[^\]]*\])/g)) {
        for (const reference of JSON.parse(match[1])) localReference(name, reference, files)
      }
    }
    if (name.endsWith('.css')) {
      for (const match of text.matchAll(/url\(\s*['"]?([^'"\s)]+)['"]?\s*\)/g)) localReference(name, match[1], files)
    }
  }
}

function atomicWrite(root, name, bytes) {
  const destination = inside(root, name)
  mkdirSync(dirname(destination), { recursive: true })
  const temporary = inside(root, `${name}.tmp`)
  writeFileSync(temporary, bytes)
  renameSync(temporary, destination)
}

export function packageFederationAssets(outputDir, emittedNames) {
  const output = resolve(outputDir)
  const files = new Map()
  for (const name of emittedNames) {
    normalizedPath(name)
    // index及Vuetify样式由既有清理钩子移除；不把旧revision或旧hash纳入新payload。
    if (name === 'index.html' || name.startsWith('assets/__federation_shared_vuetify/')) continue
    if (!name.startsWith('assets/')) throw new Error(`Federation asset is outside assets/: ${name}`)
    const asset = inside(output, name)
    if (!existsSync(asset) || !lstatSync(asset).isFile()) throw new Error(`Emitted asset is missing: ${name}`)
    files.set(name.slice('assets/'.length), readFileSync(asset))
  }
  validatePayload(files)
  const hashes = ordered([...files].map(([name, bytes]) => [name, sha256(bytes)]))
  const revision = sha256(Buffer.from(JSON.stringify(hashes)))
  const assetRoot = resolve(output, 'assets')
  const revisionName = `r${revision}`
  const destination = inside(assetRoot, revisionName)
  if (existsSync(destination)) {
    for (const [name, bytes] of files) {
      if (!readFileSync(inside(destination, name)).equals(bytes)) throw new Error('Existing content revision differs')
    }
  } else {
    const staging = mkdtempSync(inside(assetRoot, '.revision-'))
    for (const [name, bytes] of files) {
      const path = inside(staging, name)
      mkdirSync(dirname(path), { recursive: true })
      writeFileSync(path, bytes)
    }
    // 已核对源和目标均在本次输出assets内；完整目录就绪后才发布路径。
    inside(assetRoot, relative(assetRoot, staging).replaceAll('\\', '/'))
    inside(assetRoot, revisionName)
    renameSync(staging, destination)
  }
  const manifest = { schema_version: 1, revision, path: `dist/assets/${revisionName}`, files: Object.fromEntries(hashes) }
  // 兼容根入口仅影响未缓存的新读取；不能刷新已缓存的旧入口。
  atomicWrite(output, 'assets/remoteEntry.js', Buffer.from(
    `export { get, init, dynamicLoadingCss } from './${revisionName}/remoteEntry.js';\n`,
  ))
  atomicWrite(output, 'federation.json', Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`))
  // 发布完成后只移除本次已写入revision的原始生成文件，保留不属于本次输出的文件。
  for (const name of files.keys()) {
    if (name !== 'remoteEntry.js') unlinkSync(inside(assetRoot, name))
  }
  return manifest
}
