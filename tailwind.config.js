module.exports = {
  content: [
    "./src/**/*.{html,js,ts,jsx,tsx}",
    "app/**/*.{ts,tsx}",
    "components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "dark-opacitiesdark-50": "var(--dark-opacitiesdark-50)",
        "dark-opacitiesdark-70": "var(--dark-opacitiesdark-70)",
        "greyscale-100": "var(--greyscale-100)",
        "greyscale-200": "var(--greyscale-200)",
        "greyscale-50": "var(--greyscale-50)",
        "greyscale-700": "var(--greyscale-700)",
        "greyscale-900": "var(--greyscale-900)",
        "others-black": "var(--others-black)",
        "others-white": "var(--others-white)",
        "primary-50": "var(--primary-50)",
        "primary-900": "var(--primary-900)",
        primarydark: "var(--primarydark)",
        primarylight: "var(--primarylight)",
        transparentgreen: "var(--transparentgreen)",
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      fontFamily: {
        "body-large-bold": "var(--body-large-bold-font-family)",
        "body-large-semibold": "var(--body-large-semibold-font-family)",
        "body-small-regular": "var(--body-small-regular-font-family)",
        "body-xlarge-bold": "var(--body-xlarge-bold-font-family)",
        "h4-bold": "var(--h4-bold-font-family)",
        "h6-bold": "var(--h6-bold-font-family)",
        sans: [
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
          '"Apple Color Emoji"',
          '"Segoe UI Emoji"',
          '"Segoe UI Symbol"',
          '"Noto Color Emoji"',
        ],
      },
      boxShadow: { "button-shadow-1": "var(--button-shadow-1)" },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
    container: { center: true, padding: "2rem", screens: { "2xl": "1400px" } },
  },
  plugins: [],
  darkMode: ["class"],
};
