import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load environment variables from the project root directory
  const rootDir = path.resolve(import.meta.dirname, '..');
  const env = loadEnv(mode, rootDir, '');

  // Extract key portion if IS_RAG_API_KEYS is configured (e.g., 'dev_user:key' -> 'key')
  const rawKeys = env.IS_RAG_API_KEYS || process.env.IS_RAG_API_KEYS || '';
  let devKey = '';
  if (rawKeys) {
    const firstPair = rawKeys.split(',')[0].trim();
    if (firstPair.includes(':')) {
      devKey = firstPair.split(':')[1]?.trim() || '';
    } else {
      devKey = firstPair;
    }
  }

  return {
    plugins: [react()],
    envDir: rootDir,
    server: {
      port: 5173,
      proxy: {
        '/v1': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
        '/health': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
    define: {
      // Expose the development key dynamically from the local server .env
      'import.meta.env.VITE_IS_RAG_API_KEY': JSON.stringify(devKey),
    },
  };
});
