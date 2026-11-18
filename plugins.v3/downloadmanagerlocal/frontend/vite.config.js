import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'
import { existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { packageFederationAssets } from './scripts/federationArtifacts.js'

function cleanFederationArtifacts() {
  let outputDir
  let emittedNames = []
  return {
    name: 'clean-federation-artifacts',
    configResolved(config) {
      outputDir = resolve(config.root, config.build.outDir)
    },
    writeBundle(_options, bundle) {
      emittedNames = Object.keys(bundle)
    },
    closeBundle() {
      if (!outputDir) return
      rmSync(resolve(outputDir, 'assets/__federation_shared_vuetify'), {
        recursive: true,
        force: true,
      })
      const remoteEntryPath = resolve(outputDir, 'assets/remoteEntry.js')
      if (existsSync(remoteEntryPath)) {
        const remoteEntry = readFileSync(remoteEntryPath, 'utf8').replace(/[ \t]+(?=\r?$)/gm, '')
        writeFileSync(remoteEntryPath, remoteEntry, 'utf8')
      }
      packageFederationAssets(outputDir, emittedNames)
    },
  }
}

export default defineConfig({
  plugins: [vue(), federation({
    name: 'DownloadManagerLocalV317', filename: 'remoteEntry.js',
    exposes: { './Config': './src/components/Config.vue', './Page': './src/components/Page.vue' },
    shared: {
      vue: { requiredVersion: false, generate: false },
      vuetify: { requiredVersion: false, generate: false, singleton: true },
      'vuetify/styles': { requiredVersion: false, generate: false, singleton: true },
    }, format: 'esm',
  }), cleanFederationArtifacts()],
  build: { target: 'esnext', minify: false, cssCodeSplit: true, outDir: '../dist', emptyOutDir: false },
  css: { postcss: { plugins: [
    { postcssPlugin: 'internal:charset-removal', AtRule: { charset: atRule => { if (atRule.name === 'charset') atRule.remove() } } },
    { postcssPlugin: 'vuetify-filter', Root(root) {
      const sourcePath = root.source?.input?.file?.replaceAll('\\', '/') || ''
      if (sourcePath.includes('/node_modules/vuetify/') || sourcePath.includes('/node_modules/@mdi/')) {
        root.nodes = []
        return
      }
      root.walkRules(rule => { if (rule.selector && !rule.selector.includes('.dm-') && (rule.selector.includes('.v-') || rule.selector.includes('.mdi-'))) { rule.remove() } })
    } },
  ]}},
})
