"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchMarkets } from "@/lib/api";
import type { Market } from "@/types";

/* ── Demo data ─────────────────────────────────────────────────── */
const DEMO_MARKETS: Market[] = [
  {
    id: "mkt-001",
    question: "Will Bitcoin exceed $200,000 by end of 2026?",
    category: "Crypto",
    resolution_date: "2026-12-31",
    current_yes_price: 0.61,
    yes_price: 0.61,
    our_latest_estimate: 0.58,
    our_confidence: 0.84,
    last_scouted: new Date().toISOString(),
    resolved: false,
    actual_resolution: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "mkt-002",
    question: "Will the Fed cut rates at the June 2026 FOMC?",
    category: "Macro",
    resolution_date: "2026-06-18",
    current_yes_price: 0.43,
    yes_price: 0.43,
    our_latest_estimate: 0.47,
    our_confidence: 0.79,
    last_scouted: new Date().toISOString(),
    resolved: false,
    actual_resolution: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "mkt-003",
    question: "Will Ethereum ETF inflows exceed $1B in May 2026?",
    category: "Crypto",
    resolution_date: "2026-05-31",
    current_yes_price: 0.72,
    yes_price: 0.72,
    our_latest_estimate: 0.68,
    our_confidence: 0.88,
    last_scouted: new Date().toISOString(),
    resolved: false,
    actual_resolution: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "mkt-004",
    question: "Will SpaceX Starship reach orbit before July 2026?",
    category: "Science",
    resolution_date: "2026-06-30",
    current_yes_price: 0.55,
    yes_price: 0.55,
    our_latest_estimate: 0.59,
    our_confidence: 0.76,
    last_scouted: new Date().toISOString(),
    resolved: false,
    actual_resolution: null,
    created_at: new Date().toISOString(),
  },
  {
    id: "mkt-005",
    question: "Will GPT-5 be publicly released before Q4 2026?",
    category: "AI",
    resolution_date: "2026-09-30",
    current_yes_price: 0.48,
    yes_price: 0.48,
    our_latest_estimate: 0.51,
    our_confidence: 0.71,
    last_scouted: new Date().toISOString(),
    resolved: false,
    actual_resolution: null,
    created_at: new Date().toISOString(),
  },
];

const DEMO_POLICIES = [
  {
    id: "POL-0042",
    market: "Will Bitcoin exceed $200,000 by end of 2026?",
    coverage: 500,
    premium: 25,
    status: "Active" as const,
    expiry: "2026-12-31",
    purchaseDate: "2026-05-10",
  },
  {
    id: "POL-0038",
    market: "Will the Fed cut rates at the June 2026 FOMC?",
    coverage: 200,
    premium: 10,
    status: "Claimed" as const,
    expiry: "2026-06-18",
    purchaseDate: "2026-04-22",
  },
];

const DURATIONS = [7, 14, 30] as const;
type Duration = typeof DURATIONS[number];

/* ── Step card for hero ───────────────────────────────────────── */
function HowItWorksStep({ step, icon, title, desc }: {
  step: number;
  icon: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="flex items-start gap-4">
      <div className="w-8 h-8 rounded-xl flex items-center justify-center text-sm font-black flex-shrink-0"
        style={{
          background: "rgba(6,182,212,0.12)",
          border: "1px solid rgba(6,182,212,0.25)",
          color: "#06b6d4",
        }}>
        {step}
      </div>
      <div>
        <p className="text-sm font-semibold mb-0.5" style={{ color: "var(--text-primary)" }}>
          {icon} {title}
        </p>
        <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>{desc}</p>
      </div>
    </div>
  );
}

/* ── Main page ─────────────────────────────────────────────────── */
export default function InsurancePage() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);

  // Form state
  const [selectedMarketId, setSelectedMarketId] = useState("");
  const [coverage, setCoverage] = useState(100);
  const [duration, setDuration] = useState<Duration>(14);
  const [buySuccess, setBuySuccess] = useState(false);
  const [buying, setBuying] = useState(false);

  const load = useCallback(async () => {
    try {
      const mkts = await fetchMarkets(false, 5);
      if (mkts.length > 0) {
        setMarkets(mkts.slice(0, 5));
        setSelectedMarketId(mkts[0].id);
      } else {
        throw new Error("empty");
      }
    } catch {
      setMarkets(DEMO_MARKETS);
      setSelectedMarketId(DEMO_MARKETS[0].id);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const displayMarkets = markets.length > 0 ? markets : DEMO_MARKETS;

  const premium = Math.round(coverage * 0.05 * 100) / 100;

  const handleBuy = () => {
    setBuying(true);
    setTimeout(() => {
      setBuying(false);
      setBuySuccess(true);
      setTimeout(() => setBuySuccess(false), 4000);
    }, 1200);
  };

  const selectedMarket = displayMarkets.find(m => m.id === selectedMarketId) ?? displayMarkets[0];

  return (
    <div className="max-w-6xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black mb-1"
          style={{
            background: "linear-gradient(90deg, #a855f7, #06b6d4)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}>
          🛡️ Dispute Insurance
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Buy protection against prediction market manipulation — powered by ERC-8183
        </p>
      </div>

      {/* Hero explainer */}
      <div className="sentinel-card p-6"
        style={{
          background: "linear-gradient(135deg, rgba(168,85,247,0.05) 0%, rgba(6,182,212,0.03) 100%)",
          border: "1px solid rgba(168,85,247,0.2)",
        }}>
        <div className="flex items-center gap-2 mb-5">
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
            How Dispute Insurance Works
          </h2>
          <span className="text-xs px-2 py-0.5 rounded-full font-mono"
            style={{ background: "rgba(168,85,247,0.12)", color: "#a855f7", border: "1px solid rgba(168,85,247,0.25)" }}>
            ERC-8183
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <HowItWorksStep
            step={1}
            icon="🛒"
            title="Buy Insurance"
            desc="Select any active prediction market and purchase coverage for $10–$1000 USDC. Pay only a 5% premium — gas is covered by Circle Paymaster."
          />
          <HowItWorksStep
            step={2}
            icon="🔍"
            title="Sentinel Monitors"
            desc="Oracle Sentinel's Watchdog agent continuously monitors for manipulation. If detected, it automatically triggers an on-chain dispute via UMA."
          />
          <HowItWorksStep
            step={3}
            icon="💰"
            title="Claim Payout"
            desc="If the dispute succeeds, your coverage is paid out in USDC via ERC-8183 Agentic Commerce. Fully automated, no manual claim required."
          />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Policies Sold", value: "47", color: "#06b6d4" },
          { label: "Total Coverage", value: "$12,400", color: "#a855f7" },
          { label: "Claims Paid", value: "$3,200", color: "#00ff88" },
          { label: "Claim Rate", value: "12%", color: "#ffcc00" },
        ].map(({ label, value, color }) => (
          <div key={label} className="sentinel-card p-4">
            <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
            <p className="text-2xl font-black" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Buy Insurance form */}
        <div className="sentinel-card p-6 space-y-5">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
              Buy Insurance Policy
            </h2>
          </div>

          {/* Market selector */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider"
              style={{ color: "var(--text-muted)" }}>
              Select Market
            </label>
            {loading ? (
              <div className="h-10 rounded-xl animate-pulse"
                style={{ background: "rgba(255,255,255,0.04)" }} />
            ) : (
              <select
                value={selectedMarketId}
                onChange={e => setSelectedMarketId(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl text-sm outline-none"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(6,182,212,0.15)",
                  color: "var(--text-primary)",
                  appearance: "none",
                  cursor: "pointer",
                }}>
                {displayMarkets.map(m => (
                  <option key={m.id} value={m.id}
                    style={{ background: "#030712" }}>
                    {m.question.length > 60 ? m.question.slice(0, 60) + "…" : m.question}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Coverage slider */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider"
                style={{ color: "var(--text-muted)" }}>
                Coverage Amount
              </label>
              <span className="text-sm font-black font-mono" style={{ color: "#06b6d4" }}>
                ${coverage} USDC
              </span>
            </div>
            <input
              type="range"
              min={10}
              max={1000}
              step={10}
              value={coverage}
              onChange={e => setCoverage(Number(e.target.value))}
              className="w-full"
              style={{ accentColor: "#06b6d4", cursor: "pointer" }}
            />
            <div className="flex justify-between text-xs" style={{ color: "var(--text-muted)" }}>
              <span>$10</span>
              <span>$1,000</span>
            </div>
          </div>

          {/* Duration selector */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider"
              style={{ color: "var(--text-muted)" }}>
              Duration
            </label>
            <div className="flex gap-2">
              {DURATIONS.map(d => (
                <button
                  key={d}
                  onClick={() => setDuration(d)}
                  className="flex-1 py-2 rounded-xl text-xs font-semibold transition-all"
                  style={{
                    background: duration === d ? "rgba(6,182,212,0.15)" : "rgba(255,255,255,0.04)",
                    color: duration === d ? "#06b6d4" : "var(--text-secondary)",
                    border: `1px solid ${duration === d ? "rgba(6,182,212,0.35)" : "rgba(255,255,255,0.07)"}`,
                  }}>
                  {d} days
                </button>
              ))}
            </div>
          </div>

          {/* Premium calculation */}
          <div className="rounded-xl p-4 space-y-2"
            style={{
              background: "rgba(6,182,212,0.05)",
              border: "1px solid rgba(6,182,212,0.15)",
            }}>
            <div className="flex items-center justify-between text-xs">
              <span style={{ color: "var(--text-muted)" }}>Coverage</span>
              <span className="font-mono" style={{ color: "var(--text-secondary)" }}>${coverage}.00 USDC</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span style={{ color: "var(--text-muted)" }}>Premium rate</span>
              <span className="font-mono" style={{ color: "var(--text-secondary)" }}>5.0%</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span style={{ color: "var(--text-muted)" }}>Duration</span>
              <span className="font-mono" style={{ color: "var(--text-secondary)" }}>{duration} days</span>
            </div>
            <div className="h-px" style={{ background: "rgba(6,182,212,0.15)" }} />
            <div className="flex items-center justify-between text-sm">
              <span className="font-semibold" style={{ color: "var(--text-secondary)" }}>You Pay</span>
              <span className="font-black font-mono" style={{ color: "#06b6d4" }}>${premium.toFixed(2)} USDC</span>
            </div>
          </div>

          {/* Paymaster badge */}
          <div className="flex items-center gap-2 text-xs px-3 py-2 rounded-xl"
            style={{
              background: "rgba(168,85,247,0.06)",
              border: "1px solid rgba(168,85,247,0.15)",
            }}>
            <span>🔵</span>
            <span style={{ color: "var(--text-muted)" }}>
              Gas-free via <strong style={{ color: "#a855f7" }}>Circle Paymaster</strong> — pay in USDC only
            </span>
          </div>

          {/* Buy button */}
          {buySuccess ? (
            <div className="rounded-xl p-4 text-center"
              style={{
                background: "rgba(0,255,136,0.08)",
                border: "1px solid rgba(0,255,136,0.25)",
              }}>
              <p className="text-lg mb-1">✅</p>
              <p className="text-sm font-bold" style={{ color: "#00ff88" }}>Policy Purchased!</p>
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                Coverage: ${coverage} USDC · Premium paid: ${premium.toFixed(2)} USDC
              </p>
            </div>
          ) : (
            <button
              onClick={handleBuy}
              disabled={buying}
              className="w-full py-3 rounded-xl text-sm font-bold transition-all"
              style={{
                background: buying
                  ? "rgba(168,85,247,0.1)"
                  : "linear-gradient(135deg, rgba(168,85,247,0.2), rgba(6,182,212,0.15))",
                color: buying ? "#a855f7" : "#fff",
                border: "1px solid rgba(168,85,247,0.35)",
                cursor: buying ? "not-allowed" : "pointer",
              }}>
              {buying ? "⏳ Processing Payment…" : `🛡️ Buy Policy — Pay $${premium.toFixed(2)} USDC`}
            </button>
          )}
        </div>

        {/* Active policies */}
        <div className="space-y-4">
          <div className="sentinel-card p-5 space-y-4">
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
              Active Policies
            </h2>
            {DEMO_POLICIES.map(policy => (
              <div
                key={policy.id}
                className="rounded-xl p-4 space-y-3"
                style={{
                  background: policy.status === "Claimed"
                    ? "rgba(0,255,136,0.04)"
                    : "rgba(255,255,255,0.03)",
                  border: policy.status === "Claimed"
                    ? "1px solid rgba(0,255,136,0.15)"
                    : "1px solid rgba(255,255,255,0.06)",
                }}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono font-bold" style={{ color: "var(--sentinel-cyan)" }}>
                        {policy.id}
                      </span>
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-semibold"
                        style={{
                          background: policy.status === "Active"
                            ? "rgba(6,182,212,0.12)"
                            : "rgba(0,255,136,0.12)",
                          color: policy.status === "Active" ? "#06b6d4" : "#00ff88",
                          border: `1px solid ${policy.status === "Active" ? "rgba(6,182,212,0.3)" : "rgba(0,255,136,0.3)"}`,
                        }}>
                        {policy.status}
                      </span>
                    </div>
                    <p className="text-xs font-medium line-clamp-2" style={{ color: "var(--text-primary)" }}>
                      {policy.market}
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <p style={{ color: "var(--text-muted)" }}>Coverage</p>
                    <p className="font-mono font-bold" style={{ color: "var(--text-secondary)" }}>
                      ${policy.coverage}
                    </p>
                  </div>
                  <div>
                    <p style={{ color: "var(--text-muted)" }}>Premium</p>
                    <p className="font-mono" style={{ color: "var(--text-secondary)" }}>
                      ${policy.premium}
                    </p>
                  </div>
                  <div>
                    <p style={{ color: "var(--text-muted)" }}>Expires</p>
                    <p className="font-mono" style={{ color: "var(--text-secondary)" }}>
                      {new Date(policy.expiry).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Risk explainer */}
          <div className="sentinel-card p-5 space-y-3">
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
              ⚡ Why This Matters
            </h3>
            <div className="space-y-2 text-xs" style={{ color: "var(--text-muted)" }}>
              {[
                { icon: "🎯", text: "Prediction markets have been exploited for millions in the past year" },
                { icon: "🤖", text: "Sentinel's AI detects manipulation with 88%+ accuracy" },
                { icon: "⚖️", text: "Successful disputes are filed automatically via UMA Protocol" },
                { icon: "💸", text: "Payouts happen in USDC — no governance tokens needed" },
              ].map(({ icon, text }) => (
                <div key={text} className="flex items-start gap-2">
                  <span className="flex-shrink-0">{icon}</span>
                  <span className="leading-relaxed">{text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Footer badge */}
      <div className="flex justify-center pt-2">
        <div className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs"
          style={{
            background: "rgba(168,85,247,0.06)",
            border: "1px solid rgba(168,85,247,0.15)",
            color: "var(--text-muted)",
          }}>
          <span style={{ color: "#a855f7" }}>◈</span>
          Powered by ERC-8183 Agentic Commerce · USDC settlements · Circle Paymaster gas sponsorship
        </div>
      </div>
    </div>
  );
}
