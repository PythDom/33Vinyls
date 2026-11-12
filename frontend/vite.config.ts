import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(process.env.npm_package_version ?? "0.1.0") },
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: false,
      includeAssets: ["icons/*.png"],
      manifest: {
        name: "33Vinyls",
        short_name: "33Vinyls",
        description: "Identify records, check prices in EUR and keep your collection offline.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "portrait",
        background_color: "#141210",
        theme_color: "#141210",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ["**/*.{js,css,html,png,svg,webmanifest}"],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: { environment: "node" },
});
