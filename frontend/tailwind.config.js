/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        arc: {
          50: "#ecfeff",
          100: "#cffafe",
          200: "#a5f3fc",
          400: "#22d3ee",
          500: "#06b6d4",
          600: "#0891b2",
          700: "#0e7490",
          900: "#083344",
        },
        sentinel: {
          green: "#00ff88",
          red: "#ff3366",
          yellow: "#ffcc00",
          purple: "#a855f7",
          cyan: "#06b6d4",
        },
      },
      backgroundImage: {
        "grid-pattern": "linear-gradient(rgba(6,182,212,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.03) 1px, transparent 1px)",
        "hero-gradient": "radial-gradient(ellipse at top, rgba(6,182,212,0.12) 0%, rgba(168,85,247,0.06) 50%, transparent 100%)",
        "card-gradient": "linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)",
        "threat-gradient": "radial-gradient(ellipse at center, rgba(255,51,102,0.15) 0%, transparent 70%)",
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "ping-slow": "ping 2s cubic-bezier(0,0,0.2,1) infinite",
        "slide-in": "slideIn 0.3s ease-out",
        "fade-in": "fadeIn 0.4s ease-out",
        "counter": "counter 1s ease-out",
        "glow": "glow 2s ease-in-out infinite alternate",
        "scan": "scan 3s linear infinite",
        "threat-pulse": "threatPulse 1.5s ease-in-out infinite",
        "float": "float 6s ease-in-out infinite",
        "shimmer": "shimmer 2s linear infinite",
      },
      keyframes: {
        slideIn: { from: { transform: "translateY(-8px)", opacity: 0 }, to: { transform: "translateY(0)", opacity: 1 } },
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        glow: {
          from: { boxShadow: "0 0 10px rgba(6,182,212,0.2), 0 0 20px rgba(6,182,212,0.1)" },
          to: { boxShadow: "0 0 20px rgba(6,182,212,0.4), 0 0 40px rgba(6,182,212,0.2)" },
        },
        scan: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(200%)" },
        },
        threatPulse: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(255,51,102,0.4)" },
          "50%": { boxShadow: "0 0 0 8px rgba(255,51,102,0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      backdropBlur: { xs: "2px" },
      boxShadow: {
        "glow-cyan": "0 0 20px rgba(6,182,212,0.3), 0 0 40px rgba(6,182,212,0.1)",
        "glow-purple": "0 0 20px rgba(168,85,247,0.3), 0 0 40px rgba(168,85,247,0.1)",
        "glow-red": "0 0 20px rgba(255,51,102,0.4), 0 0 40px rgba(255,51,102,0.15)",
        "glow-green": "0 0 20px rgba(0,255,136,0.3), 0 0 40px rgba(0,255,136,0.1)",
        "card": "0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)",
      },
    },
  },
  plugins: [],
};
