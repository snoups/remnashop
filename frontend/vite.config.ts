import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@app": fileURLToPath(new URL("./src/app", import.meta.url)),
      "@pages": fileURLToPath(new URL("./src/pages", import.meta.url)),
      "@widgets": fileURLToPath(new URL("./src/widgets", import.meta.url)),
      "@features": fileURLToPath(new URL("./src/features", import.meta.url)),
      "@entities": fileURLToPath(new URL("./src/entities", import.meta.url)),
      "@shared": fileURLToPath(new URL("./src/shared", import.meta.url)),
    },
  },
  optimizeDeps: {
    // recharts pulls in a dozen d3-* packages -- without eager pre-bundling
    // Vite discovers them lazily on first visit to a page that imports it
    // (the overview dashboard), triggering a mid-navigation "bundling
    // dependencies" pass that stalls every in-flight request for 10-20s+.
    include: ["recharts"],
  },
  server: {
    allowedHosts: process.env.APP_DOMAIN ? [process.env.APP_DOMAIN] : [],
    proxy: {
      "/api": {
        // 127.0.0.1, not localhost: on macOS with AirPlay Receiver enabled, "localhost"
        // can resolve to ::1 first and hit AirPlay's own port-5000 listener instead
        // of the API's IPv4-only Docker port mapping.
        target: process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:5000",
        // forwards the real browser IP via X-Forwarded-For -- otherwise the API
        // sees every request as coming from this dev-server container/process.
        xfwd: true,
      },
    },
  },
});
