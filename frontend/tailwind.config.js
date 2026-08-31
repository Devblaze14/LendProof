/** Design tokens for LendProof — Loan Data Verification Copilot.
 *  Dark-mode glassmorphic design with indigo accent system. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          primary: "#0a0e1a",
          secondary: "#111827",
          card: "rgba(17, 24, 39, 0.7)",
          glass: "rgba(255, 255, 255, 0.03)",
        },
        accent: {
          DEFAULT: "#6366f1",
          light: "#818cf8",
          dark: "#4f46e5",
          glow: "rgba(99, 102, 241, 0.15)",
        },
        verified: "#10b981",
        severity: {
          critical: "#ef4444",
          high: "#f59e0b",
          medium: "#3b82f6",
          low: "#64748b",
        },
        ink: "#f1f5f9",
        muted: "#64748b",
        subtle: "#94a3b8",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        xl: "16px",
        "2xl": "20px",
        "3xl": "24px",
      },
      animation: {
        "fade-in-up": "fadeInUp 0.5s ease-out forwards",
        "fade-in": "fadeIn 0.4s ease-out forwards",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "float": "float 3s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
