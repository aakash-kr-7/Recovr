/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Values manually extracted from @razorpay/blade/tokens (bladeTheme.colors.onLight.surface.background.primary)
        brand: {
          DEFAULT: "hsla(218, 89%, 51%, 1)", // intense
          light: "hsla(218, 100%, 63%, 1)", // from data.background.categorical.blue.intense
          subtle: "hsla(218, 89%, 51%, 0.09)", // subtle
        },
        // Exact Blade onDark CSS custom properties from
        // https://github.com/razorpay/blade/blob/master/packages/blade-core/src/tokens/theme.css
        // Dark Mode block (lines 590–733 surface/interactive; 655–685 feedback;
        // 899–904 data categorical). Values copied as published, not inverted.
        bladeDark: {
          canvas: "hsla(210, 5%, 8%, 1)", // --surface-background-gray-moderate
          surface: "hsla(210, 6%, 13%, 1)", // --surface-background-gray-intense
          subtle: "hsla(210, 4%, 11%, 1)", // --surface-background-gray-subtle
          border: "hsla(216, 4%, 24%, 1)", // --surface-border-gray-subtle
          borderStrong: "hsla(210, 4%, 47%, 1)", // --surface-border-gray-normal (also used for chart axis/grid)
          text: "hsla(0, 0%, 100%, 1)", // --surface-text-gray-normal
          textSubtle: "hsla(210, 3%, 69%, 1)", // --surface-text-gray-subtle
          textMuted: "hsla(207, 4%, 52%, 1)", // --surface-text-gray-muted
          primary: "hsla(218, 100%, 63%, 1)", // --interactive-background-primary-default
          primarySubtle: "hsla(218, 89%, 51%, 0.32)", // --surface-background-primary-subtle
          chartBlue: "hsla(218, 100%, 63%, 1)", // --data-background-categorical-blue-strong
          chartGreen: "hsla(150, 48%, 44%, 1)", // --data-background-categorical-green-strong
          chartOrange: "hsla(22, 100%, 63%, 1)", // --data-background-categorical-orange-strong
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
