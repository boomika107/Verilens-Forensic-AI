
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],

  server: {
    allowedHosts: ['verilens-forensic-ai-6.onrender.com']
  },

  preview: {
    allowedHosts: ['verilens-forensic-ai-6.onrender.com']
  },

  esbuild: {
    jsx: 'automatic'
  }
});
