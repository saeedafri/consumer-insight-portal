import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api and /auth go to the FastAPI service; in production FastAPI (or nginx) serves dist/.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000", "/auth": "http://127.0.0.1:8000" } },
  build: {
    chunkSizeWarningLimit: 600,   // the charts chunk (ECharts) is ≈ 550 KB minified, 190 KB gzipped
    rolldownOptions: {   // charts change least: their own long-cached chunk
      output: { advancedChunks: { groups: [{ name: "charts", test: /node_modules[\\/](echarts|zrender)/ }] } },
    },
  },
});
