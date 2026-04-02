import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/three/') || id.includes('/node_modules/@react-three/')) {
            return 'three-stack';
          }
          if (id.includes('/node_modules/jspdf/')) {
            return 'reporting';
          }
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5174,
    host: true,
  },
});
