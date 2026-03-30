import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3022,
    proxy: {
      "/strategy": {
        target: "http://localhost:8072",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/strategy/, ""),
      },
    },
  },
})
