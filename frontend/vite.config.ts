import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({
 plugins: [react(), tailwindcss()],
 build: { outDir: '../src/rag_reglementation_ui/static', emptyOutDir: true, sourcemap: false },
 server: { proxy: Object.fromEntries(['/ask', '/search', '/ui-config', '/ready', '/health'].map(path => [path, 'http://127.0.0.1:8000'])) },
});
