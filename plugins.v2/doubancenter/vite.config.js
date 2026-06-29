import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'
import { rmSync } from 'node:fs'

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
    {
      name: 'remove-unused-vuetify-shared-styles',
      closeBundle() {
        rmSync('dist/assets/__federation_shared_vuetify', { recursive: true, force: true })
      },
    },
  ],
  build: {
    target: 'esnext',
    minify: false,
    cssCodeSplit: true,
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
