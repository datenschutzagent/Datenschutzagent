/// <reference types="vitest" />
import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'lcov'],
      reportsDirectory: 'coverage',
      // Only application code counts: generated API types, the shadcn/Radix
      // wrappers and test scaffolding would inflate the denominator without
      // telling us anything about our own logic.
      include: ['src/app/**/*.{ts,tsx}'],
      exclude: [
        'src/app/lib/api/schema.ts',
        'src/app/components/ui/**',
        'src/app/**/*.test.{ts,tsx}',
        'src/app/**/*.d.ts',
        'src/app/test-utils.tsx',
      ],
      // Ratchet, not target: set just under the measured value and raised whenever a
      // round adds tests, never lowered (measured 29 % lines on 2026-09-06, see
      // mkdocs/docs/projekt/qualitaetsplan.md). `npm run test:coverage` fails below it.
      thresholds: { lines: 27, statements: 25, functions: 24, branches: 20 },
    },
  },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },

  server: {
    port: 3002,
    proxy: {
      "/api": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
    },
  },

  // Raw-import asset types.
  assetsInclude: ['**/*.svg', '**/*.csv'],
})
