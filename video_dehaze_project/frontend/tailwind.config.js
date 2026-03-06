/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Space Grotesk'", "system-ui", "sans-serif"],
      },
      colors: {
        "neon-blue": "#60a5fa",
        "neon-cyan": "#22d3ee",
        "neon-pink": "#f472b6",
      },
    },
  },
  plugins: [],
};

