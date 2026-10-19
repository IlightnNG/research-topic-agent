import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// API 走 /api 代理到本地后端（8000），前端不硬编码 host
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist" },
});
