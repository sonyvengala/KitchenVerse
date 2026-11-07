import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    strictPort: true,
    hmr: {
      port: 3000,
    },
    watch: {
      ignored: [
        "**/database/**",
        "**/ml/artifacts/**",
        "**/.venv/**",
        "**/backend/venv/**",
        "**/*.pyc",
        "**/__pycache__/**",
      ],
    },
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
      "/ws": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
      "/admin": {
        target: "http://localhost:8000",
        changeOrigin: true,
        bypass(req) {
          if (req.headers.accept?.includes("text/html")) {
            return "/index.html";
          }
        },
      },
      "/uploads": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
