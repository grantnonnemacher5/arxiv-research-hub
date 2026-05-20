import path from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// https://vite.dev/config/
export default defineConfig({
  envDir: repoRoot,
  plugins: [react(), tailwindcss()],
});
