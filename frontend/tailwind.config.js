/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Values manually extracted from @razorpay/blade/tokens (bladeTheme.colors.onLight.surface.background.primary)
        brand: {
          DEFAULT: "hsla(218, 89%, 51%, 1)", // intense
          light: "hsla(218, 100%, 63%, 1)", // from data.background.categorical.blue.intense
          subtle: "hsla(218, 89%, 51%, 0.09)", // subtle
        },
      },
      spacing: {
        // Values extracted from @razorpay/blade/tokens (bladeTheme.spacing)
        '0': '0px',
        '1': '2px',
        '2': '4px',
        '3': '8px',
        '4': '12px',
        '5': '16px',
        '6': '20px',
        '7': '24px',
        '8': '32px',
        '9': '40px',
        '10': '48px',
        '11': '56px',
      },
      borderRadius: {
        // Values extracted from @razorpay/blade/tokens (bladeTheme.border.radius)
        'none': '0px',
        '2xsmall': '2px',
        'xsmall': '4px',
        'small': '8px',
        'medium': '12px',
        'large': '16px',
        'xlarge': '20px',
        '2xlarge': '24px',
        'max': '9999px',
        'round': '50%',
      },
      fontSize: {
        // Values extracted from @razorpay/blade/tokens (bladeTheme.typography.onDesktop.fonts.size)
        '25': '10px',
        '50': '11px',
        '75': '12px',
        '100': '14px',
        '200': '16px',
        '300': '18px',
        '400': '20px',
        '500': '24px',
        '600': '32px',
        '700': '40px',
        '800': '48px',
        '900': '56px',
        '1000': '64px',
        '1100': '72px',
      }
    },
  },
  plugins: [],
};
