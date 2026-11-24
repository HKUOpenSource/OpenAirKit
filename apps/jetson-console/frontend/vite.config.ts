import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { frontendLicenses } from "../../../packages/console-ui/licenses.mjs";
export default defineConfig({
  plugins: [react(), frontendLicenses()],
  server: { proxy: { "/api": "http://127.0.0.1:8878" } },
});
