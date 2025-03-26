import react from "@vitejs/plugin-react";
import tailwind from "tailwindcss";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  publicDir: "./static",
  base: "./",
  server: {
    proxy: {
      // Proxy all /api requests to the MongoDB API server
      '/api': {
        target: 'http://viammo-frontend-bolt-figma-v0-ba:5001',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path
      }
    }
  },
  css: {
    postcss: {
      plugins: [tailwind()],
    },
  },
});
