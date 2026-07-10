/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: { DEFAULT: '#0B1220', light: '#F6F8FB' },
        surface: { DEFAULT: '#111A2B', light: '#FFFFFF' },
        border: { DEFAULT: '#20304A', light: '#E2E8F0' },
        query: { DEFAULT: '#3FD6C6' },
        index: { DEFAULT: '#F0A954' },
        danger: { DEFAULT: '#F0615B' },
      },
      fontFamily: {
        display: ['"Sora"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
