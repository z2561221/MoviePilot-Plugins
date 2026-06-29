import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'
import { rmSync } from 'node:fs'
import { resolve } from 'node:path'

function removeUnreferencedSharedStyles() {
  return {
    name: 'remove-unreferenced-shared-styles',
    closeBundle() {
      rmSync(resolve('dist/assets/__federation_shared_vuetify'), { recursive: true, force: true })
    },
  }
}

export default defineConfig({
  plugins: [
    vue(),
    federation({
      name: 'DoubanCenter',
      filename: 'remoteEntry.js',
      exposes: {
        './Config': './src/components/Config.vue',
        './Page': './src/components/Page.vue',
        './Dashboard': './src/components/Dashboard.vue',
      },
      shared: {
        vue: { requiredVersion: false, generate: false, import: false },
        vuetify: { requiredVersion: false, generate: false, singleton: true, import: false },
        'vuetify/styles': { requiredVersion: false, generate: false, singleton: true, import: false },
      },
      format: 'esm',
    }),
    removeUnreferencedSharedStyles(),
  ],
  build: {
    target: 'esnext',
    minify: false,
    cssCodeSplit: true,
    outDir: 'dist',
    emptyOutDir: true,
  },
  css: {
    postcss: {
      plugins: [
        {
          postcssPlugin: 'internal:charset-removal',
          AtRule: {
            charset: atRule => {
              if (atRule.name === 'charset') atRule.remove()
            },
          },
        },
        {
          postcssPlugin: 'vuetify-filter',
          Root(root) {
            root.walkRules(rule => {
              if (rule.selector && (rule.selector.includes('.v-') || rule.selector.includes('.mdi-'))) {
                rule.remove()
              }
            })
          },
        },
      ],
    },
  },
})
