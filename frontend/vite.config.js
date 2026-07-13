import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发期仅代理既有服务，绝不输出或覆盖仓库根目录 static/。
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:18400',
      '/v1': 'http://127.0.0.1:18400',
      '/health': 'http://127.0.0.1:18400',
    },
  },
})
