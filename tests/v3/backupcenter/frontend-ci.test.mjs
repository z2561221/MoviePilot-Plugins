import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const root = new URL('../../../', import.meta.url)
const workflow = readFileSync(new URL('.github/workflows/plugin-gate.yml', root), 'utf8')
const releaseJob = workflow.split('  plugin-release-gate:')[1].split(/\n  [\w-]+:/)[0]
const frontend = new URL('plugins.v3/backupcenter/frontend/', root)

function installStep() {
  const match = releaseJob.match(/      - name: Install BackupCenter frontend test dependencies\n([\s\S]*?)(?=\n      - name:|$)/)
  assert.ok(match, 'The routing gate needs BackupCenter dependencies before loading its restore tests')
  return match[1]
}

test('the routing gate bootstraps pnpm and BackupCenter dependencies before running tests', () => {
  const node = releaseJob.indexOf('uses: actions/setup-node@')
  const pnpm = releaseJob.indexOf('uses: pnpm/action-setup@')
  const install = releaseJob.indexOf('- name: Install BackupCenter frontend test dependencies')
  const tests = releaseJob.indexOf('run: node --test tests/v3/*/*.test.mjs')
  assert.ok(node >= 0 && pnpm > node, 'pnpm must run with the configured Node version')
  assert.ok(install > pnpm && tests > install, 'Dependencies must be installed in the routing job before its test glob')
  assert.match(releaseJob.slice(pnpm, install), /version:\s*['"]?10['"]?\s*\n/)
})

test('the dependency step uses the existing frozen lock without running install scripts', () => {
  const step = installStep()
  assert.match(step, /working-directory: plugins\.v3\/backupcenter\/frontend/)
  assert.match(step, /run: pnpm install\b/)
  assert.match(step, /--frozen-lockfile\b/)
  assert.match(step, /--ignore-scripts\b/)
})

test('Vue required by restore regressions is declared and pinned in the checked-in pnpm lock', () => {
  const manifest = JSON.parse(readFileSync(new URL('package.json', frontend), 'utf8'))
  const lock = readFileSync(new URL('pnpm-lock.yaml', frontend), 'utf8')
  const vue = lock.match(/\n      vue:\n        specifier: ([^\n]+)\n        version: ([^\n]+)/)
  assert.ok(vue, 'The existing importer must pin Vue for a clean checkout')
  assert.equal(vue[1], manifest.dependencies.vue)
  assert.match(vue[2], /^\d+\.\d+\.\d+/)
})
