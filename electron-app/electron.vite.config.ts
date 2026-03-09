import { defineConfig } from "electron-vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  main: {
    build: {
      outDir: "dist/main",
      rollupOptions: {
        external: ["onnxruntime-node", "better-sqlite3"],
      },
    },
  },
  preload: {
    build: {
      outDir: "dist/preload",
      lib: {
        entry: "src/main/preload.ts",
      },
    },
  },
  renderer: {
    plugins: [react()],
    build: {
      outDir: "dist/renderer",
    },
  },
});
