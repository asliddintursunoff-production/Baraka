import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

// Tokens copied from design/DESIGN.md. Do not add values that are not in the design.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F5F6F8",
        surface: { DEFAULT: "#FFFFFF", muted: "#F9FAFB", "muted-2": "#FCFCFD" },
        border: { DEFAULT: "#E4E7EC", subtle: "#EAECF0", input: "#D0D5DD" },
        ink: "#101828",
        "text-2": "#344054",
        "text-3": "#475467",
        "text-4": "#5D6679",
        primary: { DEFAULT: "#1D4ED8", hover: "#1E3A8A", soft: "#EFF4FF", border: "#84ADFF" },
        success: { DEFAULT: "#067647", bg: "#ECFDF3" },
        warning: { DEFAULT: "#B54708", bg: "#FFFAEB", accent: "#F79009" },
        danger: { DEFAULT: "#B42318", bg: "#FEF3F2", strong: "#D92D20" },
        live: { bg: "#0B1220", surface: "#101A2E", border: "#1D2939" },
        // shadcn/ui semantic aliases (CSS variables in index.css)
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        ring: "hsl(var(--ring))",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["'Space Grotesk'", "Inter", "sans-serif"],
      },
      fontSize: {
        11: "11px", 12: "12px", 13: "13px", 14: "14px", 15: "15px", 16: "16px", 17: "17px",
        20: "20px", 22: "22px", 24: "24px", 26: "26px", 30: "30px", 32: "32px",
      },
      borderRadius: { card: "16px", inner: "12px", btn: "10px", "btn-lg": "12px", pill: "999px" },
      letterSpacing: { label: "0.04em" },
      spacing: { tap: "44px", rail: "64px", sidebar: "260px", topbar: "52px", tabbar: "56px", chat: "768px" },
      maxWidth: { chat: "768px" },
      minHeight: { tap: "44px" },
      minWidth: { tap: "44px" },
    },
  },
  plugins: [animate],
} satisfies Config;
