import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api and /auth go to the FastAPI service; in production FastAPI (or nginx) serves dist/.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  server: { proxy: { "/api": "http://127.0.0.1:8000", "/auth": "http://127.0.0.1:8000" } },
  build: {
    chunkSizeWarningLimit: 600,   // the charts chunk (ECharts core, bar/line/pie, plain legend) is ≈ 549 KB minified, 187 KB gzipped
    rolldownOptions: {   // charts change least: their own long-cached chunk
      output: { codeSplitting: { groups: [{ name: "charts", test: /node_modules[\\/](echarts|zrender)/ }] } },
    },
  },
});
