import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendTarget = process.env.VITE_BACKEND_URL ?? "http://localhost:8200";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5273,
    proxy: {
      "/api": backendTarget,
      "/health": backendTarget,
    },
  },
  preview: {
    port: 5273,
  },
});
