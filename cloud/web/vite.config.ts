import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The SPA calls the API with relative URLs (e.g. `/v1/dashboard`). In production
// Caddy serves this build and proxies `/v1` to the API on the same origin. In
// dev, Vite proxies `/v1` to the local backend so there's no CORS and the code
// is identical to production. Override the dev target with VM_API_TARGET.
const API_TARGET = process.env.VM_API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": { target: API_TARGET, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
