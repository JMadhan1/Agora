"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Dashboard", icon: "◈", exact: true },
  { href: "/markets", label: "Markets", icon: "◉" },
  { href: "/agents", label: "Agents", icon: "◎" },
  { href: "/jobs", label: "Jobs", icon: "◐", badge: "ERC-8183" },
  { href: "/alerts", label: "Alerts", icon: "⚠" },
];

const specialItems = [
  { href: "/try-live", label: "Try Live", icon: "⚡", accent: "#22c55e" },
  { href: "/warroom", label: "War Room", icon: "🔴", accent: "#ff3366" },
  { href: "/circle", label: "Circle Tools", icon: "💎", accent: "#a855f7" },
  { href: "/history", label: "Hall of Fame", icon: "🏛", accent: "#ffcc00" },
  { href: "/traces", label: "Trace Viewer", icon: "🔬", accent: "#06b6d4" },
  { href: "/leaderboard", label: "Leaderboard", icon: "🏆", accent: "#ffcc00" },
  { href: "/insurance", label: "Insurance", icon: "🛡️", accent: "#a855f7" },
];

export function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href);

  return (
    <aside className="fixed left-0 top-16 bottom-0 w-64 flex flex-col py-4 z-30"
      style={{
        background: "rgba(3,7,18,0.9)",
        borderRight: "1px solid rgba(6,182,212,0.12)",
        backdropFilter: "blur(16px)",
      }}>

      {/* Main navigation */}
      <nav className="flex-1 px-3 space-y-0.5">
        <p className="px-3 py-2 text-xs font-semibold tracking-widest uppercase"
          style={{ color: "var(--text-muted)" }}>
          Monitor
        </p>
        {navItems.map(({ href, label, icon, badge, exact }) => {
          const active = isActive(href, exact);
          return (
            <Link key={href} href={href}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all"
              style={{
                background: active ? "rgba(6,182,212,0.1)" : "transparent",
                color: active ? "#06b6d4" : "var(--text-secondary)",
                border: active ? "1px solid rgba(6,182,212,0.2)" : "1px solid transparent",
              }}>
              <span className="text-base w-5 text-center"
                style={{ color: active ? "#06b6d4" : "var(--text-muted)" }}>
                {icon}
              </span>
              <span className="flex-1">{label}</span>
              {badge && (
                <span className="text-xs px-1.5 py-0.5 rounded font-mono"
                  style={{ background: "rgba(168,85,247,0.15)", color: "#a855f7" }}>
                  {badge}
                </span>
              )}
            </Link>
          );
        })}

        <div className="pt-4 pb-2">
          <p className="px-3 py-2 text-xs font-semibold tracking-widest uppercase"
            style={{ color: "var(--text-muted)" }}>
            Intelligence
          </p>
          {specialItems.map(({ href, label, icon, accent }) => {
            const active = isActive(href);
            return (
              <Link key={href} href={href}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all"
                style={{
                  background: active ? `${accent}18` : "transparent",
                  color: active ? accent : "var(--text-secondary)",
                  border: active ? `1px solid ${accent}35` : "1px solid transparent",
                }}>
                <span className="text-base w-5 text-center">{icon}</span>
                {label}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="px-4 pt-4 space-y-3"
        style={{ borderTop: "1px solid rgba(6,182,212,0.1)" }}>
        <div className="space-y-1.5">
          <p className="text-xs font-semibold tracking-widest uppercase"
            style={{ color: "var(--sentinel-cyan)" }}>
            Circle Primitives
          </p>
          {["ERC-8004 Identity", "ERC-8183 Commerce", "USYC Yield", "Dev Wallets"].map(t => (
            <p key={t} className="text-xs flex items-center gap-2"
              style={{ color: "var(--text-muted)" }}>
              <span style={{ color: "var(--sentinel-cyan)", opacity: 0.5 }}>◦</span> {t}
            </p>
          ))}
        </div>
        <div className="rounded-lg px-3 py-2 text-xs"
          style={{ background: "rgba(6,182,212,0.05)", border: "1px solid rgba(6,182,212,0.1)" }}>
          <span style={{ color: "var(--text-muted)" }}>Agora Hackathon 2026</span>
          <br />
          <span style={{ color: "var(--sentinel-cyan)", fontFamily: "monospace" }}>
            Canteen × Circle × Arc
          </span>
        </div>
      </div>
    </aside>
  );
}
