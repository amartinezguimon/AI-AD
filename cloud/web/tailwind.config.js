/** @type {import('tailwindcss').Config} */
// Palette and radii lifted verbatim from Hector's mockup so the build is pixel-faithful.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F1EEE8",
        card: "#FFFFFF",
        dark: "#1C1C1C",
        purple: "#3d1a6e",
        "purple-deep": "#1a0a3e",
        "purple-soft": "#c9b8e8",
        slate: "#5e6e83",
        cream: "#fff7cd",
        yellow: "#F0DC6A",
        gray2: "#666666",
        gray3: "#999999",
        gray4: "#C8C8C8",
        gray5: "#EBEBEB",
        gray6: "#F5F5F5",
        danger: "#E8394A",
        "good-green": "#22863A",
        "bad-red": "#C4604A",
        live: "#22C55E",
        "traffic-high": "#4CAF72",
        "traffic-mid": "#FF8C42",
        "traffic-low": "#E8394A",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "18px",
      },
    },
  },
  plugins: [],
};
