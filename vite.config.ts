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
        },
        // '/api/google_login/oauth2callback': {
        //   target: `http://${apiHost}:${apiPort}`,
        //   secure: false,
        //   rewrite: (path) => path,
        //   // Optional: customize cookie handling if needed
        //   configure: (proxy, options) => {
        //     proxy.on('proxyRes', (proxyRes, req, res) => {
        //       const cookies = proxyRes.headers['set-cookie'];
        //       if (cookies) {
        //         proxyRes.headers['set-cookie'] = cookies.map(cookie =>
        //           cookie
        //             .replace(/;\s*Secure/i, '')
        //             .replace(/domain=[^;]+/i, 'domain=localhost')
        //         );
        //       }
        //     });
        //   }
        // },
      }
    },
    css: {
      postcss: {
        plugins: [tailwind()],
      },
    },
  };
});
