"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { LiveFeed } from "@/components/dashboard/LiveFeed";
import { CalibrationChart } from "@/components/dashboard/CalibrationChart";
import { AlertBanner } from "@/components/dashboard/AlertBanner";
import { fetchSystemStats, fetchDisputeAlerts } from "@/lib/api";
import type { SystemStats, DisputeAlert } from "@/types";

/* ── Animated counter ─────────────────────────────────────── */
function AnimatedCounter({
  target, suffix = "", prefix = "", duration = 1800, decimals = 0,
}: { target: number; suffix?: string; prefix?: string; duration?: number; decimals?: number }) {
  const [display, setDisplay] = useState(0);
  const startTime = useRef<number | null>(null);
  const frame = useRef<number>(0);

  useEffect(() => {
    startTime.current = null;
    const animate = (ts: number) => {
      if (!startTime.current) startTime.current = ts;
      const pct = Math.min((ts - startTime.current) / duration, 1);
      const ease = 1 - Math.pow(1 - pct, 3);
      setDisplay(parseFloat((ease * target).toFixed(decimals)));
      if (pct < 1) frame.current = requestAnimationFrame(animate);
    };
    frame.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame.current);
  }, [target, duration, decimals]);

  return (
    <span>
      {prefix}{decimals > 0 ? display.toFixed(decimals) : display.toLocaleString()}{suffix}
    </span>
  );
}

/* ── Stat card ────────────────────────────────────────────── */
function HeroStat({
  label, value, sub, accent = "#06b6d4", icon,
}: { label: string; value: React.ReactNode; sub: string; accent?: string; icon: string }) {
  return (
    <div className="sentinel-card p-5 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold tracking-widest uppercase"
          style={{ color: "var(--text-muted)" }}>{label}</span>
        <span className="text-lg">{icon}</span>
      </div>
      <div className="text-2xl font-bold" style={{ color: accent }}>
        {value}
      </div>
      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{sub}</p>
    </div>
  );
}

/* ── Agent status badge ───────────────────────────────────── */
function AgentBadge({ name, pct, color }: { name: string; pct: number; color: string }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl"
      style={{ background: `${color}10`, border: `1px solid ${color}30` }}>
      <span className="status-dot" style={{ background: color, boxShadow: `0 0 6px ${color}80` }} />
      <span className="text-sm font-medium" style={{ color }}>{name}</span>
      <span className="ml-auto text-xs font-mono" style={{ color }}>{pct}%</span>
    </div>
  );
}

/* ── Main page ────────────────────────────────────────────── */
export default function DashboardPage() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [alerts, setAlerts] = useState<DisputeAlert[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [s, a] = await Promise.all([fetchSystemStats(), fetchDisputeAlerts(10)]);
        setStats(s);
        setAlerts(a.filter((al) => al.manipulation_suspected && !al.dispute_won));
      } catch {
        /* silently degrade */
      } finally {
        setLoaded(true);
      }
    }
    load();
    const iv = setInterval(load, 15_000);
    return () => clearInterval(iv);
  }, []);

  const attestations = stats?.total_attestations ?? 0;
  const markets = stats?.total_markets_monitored ?? 0;
  const accuracy = stats ? Math.round(stats.calibration_accuracy * 100) : 0;
  const disputes = stats?.total_disputes_triggered ?? 0;
  const usyc = stats?.usyc_deployed ?? 0;

  return (
    <div className="max-w-7xl space-y-8">

      {/* ── Hero Header ──────────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl px-8 py-10"
        style={{
          background: "radial-gradient(ellipse at 50% 0%, rgba(6,182,212,0.18) 0%, rgba(168,85,247,0.09) 50%, rgba(3,7,18,0.9) 100%)",
          border: "1px solid rgba(6,182,212,0.2)",
        }}>

        {/* Scan line */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 left-0 right-0 h-px animate-shimmer"
            style={{
              background: "linear-gradient(90deg, transparent 0%, rgba(6,182,212,0.6) 50%, transparent 100%)",
              backgroundSize: "200% 100%",
            }} />
        </div>

        <div className="relative z-10">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs font-mono font-semibold px-3 py-1 rounded-full"
                  style={{
                    background: "rgba(0,255,136,0.1)",
                    color: "var(--sentinel-green)",
                    border: "1px solid rgba(0,255,136,0.25)",
                  }}>
                  ● SYSTEM ONLINE
                </span>
                <span className="text-xs font-mono"
                  style={{ color: "var(--text-muted)" }}>
                  Arc Testnet · Chain 5042002
                </span>
              </div>
              <h1 className="text-5xl font-black tracking-tight mb-2"
                style={{ color: "var(--text-primary)" }}>
                Oracle{" "}
                <span style={{
                  background: "linear-gradient(90deg, #06b6d4, #a855f7)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}>
                  Sentinel
                </span>
              </h1>
              <p className="text-lg max-w-xl" style={{ color: "var(--text-secondary)" }}>
                Autonomous AI truth verification for prediction markets.
                3 agents. Cryptographic attestations. Zero human in the loop.
              </p>
            </div>

            <div className="hidden lg:flex flex-col gap-2 text-right">
              <AgentBadge name="Scout" pct={85} color="#06b6d4" />
              <AgentBadge name="Judge" pct={91} color="#a855f7" />
              <AgentBadge name="Watchdog" pct={94} color="#00ff88" />
            </div>
          </div>

          <div className="flex gap-3 mt-6">
            <Link href="/warroom"
              className="px-5 py-2.5 rounded-xl text-sm font-semibold transition-all"
              style={{
                background: "linear-gradient(135deg, rgba(255,51,102,0.2), rgba(255,51,102,0.1))",
                border: "1px solid rgba(255,51,102,0.4)",
                color: "#ff3366",
              }}>
              🔴 Enter War Room
            </Link>
            <Link href="/markets"
              className="px-5 py-2.5 rounded-xl text-sm font-semibold transition-all"
              style={{
                background: "rgba(6,182,212,0.1)",
                border: "1px solid rgba(6,182,212,0.3)",
                color: "#06b6d4",
              }}>
              View All Markets →
            </Link>
            <Link href="/circle"
              className="px-5 py-2.5 rounded-xl text-sm font-semibold transition-all"
              style={{
                background: "rgba(168,85,247,0.1)",
                border: "1px solid rgba(168,85,247,0.3)",
                color: "#a855f7",
              }}>
              💎 Circle Tools
            </Link>
          </div>
        </div>
      </div>

      {/* ── Alerts ───────────────────────────────────── */}
      {alerts.length > 0 && <AlertBanner alerts={alerts} />}

      {/* ── KPI Stats Grid ───────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <HeroStat
          label="Attestations"
          icon="🔐"
          accent="#06b6d4"
          value={loaded ? <AnimatedCounter target={attestations} /> : "—"}
          sub="on Arc Testnet"
        />
        <HeroStat
          label="Markets"
          icon="📊"
          accent="#a855f7"
          value={loaded ? <AnimatedCounter target={markets} /> : "—"}
          sub="Polymarket monitored"
        />
        <HeroStat
          label="Accuracy"
          icon="🎯"
          accent="#00ff88"
          value={loaded ? <AnimatedCounter target={accuracy} suffix="%" /> : "—"}
          sub="calibration score"
        />
        <HeroStat
          label="Disputes"
          icon="⚡"
          accent="#ff3366"
          value={loaded ? <AnimatedCounter target={disputes} /> : "—"}
          sub="manipulation flags"
        />
        <HeroStat
          label="USYC Yield"
          icon="💰"
          accent="#ffcc00"
          value={loaded ? <AnimatedCounter target={usyc} prefix="$" decimals={2} /> : "—"}
          sub="idle capital deployed"
        />
      </div>

      {/* ── Architecture Flow ─────────────────────────── */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { title: "Scout", icon: "🔭", color: "#06b6d4", desc: "5 parallel agents scan news, on-chain data, Wayback Machine, social sentiment, market prices every 5 min" },
          { title: "Judge", icon: "⚖️", color: "#a855f7", desc: "LangGraph + Bayesian inference produces probability estimate, commits SHA-256 trace to IPFS + Arc Testnet" },
          { title: "Watchdog", icon: "🐕", color: "#00ff88", desc: "Monitors deviation from Polymarket price, auto-triggers UMA dispute on Polygon if manipulation detected" },
        ].map(({ title, icon, color, desc }) => (
          <div key={title} className="sentinel-card p-5">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-2xl">{icon}</span>
              <span className="text-lg font-bold" style={{ color }}>{title}</span>
            </div>
            <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>{desc}</p>
          </div>
        ))}
      </div>

      {/* ── Live Feed + Calibration ───────────────────── */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <LiveFeed />
        </div>
        <div className="col-span-1">
          <CalibrationChart />
        </div>
      </div>

      {/* ── Contract Addresses ────────────────────────── */}
      <div className="sentinel-card p-5">
        <h3 className="text-sm font-semibold mb-4" style={{ color: "var(--text-secondary)" }}>
          Deployed Contracts — Arc Testnet
        </h3>
        <div className="grid grid-cols-3 gap-4">
          {[
            { name: "AttestationVault", addr: "0x4dE6AF7329E88F08C0560DAf1290a0DF152901E3" },
            { name: "BondManager",      addr: "0x2274D05C24527D0e4b689b215ddEAfE51B319008" },
            { name: "SentinelRegistry", addr: "0x165825Bd33c87c8aE31d60211dE9EE93e8039adE" },
          ].map(({ name, addr }) => (
            <a key={name}
              href={`https://testnet.arcscan.app/address/${addr}`}
              target="_blank" rel="noopener noreferrer"
              className="group rounded-xl p-4 transition-all"
              style={{
                background: "rgba(6,182,212,0.04)",
                border: "1px solid rgba(6,182,212,0.1)",
              }}>
              <p className="text-xs font-semibold mb-1.5"
                style={{ color: "var(--text-secondary)" }}>{name}</p>
              <p className="font-mono text-xs truncate group-hover:text-cyan-400 transition-colors"
                style={{ color: "var(--sentinel-cyan)" }}>
                {addr}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                ArcScan ↗
              </p>
            </a>
          ))}
        </div>
      </div>

    </div>
  );
}
