import react from "@vitejs/plugin-react";
import tailwind from "tailwindcss";
import { defineConfig, loadEnv } from "vite";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load environment variables
  const env = loadEnv(mode, process.cwd(), '');
  
  // Use env variables or fallbacks
  const apiHost = env.VITE_API_HOST || 'localhost';
  const apiPort = env.VITE_API_PORT || '5001';
  
  return {
    plugins: [react()],
    publicDir: "./static",
    base: "./",
    server: {
      proxy: {
        // Proxy all /api requests to the MongoDB API server
        '/api': {
          target: `http://${apiHost}:${apiPort}`,
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
  };
});
