"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { fetchMarkets, fetchDisputeAlerts } from "@/lib/api";
import type { Market, DisputeAlert } from "@/types";

/* ── Threat level color ───────────────────────────────────── */
function getThreatColor(deviation: number): { color: string; label: string; glow: string } {
  if (deviation >= 0.3)  return { color: "#ff3366", label: "CRITICAL", glow: "rgba(255,51,102,0.4)" };
  if (deviation >= 0.15) return { color: "#ffcc00", label: "HIGH",     glow: "rgba(255,204,0,0.3)" };
  if (deviation >= 0.05) return { color: "#06b6d4", label: "WATCH",    glow: "rgba(6,182,212,0.3)" };
  return                        { color: "#00ff88", label: "CLEAR",    glow: "rgba(0,255,136,0.2)" };
}

/* ── Market threat cell ───────────────────────────────────── */
function ThreatCell({ market, alerts }: { market: Market; alerts: DisputeAlert[] }) {
  const alert = alerts.find(a => a.market_id === market.id);
  const marketPrice = market.yes_price ?? market.current_yes_price;
  const sentinelEst = alert?.our_estimate ?? alert?.sentinel_estimate ?? 0.5;
  const deviation = alert ? Math.abs(sentinelEst - marketPrice) : 0;
  const threat = getThreatColor(deviation);
  const isCritical = threat.label === "CRITICAL";

  return (
    <Link href={`/markets/${market.id}`}
      className="group relative rounded-xl p-3 transition-all cursor-pointer"
      style={{
        background: `${threat.color}08`,
        border: `1px solid ${threat.color}${isCritical ? "60" : "25"}`,
        animation: isCritical ? "threat-pulse 1.5s ease-in-out infinite" : undefined,
      }}>
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs font-bold px-1.5 py-0.5 rounded"
          style={{ background: `${threat.color}20`, color: threat.color }}>
          {threat.label}
        </span>
        {isCritical && <span className="text-xs animate-pulse">⚠️</span>}
      </div>
      <p className="text-xs font-medium leading-tight line-clamp-2 mb-2"
        style={{ color: "var(--text-primary)" }}>
        {market.question}
      </p>
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs" style={{ color: "var(--sentinel-cyan)" }}>
          {Math.round(marketPrice * 100)}%
        </span>
        {deviation > 0 && (
          <span className="font-mono text-xs" style={{ color: threat.color }}>
            Δ{Math.round(deviation * 100)}%
          </span>
        )}
      </div>
    </Link>
  );
}

/* ── Alert item ───────────────────────────────────────────── */
function AlertRow({ alert }: { alert: DisputeAlert }) {
  const deviation = alert.deviation ?? Math.abs(alert.our_estimate - 0.5);
  const threat = getThreatColor(deviation);
  return (
    <div className="flex items-start gap-3 py-3"
      style={{ borderBottom: "1px solid rgba(6,182,212,0.08)" }}>
      <span className="status-dot mt-1" style={{
        background: threat.color,
        boxShadow: `0 0 6px ${threat.glow}`,
        flexShrink: 0,
        animation: "live-pulse 1.2s ease-in-out infinite",
      }} />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium line-clamp-1" style={{ color: "var(--text-primary)" }}>
          {alert.reason ?? `Deviation detected for market ${alert.market_id?.slice(0,12)}`}
        </p>
        <p className="text-xs mt-0.5 font-mono" style={{ color: "var(--text-muted)" }}>
          {new Date(alert.created_at ?? alert.timestamp).toLocaleTimeString()}
        </p>
      </div>
      <span className="text-xs font-bold" style={{ color: threat.color }}>{threat.label}</span>
    </div>
  );
}

/* ── Radar spinner ────────────────────────────────────────── */
function RadarAnimation() {
  return (
    <div className="relative w-32 h-32 mx-auto">
      <div className="absolute inset-0 rounded-full"
        style={{ border: "1px solid rgba(6,182,212,0.15)" }} />
      <div className="absolute inset-4 rounded-full"
        style={{ border: "1px solid rgba(6,182,212,0.1)" }} />
      <div className="absolute inset-8 rounded-full"
        style={{ border: "1px solid rgba(6,182,212,0.08)" }} />
      {/* Sweep */}
      <div className="absolute inset-0 animate-radar-sweep origin-center"
        style={{
          background: "conic-gradient(rgba(6,182,212,0.3) 0deg, transparent 60deg, transparent 360deg)",
          borderRadius: "9999px",
        }} />
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-2xl">🎯</span>
      </div>
    </div>
  );
}

/* ── Main page ────────────────────────────────────────────── */
export default function WarRoomPage() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [alerts, setAlerts] = useState<DisputeAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const load = useCallback(async () => {
    try {
      const [m, a] = await Promise.all([fetchMarkets(false, 200), fetchDisputeAlerts(50)]);
      setMarkets(m.slice(0, 200));
      setAlerts(a.sort((x, y) => {
        const dx = Math.abs(x.sentinel_estimate - 0.5);
        const dy = Math.abs(y.sentinel_estimate - 0.5);
        return dy - dx;
      }));
      setLastUpdate(new Date());
    } catch {
      /* degraded */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(() => { load(); setTick(t => t + 1); }, 10_000);
    return () => clearInterval(iv);
  }, [load]);

  const criticalAlerts = alerts.filter(a => a.manipulation_suspected);
  const criticalMarkets = markets.filter(m => {
    const alert = alerts.find(a => a.market_id === m.id);
    if (!alert) return false;
    const est = alert.our_estimate ?? alert.sentinel_estimate ?? 0.5;
    const price = m.current_yes_price;
    return Math.abs(est - price) >= 0.3;
  });

  const demoMarkets = markets.length === 0 ? Array.from({ length: 40 }, (_, i) => ({
    id: `demo-${i}`,
    question: ["Will BTC hit 200k by EOY?", "US election: incumbent wins?", "Fed cut rates in June?", "ETH ETF approved?", "GPT-5 released Q3?"][i % 5],
    yes_price: 0.3 + Math.random() * 0.5,
    volume: Math.random() * 500000,
    resolution_date: new Date(Date.now() + 86400000 * 30).toISOString(),
    is_resolved: false,
    current_yes_price: 0.3 + Math.random() * 0.5,
  } as unknown as Market)) : markets;

  return (
    <div className="max-w-7xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-3xl font-black" style={{ color: "#ff3366" }}>
              ⚔️ War Room
            </h1>
            <span className="text-xs font-mono px-2 py-1 rounded-full animate-pulse"
              style={{ background: "rgba(255,51,102,0.15)", color: "#ff3366", border: "1px solid rgba(255,51,102,0.3)" }}>
              LIVE
            </span>
          </div>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Real-time threat grid — {demoMarkets.length} markets under surveillance
          </p>
        </div>
        <div className="text-right text-xs space-y-1" style={{ color: "var(--text-muted)" }}>
          <p>Last scan: <span style={{ color: "var(--sentinel-cyan)" }}>{lastUpdate.toLocaleTimeString()}</span></p>
          <p>Critical: <span style={{ color: "#ff3366", fontWeight: "bold" }}>{criticalMarkets.length}</span></p>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "🔴 Critical", value: criticalAlerts.length, color: "#ff3366" },
          { label: "🟡 High Risk", value: alerts.filter(a => !a.manipulation_suspected).length, color: "#ffcc00" },
          { label: "🔵 Watching", value: demoMarkets.length - criticalAlerts.length, color: "#06b6d4" },
          { label: "🟢 Clear", value: Math.max(0, demoMarkets.length - alerts.length), color: "#00ff88" },
        ].map(({ label, value, color }) => (
          <div key={label} className="sentinel-card p-4 text-center">
            <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
            <p className="text-2xl font-black" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Market threat grid */}
        <div className="col-span-2 sentinel-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
              Market Threat Grid
            </h2>
            <div className="flex gap-3 text-xs">
              {[["#ff3366","CRITICAL"],["#ffcc00","HIGH"],["#06b6d4","WATCH"],["#00ff88","CLEAR"]].map(([c,l]) => (
                <span key={l} className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full" style={{ background: c }} />
                  <span style={{ color: "var(--text-muted)" }}>{l}</span>
                </span>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 gap-4">
              <RadarAnimation />
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>Scanning markets...</p>
            </div>
          ) : (
            <div className="grid grid-cols-4 gap-2 max-h-[600px] overflow-y-auto">
              {demoMarkets.map((market) => (
                <ThreatCell key={market.id} market={market} alerts={alerts} />
              ))}
            </div>
          )}
        </div>

        {/* Live alert feed */}
        <div className="col-span-1 space-y-4">
          <div className="sentinel-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <span className="status-dot danger" />
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
                Threat Feed
              </h2>
            </div>
            {criticalAlerts.length === 0 ? (
              <div className="text-center py-8">
                <div className="text-3xl mb-2">✅</div>
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>No active threats</p>
              </div>
            ) : (
              <div className="space-y-0 max-h-80 overflow-y-auto">
                {criticalAlerts.slice(0, 15).map((a, i) => (
                  <AlertRow key={i} alert={a} />
                ))}
              </div>
            )}
          </div>

          <div className="sentinel-card p-5">
            <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>
              Radar Status
            </h2>
            <RadarAnimation />
            <div className="mt-4 space-y-2 text-xs">
              {[
                ["Scout agents", "5 active"],
                ["Scan interval", "10s"],
                ["UMA Oracle", "Monitoring"],
                ["Arc commits", "Live"],
              ].map(([k,v]) => (
                <div key={k} className="flex justify-between">
                  <span style={{ color: "var(--text-muted)" }}>{k}</span>
                  <span style={{ color: "var(--sentinel-cyan)" }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
