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
    port: 3023,
    proxy: {
      "/trade-api/ws": {
        target: "ws://localhost:8073",
        ws: true,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("error", () => {})
          proxy.on("proxyReqWs", (_proxyReq, _req, socket) => {
            socket.on("error", () => {})
          })
        },
      },
      "/trade-api": {
        target: "http://localhost:8073",
        changeOrigin: true,
      },
    },
  },
})
