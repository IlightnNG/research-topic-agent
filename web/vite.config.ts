import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import AutoImport from "unplugin-auto-import/vite";
import { ElementPlusResolver } from "unplugin-vue-components/resolvers";
import Components from "unplugin-vue-components/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    vue(),
    // 批次 4 / M：Element Plus 按需引入（只打包用到的组件与样式）
    AutoImport({ resolvers: [ElementPlusResolver()], dts: "src/auto-imports.d.ts" }),
    Components({ resolvers: [ElementPlusResolver()], dts: "src/components.d.ts" }),
  ],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
  build: { outDir: "dist" },
});
