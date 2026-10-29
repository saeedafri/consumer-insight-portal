import type { NextConfig } from "next";

// Static export: plain HTML/JS/CSS in out/, served by nginx (deploy/) or FastAPI (api/main.py); no Node server runs.
export default {
  output: "export",
  trailingSlash: true,   // /features/ → out/features/index.html, which any static server finds without rewrites
  images: { unoptimized: true },
} satisfies NextConfig;
