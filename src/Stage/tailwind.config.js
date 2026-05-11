/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./**/*.html",
    "./**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",

        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",

        border: "var(--border)",
        background: "var(--background)",
        foreground: "var(--foreground)",
        accent: "var(--accent)",
      },
    },
  },
  plugins: [],
}