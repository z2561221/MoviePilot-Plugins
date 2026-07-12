import { createApp } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import PreviewApp from './PreviewApp.vue'

createApp(PreviewApp).use(createVuetify({ components, directives })).mount('#preview')
