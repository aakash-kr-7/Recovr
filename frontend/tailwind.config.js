/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Loosely matched to Razorpay's public brand blue as a stand-in
        // until/unless @razorpay/blade is adopted (see README.md) — not
        // an exact token match, just a reasonable placeholder so the
        // fallback UI doesn't look generic.
        brand: {
          DEFAULT: "#0C2451",
          light: "#3B5EDB",
        },
      },
    },
  },
  plugins: [],
};
