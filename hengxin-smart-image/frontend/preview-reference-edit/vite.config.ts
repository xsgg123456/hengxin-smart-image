import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
  server: { host: '127.0.0.1', port: 3017, strictPort: true, fs: { allow: [fileURLToPath(new URL('..', import.meta.url))] } },
  build: { outDir: '../output/reference-edit-preview-build', emptyOutDir: true }
})
