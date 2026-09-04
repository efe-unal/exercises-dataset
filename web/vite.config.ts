import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The API runs separately in development; proxying keeps the browser on a
    // single origin so no CORS configuration is needed while developing.
    proxy: {
      '/v1': 'http://127.0.0.1:8000',
      '/images': 'http://127.0.0.1:8000',
      '/videos': 'http://127.0.0.1:8000',
    },
  },
  build: { outDir: 'dist', sourcemap: true },
});
