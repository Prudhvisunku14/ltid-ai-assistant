/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: {
    colors: { bg: '#F8FAFC', ink: '#172033', muted: '#64748B', brand: '#4F6BED', soft: '#EEF2FF', line: '#E5EAF1', ok: '#16A36A', warn: '#E6A23C', err: '#DC5555' },
    boxShadow: { card: '0 1px 2px rgba(23,32,51,.04), 0 4px 16px rgba(23,32,51,.05)' },
    fontFamily: { sans: ['Inter', 'system-ui', 'Segoe UI', 'sans-serif'], mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'] }
  } }, plugins: []
}
