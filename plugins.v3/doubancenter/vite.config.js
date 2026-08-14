import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'
import { readFileSync, rmSync, writeFileSync } from 'node:fs'

function cleanFederationArtifacts() {
  return {
    name: 'clean-federation-artifacts',
    closeBundle() {
      rmSync(new URL('./dist/index.html', import.meta.url), { force: true })
      rmSync(new URL('./dist/assets/__federation_shared_vuetify', import.meta.url), {
        recursive: true,
        force: true,
      })
      const remoteEntryUrl = new URL('./dist/assets/remoteEntry.js', import.meta.url)
      const remoteEntry = readFileSync(remoteEntryUrl, 'utf8').replace(/[ \t]+(?=\r?$)/gm, '')
      writeFileSync(remoteEntryUrl, remoteEntry, 'utf8')
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
        './AppPage': './src/components/AppPage.vue',
      },
      shared: {
        vue: { requiredVersion: false, generate: false },
        vuetify: { requiredVersion: false, generate: false, singleton: true },
        'vuetify/styles': { requiredVersion: false, generate: false, singleton: true },
      },
      format: 'esm',
    }),
    cleanFederationArtifacts(),
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
