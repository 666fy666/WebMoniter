import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: { include: ['tests/*.test.ts'] },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8866',
      '/health': 'http://127.0.0.1:8866',
      '/weibo_img': 'http://127.0.0.1:8866',
    },
  },
  build: { target: 'es2022', sourcemap: false, chunkSizeWarningLimit: 250 },
})
