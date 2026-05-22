"use client";

import Link from "next/link";
import { useWebSocket } from "@/hooks/useWebSocket";
import { WS_URL } from "@/lib/config";

export function Navbar() {
  const { connected } = useWebSocket(WS_URL);

  return (
    <nav className="fixed top-0 left-0 right-0 z-40 h-16 flex items-center px-6 justify-between"
      style={{
        background: "rgba(3,7,18,0.85)",
        borderBottom: "1px solid rgba(6,182,212,0.15)",
        backdropFilter: "blur(16px)",
      }}>
      <Link href="/" className="flex items-center gap-3 group">
        <div className="relative w-9 h-9 rounded-xl flex items-center justify-center font-bold text-white text-sm"
          style={{
            background: "linear-gradient(135deg, #06b6d4, #a855f7)",
            boxShadow: "0 0 20px rgba(6,182,212,0.4)",
          }}>
          <span className="relative z-10">⬡</span>
        </div>
        <div>
          <span className="font-bold text-white tracking-tight">Oracle Sentinel</span>
          <span className="ml-2 text-xs font-mono px-2 py-0.5 rounded-full"
            style={{ background: "rgba(6,182,212,0.1)", color: "#06b6d4", border: "1px solid rgba(6,182,212,0.25)" }}>
            Arc Testnet
          </span>
        </div>
      </Link>

      <div className="flex items-center gap-5">
        <Link href="/warroom"
          className="text-xs font-medium px-3 py-1.5 rounded-lg transition-all"
          style={{
            background: "rgba(255,51,102,0.1)",
            color: "#ff3366",
            border: "1px solid rgba(255,51,102,0.25)",
          }}>
          🔴 War Room
        </Link>
        <a href="https://testnet.arcscan.app" target="_blank" rel="noopener noreferrer"
          className="text-xs transition-colors"
          style={{ color: "var(--text-secondary)" }}
          onMouseEnter={e => (e.currentTarget.style.color = "#06b6d4")}
          onMouseLeave={e => (e.currentTarget.style.color = "var(--text-secondary)")}>
          ArcScan ↗
        </a>
        <div className="flex items-center gap-2 text-xs">
          <span className={`status-dot ${connected ? "live" : "offline"}`} />
          <span style={{ color: connected ? "var(--sentinel-green)" : "var(--text-muted)" }}>
            {connected ? "Live" : "Offline"}
          </span>
        </div>
      </div>
    </nav>
  );
}
