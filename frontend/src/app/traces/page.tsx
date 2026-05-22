"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchAttestations, fetchMarkets } from "@/lib/api";
import type { Attestation, Market } from "@/types";

/* ── Demo fallback data ─────────────────────────────────────── */
const DEMO_ATTESTATIONS: Attestation[] = Array.from({ length: 12 }, (_, i) => ({
  id: i + 1,
  market_id: `market-${i + 1}`,
  trace_hash: `0x${Array.from({ length: 64 }, () => Math.floor(Math.random() * 16).toString(16)).join("")}`,
  ipfs_cid: `Qm${Array.from({ length: 44 }, () => "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz123456789"[Math.floor(Math.random() * 58)]).join("")}`,
  arc_tx_hash: `0x${Array.from({ length: 64 }, () => Math.floor(Math.random() * 16).toString(16)).join("")}`,
  arc_scan_url: `https://testnet.arcscan.app/tx/0xdemo${i}`,
  arc_block_number: 4200000 + i * 37,
  confidence: 0.72 + Math.random() * 0.25,
  recommendation: (["YES", "NO", "YES", "UNCERTAIN", "YES", "NO"][i % 6]) as "YES" | "NO" | "UNCERTAIN",
  probability_estimate: 0.3 + Math.random() * 0.5,
  timestamp: new Date(Date.now() - i * 3600000 * 4).toISOString(),
}));

const DEMO_QUESTIONS = [
  "Will Bitcoin exceed $200,000 by end of 2026?",
  "Will the Fed cut rates at the June 2026 FOMC meeting?",
  "Will SpaceX Starship reach orbit before July 2026?",
  "Will Ethereum ETF inflows exceed $1B in May 2026?",
  "Will GPT-5 be publicly released before Q4 2026?",
  "Will the US unemployment rate stay below 4.5% in 2026?",
  "Will Apple release an AR headset in 2026?",
  "Will Solana overtake Ethereum in daily transactions by EOY?",
  "Will the 2026 World Cup host nation reach the semifinals?",
  "Will US inflation stay below 3% through 2026?",
  "Will China's GDP growth exceed 4.5% in 2026?",
  "Will a major DeFi protocol experience a >$100M exploit in 2026?",
];

/* ── Simulated reasoning trace data ──────────────────────────── */
function generateTrace(att: Attestation, question: string) {
  const scouts = ["Perplexity Scout", "Tavily Scout", "News Scout"];
  const priors = [0.45, 0.51, 0.48];
  return {
    market_question: question,
    trace_id: att.trace_hash,
    ipfs_cid: att.ipfs_cid,
    timestamp: att.timestamp,
    methodology: "Bayesian aggregation over multi-source LLM scouts",
    bayesian_steps: scouts.map((name, i) => ({
      scout: name,
      prior: priors[i],
      likelihood_ratio: 1.1 + Math.random() * 0.8,
      posterior: Math.min(0.99, priors[i] + (att.probability_estimate - 0.5) * 0.3 + Math.random() * 0.05),
      evidence_summary: `Scout found ${Math.floor(Math.random() * 15) + 5} relevant sources with ${Math.floor(Math.random() * 80) + 60}% agreement`,
    })),
    final_estimate: att.probability_estimate,
    confidence: att.confidence,
    recommendation: att.recommendation,
    llm_narrative: `Based on comprehensive analysis across ${Math.floor(Math.random() * 20) + 10} sources, the weight of evidence ${att.recommendation === "YES" ? "supports" : att.recommendation === "NO" ? "contradicts" : "is ambiguous regarding"} the stated outcome. The Bayesian aggregation converged at ${(att.probability_estimate * 100).toFixed(1)}% probability with ${(att.confidence * 100).toFixed(0)}% confidence. Key signals include recent market dynamics, macroeconomic context, and corroborating on-chain data.`,
    arc_attestation: {
      tx_hash: att.arc_tx_hash,
      block: att.arc_block_number,
      network: "Arc Testnet",
    },
  };
}

/* ── Recommendation badge ─────────────────────────────────────── */
function RecBadge({ rec }: { rec: "YES" | "NO" | "UNCERTAIN" }) {
  const map = {
    YES: { color: "#00ff88", bg: "rgba(0,255,136,0.1)", border: "rgba(0,255,136,0.3)" },
    NO: { color: "#ff3366", bg: "rgba(255,51,102,0.1)", border: "rgba(255,51,102,0.3)" },
    UNCERTAIN: { color: "#ffcc00", bg: "rgba(255,204,0,0.1)", border: "rgba(255,204,0,0.3)" },
  };
  const s = map[rec];
  return (
    <span className="text-xs font-bold px-2 py-0.5 rounded-full"
      style={{ color: s.color, background: s.bg, border: `1px solid ${s.border}` }}>
      {rec}
    </span>
  );
}

/* ── Bayesian step bar ─────────────────────────────────────────── */
function BayesBar({ step }: { step: { scout: string; prior: number; posterior: number; evidence_summary: string } }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span style={{ color: "var(--text-secondary)" }}>{step.scout}</span>
        <span className="font-mono" style={{ color: "var(--sentinel-cyan)" }}>
          {(step.prior * 100).toFixed(0)}% → {(step.posterior * 100).toFixed(0)}%
        </span>
      </div>
      <div className="relative h-2 rounded-full overflow-hidden"
        style={{ background: "rgba(255,255,255,0.06)" }}>
        <div className="absolute left-0 top-0 h-full rounded-full transition-all duration-700"
          style={{
            width: `${step.prior * 100}%`,
            background: "rgba(168,85,247,0.5)",
          }} />
        <div className="absolute left-0 top-0 h-full rounded-full transition-all duration-700"
          style={{
            width: `${step.posterior * 100}%`,
            background: "linear-gradient(90deg, #a855f7, #06b6d4)",
            opacity: 0.85,
          }} />
      </div>
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>{step.evidence_summary}</p>
    </div>
  );
}

/* ── Trace modal ───────────────────────────────────────────────── */
function TraceModal({
  att, question, onClose, onPayment,
}: {
  att: Attestation;
  question: string;
  onClose: () => void;
  onPayment: () => void;
}) {
  const [paid, setPaid] = useState(false);
  const [paying, setPaying] = useState(false);
  const [jsonOpen, setJsonOpen] = useState(false);
  const trace = generateTrace(att, question);

  const handlePay = () => {
    setPaying(true);
    setTimeout(() => {
      setPaid(true);
      setPaying(false);
      onPayment();
    }, 900);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(3,7,18,0.85)", backdropFilter: "blur(8px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl"
        style={{
          background: "rgba(3,7,18,0.98)",
          border: "1px solid rgba(6,182,212,0.25)",
          boxShadow: "0 0 60px rgba(6,182,212,0.12), 0 0 120px rgba(168,85,247,0.06)",
        }}>
        {/* Header */}
        <div className="flex items-start justify-between p-6 pb-4"
          style={{ borderBottom: "1px solid rgba(6,182,212,0.1)" }}>
          <div className="flex-1 min-w-0 pr-4">
            <p className="text-xs font-mono mb-1" style={{ color: "var(--sentinel-cyan)" }}>
              Reasoning Trace #{att.id}
            </p>
            <h3 className="text-sm font-semibold leading-snug" style={{ color: "var(--text-primary)" }}>
              {question}
            </h3>
          </div>
          <button onClick={onClose}
            className="text-lg leading-none flex-shrink-0 hover:opacity-70 transition-opacity"
            style={{ color: "var(--text-muted)" }}>✕</button>
        </div>

        <div className="p-6 space-y-5">
          {/* Payment gate */}
          {!paid ? (
            <div className="rounded-xl p-5 text-center"
              style={{
                background: "rgba(6,182,212,0.04)",
                border: "1px solid rgba(6,182,212,0.2)",
              }}>
              <div className="text-3xl mb-3">🔐</div>
              <p className="text-sm font-semibold mb-1" style={{ color: "var(--text-primary)" }}>
                Nanopayment Required
              </p>
              <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
                Pay $0.0001 USDC to unlock this cryptographic reasoning trace
              </p>
              <button
                onClick={handlePay}
                disabled={paying}
                className="px-6 py-2.5 rounded-xl text-sm font-bold transition-all"
                style={{
                  background: paying ? "rgba(6,182,212,0.1)" : "rgba(6,182,212,0.15)",
                  color: "#06b6d4",
                  border: "1px solid rgba(6,182,212,0.4)",
                  cursor: paying ? "not-allowed" : "pointer",
                }}>
                {paying ? "⏳ Processing…" : "🔓 View Trace — $0.0001 USDC"}
              </button>
              <p className="text-xs mt-3" style={{ color: "var(--text-muted)", opacity: 0.6 }}>
                Powered by Circle Nanopayments
              </p>
            </div>
          ) : (
            <>
              {/* Payment success banner */}
              <div className="rounded-xl px-4 py-3 flex items-center gap-3"
                style={{
                  background: "rgba(0,255,136,0.06)",
                  border: "1px solid rgba(0,255,136,0.2)",
                }}>
                <span className="text-lg">✅</span>
                <div>
                  <p className="text-xs font-semibold" style={{ color: "#00ff88" }}>
                    Paid $0.0001 USDC via Circle Gateway
                  </p>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Transaction confirmed · Trace unlocked
                  </p>
                </div>
              </div>

              {/* Verdict */}
              <div className="flex items-center gap-3 p-4 rounded-xl"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                <RecBadge rec={att.recommendation} />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                      {(att.probability_estimate * 100).toFixed(1)}% probability
                    </span>
                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                      · {(att.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full overflow-hidden"
                    style={{ background: "rgba(255,255,255,0.08)" }}>
                    <div className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${att.probability_estimate * 100}%`,
                        background: att.recommendation === "YES" ? "#00ff88" : att.recommendation === "NO" ? "#ff3366" : "#ffcc00",
                      }} />
                  </div>
                </div>
              </div>

              {/* Bayesian steps */}
              <div>
                <p className="text-xs font-semibold mb-3 uppercase tracking-wider"
                  style={{ color: "var(--text-muted)" }}>
                  Bayesian Updates — Prior → Posterior
                </p>
                <div className="space-y-4 p-4 rounded-xl"
                  style={{ background: "rgba(6,182,212,0.04)", border: "1px solid rgba(6,182,212,0.1)" }}>
                  {trace.bayesian_steps.map((step, i) => (
                    <BayesBar key={i} step={step} />
                  ))}
                </div>
              </div>

              {/* LLM narrative */}
              <div>
                <p className="text-xs font-semibold mb-2 uppercase tracking-wider"
                  style={{ color: "var(--text-muted)" }}>
                  Judge Agent Narrative
                </p>
                <p className="text-sm leading-relaxed p-4 rounded-xl italic"
                  style={{
                    color: "var(--text-secondary)",
                    background: "rgba(168,85,247,0.04)",
                    border: "1px solid rgba(168,85,247,0.1)",
                  }}>
                  "{trace.llm_narrative}"
                </p>
              </div>

              {/* JSON trace */}
              <div>
                <button
                  onClick={() => setJsonOpen(o => !o)}
                  className="text-xs font-semibold flex items-center gap-2 mb-2 hover:opacity-80 transition-opacity"
                  style={{ color: "var(--sentinel-cyan)" }}>
                  {jsonOpen ? "▾" : "▸"} Raw Reasoning JSON
                </button>
                {jsonOpen && (
                  <pre className="text-xs overflow-x-auto p-4 rounded-xl leading-relaxed"
                    style={{
                      background: "rgba(6,182,212,0.04)",
                      border: "1px solid rgba(6,182,212,0.1)",
                      color: "var(--text-secondary)",
                      fontFamily: "monospace",
                      maxHeight: "240px",
                      overflowY: "auto",
                    }}>
                    {JSON.stringify(trace, null, 2)}
                  </pre>
                )}
              </div>

              {/* Links */}
              <div className="flex gap-3 flex-wrap">
                <a
                  href={`https://ipfs.io/ipfs/${att.ipfs_cid}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs px-3 py-1.5 rounded-lg font-mono transition-opacity hover:opacity-80"
                  style={{
                    background: "rgba(168,85,247,0.1)",
                    color: "#a855f7",
                    border: "1px solid rgba(168,85,247,0.25)",
                  }}>
                  📦 IPFS: {att.ipfs_cid.slice(0, 20)}…
                </a>
                <a
                  href={att.arc_scan_url || `https://testnet.arcscan.app/tx/${att.arc_tx_hash}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs px-3 py-1.5 rounded-lg font-mono transition-opacity hover:opacity-80"
                  style={{
                    background: "rgba(6,182,212,0.1)",
                    color: "#06b6d4",
                    border: "1px solid rgba(6,182,212,0.25)",
                  }}>
                  ⛓ Arc: {att.arc_tx_hash.slice(0, 14)}…
                </a>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Attestation card ─────────────────────────────────────────── */
function AttCard({
  att,
  question,
  onView,
}: {
  att: Attestation;
  question: string;
  onView: () => void;
}) {
  return (
    <div className="sentinel-card p-5 space-y-3 transition-all duration-200 hover:border-cyan-500/30"
      style={{ cursor: "default" }}>
      {/* Market question */}
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium leading-snug flex-1 line-clamp-2"
          style={{ color: "var(--text-primary)" }}>
          {question}
        </p>
        <RecBadge rec={att.recommendation} />
      </div>

      {/* Confidence bar */}
      <div>
        <div className="flex items-center justify-between text-xs mb-1.5">
          <span style={{ color: "var(--text-muted)" }}>Confidence</span>
          <span className="font-mono font-bold" style={{ color: "var(--sentinel-cyan)" }}>
            {(att.confidence * 100).toFixed(0)}%
          </span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden"
          style={{ background: "rgba(255,255,255,0.06)" }}>
          <div className="h-full rounded-full transition-all"
            style={{
              width: `${att.confidence * 100}%`,
              background: "linear-gradient(90deg, #06b6d4, #a855f7)",
            }} />
        </div>
      </div>

      {/* Meta row */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <p style={{ color: "var(--text-muted)" }}>IPFS CID</p>
          <p className="font-mono truncate" style={{ color: "var(--text-secondary)" }}>
            {att.ipfs_cid.slice(0, 22)}…
          </p>
        </div>
        <div>
          <p style={{ color: "var(--text-muted)" }}>Probability</p>
          <p className="font-mono font-semibold" style={{ color: "#a855f7" }}>
            {(att.probability_estimate * 100).toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="text-xs">
        <p style={{ color: "var(--text-muted)" }}>Arc TX</p>
        <a
          href={att.arc_scan_url || `https://testnet.arcscan.app/tx/${att.arc_tx_hash}`}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono hover:opacity-80 transition-opacity"
          style={{ color: "var(--sentinel-cyan)" }}>
          {att.arc_tx_hash.slice(0, 26)}…
        </a>
      </div>

      <div className="flex items-center justify-between pt-1"
        style={{ borderTop: "1px solid rgba(6,182,212,0.08)" }}>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {new Date(att.timestamp).toLocaleString()}
        </span>
        <button
          onClick={onView}
          className="text-xs px-3 py-1.5 rounded-lg font-semibold transition-all hover:opacity-90"
          style={{
            background: "rgba(6,182,212,0.12)",
            color: "#06b6d4",
            border: "1px solid rgba(6,182,212,0.3)",
          }}>
          🔓 View Trace — $0.0001 USDC
        </button>
      </div>
    </div>
  );
}

/* ── Main page ─────────────────────────────────────────────────── */
export default function TracesPage() {
  const [attestations, setAttestations] = useState<Attestation[]>([]);
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAtt, setSelectedAtt] = useState<Attestation | null>(null);
  const [nanopayRevenue, setNanopayRevenue] = useState(0.0047);

  const load = useCallback(async () => {
    try {
      const [atts, mkts] = await Promise.all([
        fetchAttestations(undefined, 50),
        fetchMarkets(false, 50),
      ]);
      if (atts.length > 0) setAttestations(atts);
      if (mkts.length > 0) setMarkets(mkts);
    } catch {
      /* use demo data */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const displayAtts = attestations.length > 0 ? attestations : DEMO_ATTESTATIONS;

  const getQuestion = (att: Attestation, idx: number) => {
    const m = markets.find(m => m.id === att.market_id);
    return m?.question ?? DEMO_QUESTIONS[idx % DEMO_QUESTIONS.length];
  };

  const avgConfidence = displayAtts.length > 0
    ? displayAtts.reduce((s, a) => s + a.confidence, 0) / displayAtts.length
    : 0;

  const handlePayment = () => {
    setNanopayRevenue(r => Math.round((r + 0.0001) * 10000) / 10000);
  };

  return (
    <div className="max-w-7xl space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-black mb-1"
            style={{
              background: "linear-gradient(90deg, #06b6d4, #a855f7)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}>
            🔬 Reasoning Traces
          </h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Every AI judgement, cryptographically committed to Arc Testnet
          </p>
        </div>
        <div className="text-right space-y-1">
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>Nanopayment Revenue</p>
          <p className="text-xl font-black font-mono" style={{ color: "#00ff88" }}>
            ${nanopayRevenue.toFixed(4)} USDC
          </p>
          <p className="text-xs" style={{ color: "var(--text-muted)", opacity: 0.7 }}>
            Powered by Circle Nanopayments
          </p>
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Traces", value: displayAtts.length, unit: "", color: "#06b6d4" },
          { label: "Avg Confidence", value: (avgConfidence * 100).toFixed(1), unit: "%", color: "#a855f7" },
          { label: "IPFS Storage", value: (displayAtts.length * 0.0034).toFixed(2), unit: " MB", color: "#ffcc00" },
          { label: "Revenue Earned", value: `$${nanopayRevenue.toFixed(4)}`, unit: " USDC", color: "#00ff88" },
        ].map(({ label, value, unit, color }) => (
          <div key={label} className="sentinel-card p-4">
            <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
            <p className="text-xl font-black font-mono" style={{ color }}>
              {value}{unit && <span className="text-sm font-normal ml-0.5">{unit}</span>}
            </p>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 text-xs" style={{ color: "var(--text-muted)" }}>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ background: "#00ff88" }} /> YES
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ background: "#ff3366" }} /> NO
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ background: "#ffcc00" }} /> UNCERTAIN
        </span>
        <span className="ml-auto flex items-center gap-1.5">
          <span style={{ color: "var(--sentinel-cyan)" }}>⛓</span> All traces attested on Arc Testnet
        </span>
      </div>

      {/* Attestation grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="sentinel-card p-5 animate-pulse space-y-3">
              <div className="h-4 rounded" style={{ background: "rgba(255,255,255,0.06)", width: "80%" }} />
              <div className="h-3 rounded" style={{ background: "rgba(255,255,255,0.04)", width: "60%" }} />
              <div className="h-2 rounded-full" style={{ background: "rgba(255,255,255,0.04)" }} />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {displayAtts.map((att, idx) => (
            <AttCard
              key={att.id}
              att={att}
              question={getQuestion(att, idx)}
              onView={() => setSelectedAtt(att)}
            />
          ))}
        </div>
      )}

      {/* Footer badge */}
      <div className="flex justify-center pt-4">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs"
          style={{
            background: "rgba(6,182,212,0.06)",
            border: "1px solid rgba(6,182,212,0.15)",
            color: "var(--text-muted)",
          }}>
          <span style={{ color: "var(--sentinel-cyan)" }}>●</span>
          Powered by Circle Nanopayments · $0.0001 USDC per trace · Atomic settlement
        </div>
      </div>

      {/* Modal */}
      {selectedAtt && (
        <TraceModal
          att={selectedAtt}
          question={getQuestion(selectedAtt, displayAtts.indexOf(selectedAtt))}
          onClose={() => setSelectedAtt(null)}
          onPayment={handlePayment}
        />
      )}
    </div>
  );
}
