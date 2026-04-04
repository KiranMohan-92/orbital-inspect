import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/three-stdlib/')) {
            return 'vendor-three-stdlib';
          }
          if (id.includes('/node_modules/three/')) {
            return 'vendor-three-core';
          }
          if (id.includes('/node_modules/@react-three/fiber/')) {
            return 'vendor-r3f';
          }
          if (
            id.includes('/node_modules/@react-three/drei/') ||
            id.includes('/node_modules/maath/') ||
            id.includes('/node_modules/meshline/') ||
            id.includes('/node_modules/stats-gl/') ||
            id.includes('/node_modules/suspend-react/') ||
            id.includes('/node_modules/react-use-measure/')
          ) {
            return 'vendor-r3-helpers';
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
