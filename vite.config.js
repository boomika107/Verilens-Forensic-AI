
import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    allowedHosts: ['verilens-forensic-ai-3.onrender.com']
  },
  preview: {
    allowedHosts: ['verilens-forensic-ai-3.onrender.com']
  }
});
