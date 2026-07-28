import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { VitePWA } from 'vite-plugin-pwa';

const apiTarget = process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000';


export default defineConfig({

//META TAGS FOR IOS
//     <meta name="theme-color" content="#145aff" />
//
// <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
//
// <meta name="apple-mobile-web-app-capable" content="yes" />
// <meta
//     name="apple-mobile-web-app-status-bar-style"
// content="default"
// />
// <meta name="apple-mobile-web-app-title" content="CRM Bot" />

  
  base: '/',
  plugins: [
    react(),
    tailwindcss(),

    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto',

      includeAssets: [
        'favicon.ico',
        'apple-touch-icon.png',
      ],

      manifest: {
        id: '/',
        name: 'Codev',
        short_name: 'Codev',
        description: 'Kurs platforması üçün sosial media və müştəri əlaqələri idarəetməsi',

        start_url: '/',
        scope: '/',

        display: 'standalone',
        orientation: 'portrait',
        background_color: '#fffefc',
        theme_color: '#0f3e17',

        icons: [
          {
            src: '/pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/pwa-maskable-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },

      workbox: {
        navigateFallback: '/index.html',
        globPatterns: [
          '**/*.{js,css,html,ico,png,svg,webp,woff2}',
        ],
      },
    }),
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true
      },
      '/health': {
        target: apiTarget,
        changeOrigin: true
      }
    }
  }
});