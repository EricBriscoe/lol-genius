import { resolve } from "path";
import { defineConfig } from "electron-vite";
import react from "@vitejs/plugin-react";

const sharedAlias = { "@shared": resolve(__dirname, "../shared") };

export default defineConfig({
  main: {
    resolve: { alias: sharedAlias },
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
    resolve: { alias: sharedAlias },
    build: {
      outDir: "dist/renderer",
    },
  },
});
