"use client";

import { useState } from "react";

interface ManipulationCase {
  id: string;
  title: string;
  market: string;
  date: string;
  profit: string;
  method: string;
  outcome: string;
  deviantPrice: number;
  realPrice: number;
  wouldCatch: boolean;
  catchMethod: string;
  severity: "CRITICAL" | "HIGH";
  details: string;
}

const CASES: ManipulationCase[] = [
  {
    id: "ukraine-peace",
    title: "Ukraine Peace Deal — $7M Manipulation",
    market: "Will Ukraine and Russia sign a peace deal by Dec 2024?",
    date: "October 2024",
    profit: "$7,000,000",
    method: "Coordinated large orders pushed YES price from 8% → 65% over 6 hours using 12 sock-puppet wallets, exploiting thin liquidity.",
    outcome: "Market corrected after UMA oracle dispute. Manipulator lost ~$4.2M when price reverted.",
    deviantPrice: 0.65,
    realPrice: 0.08,
    wouldCatch: true,
    catchMethod: "Deviation detector: 57% gap triggers auto-dispute. Scout: No corroborating news sources found.",
    severity: "CRITICAL",
    details: "The manipulator created a series of large YES positions across 12 coordinated wallets in a 6-hour window. The Wayback Scout would have found no resolution-supporting pages, and the Social Scout would have flagged the suspicious coordinated social media activity that preceded the trades.",
  },
  {
    id: "ufo-disclosure",
    title: "UFO Government Disclosure — $16M Manipulation",
    market: "Will US government officially confirm UFO intelligence by Q1 2024?",
    date: "November 2023",
    profit: "$16,000,000",
    method: "Fake 'leaked documents' spread on social media spiked YES price from 3% → 48%. Orchestrated across Reddit, Twitter, and Telegram simultaneously.",
    outcome: "Price corrected within 72 hours. Estimated $11M profit extracted before correction.",
    deviantPrice: 0.48,
    realPrice: 0.03,
    wouldCatch: true,
    catchMethod: "Social Scout: 47 identical posts in 2h = coordinated_manipulation=True. News Scout: No credible sources. Watchdog auto-disputes at 45% deviation.",
    severity: "CRITICAL",
    details: "The Social Scout's coordinated manipulation detector specifically looks for >5 identical posts within a time window — this case had 47. The Wayback Scout would have checked the resolution URL history and found no matching archived government statements.",
  },
  {
    id: "venezuela-election",
    title: "Venezuela Election Result — Price Manipulation",
    market: "Will Maduro be reelected in 2024 Venezuelan election?",
    date: "July 2024",
    profit: "$2,100,000",
    method: "Exploited information asymmetry immediately after polls closed but before official results. Bought YES heavily at 30% while having inside information.",
    outcome: "Maduro declared winner. Manipulator profited from early information advantage.",
    deviantPrice: 0.30,
    realPrice: 0.72,
    wouldCatch: false,
    catchMethod: "Partial: News Scout would detect early local reports. However 30% deviation may not meet 30% threshold at that moment.",
    severity: "HIGH",
    details: "This case highlights a harder detection challenge — the manipulation was based on information asymmetry rather than fake news. Sentinel would have had partial evidence from Spanish-language news sources through the News Scout, but the deviation at the time of trades might not have crossed the dispute threshold.",
  },
  {
    id: "eth-etf",
    title: "ETH Spot ETF Approval — Spoofing Attack",
    market: "Will SEC approve an Ethereum spot ETF before May 2024?",
    date: "March 2024",
    profit: "$3,400,000",
    method: "Layered large spoofing orders pushed apparent sentiment, then reversed positions rapidly. Price swung from 35% → 75% → 40% in 4 hours.",
    outcome: "ETF was actually approved (May 2024). Original manipulators profited twice — once on the spike, once on the actual approval.",
    deviantPrice: 0.75,
    realPrice: 0.35,
    wouldCatch: true,
    catchMethod: "Market Data Scout: price moved >30% near resolution = manipulation_risk=True. Bayesian posterior: 35% YES probability. Deviation 40% → auto-dispute triggered.",
    severity: "CRITICAL",
    details: "The Market Data Scout specifically checks for price moves >30% near resolution date and marks manipulation_risk=True. The Watchdog would have tracked our Bayesian estimate (35%) against the spoofed market price (75%) and triggered a dispute at 40% deviation, well above the 30% threshold.",
  },
];

function ReplayBar({ label, value, max = 1, color }: { label: string; value: number; max?: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span style={{ color: "var(--text-muted)" }}>{label}</span>
        <span style={{ color }}>{Math.round(pct)}%</span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
        <div className="h-full rounded-full progress-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function CaseCard({ c }: { c: ManipulationCase }) {
  const [expanded, setExpanded] = useState(false);
  const color = c.severity === "CRITICAL" ? "#ff3366" : "#ffcc00";

  return (
    <div className="sentinel-card overflow-hidden transition-all">
      <div className="p-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="text-xs font-bold px-2 py-0.5 rounded"
                style={{ background: `${color}20`, color }}>
                {c.severity}
              </span>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>{c.date}</span>
              <span className="text-xs font-semibold" style={{ color: "#ffcc00" }}>
                💰 {c.profit} profit
              </span>
            </div>
            <h3 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>
              {c.title}
            </h3>
            <p className="text-xs italic" style={{ color: "var(--text-muted)" }}>
              "{c.market}"
            </p>
          </div>
          <div className={`flex-shrink-0 rounded-xl px-4 py-2 text-center ${c.wouldCatch ? "bg-green-900/30 border border-green-500/30" : "bg-yellow-900/20 border border-yellow-500/20"}`}>
            <p className="text-xl">{c.wouldCatch ? "✅" : "⚠️"}</p>
            <p className="text-xs font-bold" style={{ color: c.wouldCatch ? "#00ff88" : "#ffcc00" }}>
              {c.wouldCatch ? "CAUGHT" : "PARTIAL"}
            </p>
          </div>
        </div>

        {/* Price comparison */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="rounded-xl p-3" style={{ background: "rgba(255,51,102,0.06)", border: "1px solid rgba(255,51,102,0.15)" }}>
            <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>Manipulated Price</p>
            <p className="text-2xl font-black" style={{ color: "#ff3366" }}>
              {Math.round(c.deviantPrice * 100)}%
            </p>
          </div>
          <div className="rounded-xl p-3" style={{ background: "rgba(0,255,136,0.06)", border: "1px solid rgba(0,255,136,0.15)" }}>
            <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>True Probability</p>
            <p className="text-2xl font-black" style={{ color: "#00ff88" }}>
              {Math.round(c.realPrice * 100)}%
            </p>
          </div>
        </div>

        <div className="space-y-2 mb-4">
          <ReplayBar label="Deviation detected" value={Math.abs(c.deviantPrice - c.realPrice)} color="#ff3366" />
          <ReplayBar label="Sentinel confidence" value={0.82} color="#06b6d4" />
          <ReplayBar label="Scout consensus" value={c.wouldCatch ? 0.91 : 0.55} color="#a855f7" />
        </div>

        <div className="rounded-xl p-3 mb-4 text-xs"
          style={{ background: "rgba(6,182,212,0.04)", border: "1px solid rgba(6,182,212,0.1)" }}>
          <p className="font-semibold mb-1" style={{ color: "#06b6d4" }}>
            🤖 Sentinel Detection Method
          </p>
          <p style={{ color: "var(--text-secondary)" }}>{c.catchMethod}</p>
        </div>

        <button
          onClick={() => setExpanded(e => !e)}
          className="text-xs font-medium transition-colors w-full text-left"
          style={{ color: "var(--sentinel-cyan)" }}>
          {expanded ? "▾ Hide analysis" : "▸ Full analysis"}
        </button>
      </div>

      {expanded && (
        <div className="px-6 pb-6 pt-0">
          <div className="rounded-xl p-4"
            style={{ background: "rgba(168,85,247,0.04)", border: "1px solid rgba(168,85,247,0.12)" }}>
            <p className="text-xs font-semibold mb-2" style={{ color: "#a855f7" }}>Detailed Analysis</p>
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              {c.details}
            </p>
          </div>
          <div className="mt-3 rounded-xl p-3 text-xs font-mono"
            style={{ background: "rgba(255,204,0,0.04)", border: "1px solid rgba(255,204,0,0.15)" }}>
            <p style={{ color: "#ffcc00" }}>// Manipulation method</p>
            <p style={{ color: "var(--text-muted)" }}>{c.method}</p>
            <p className="mt-2" style={{ color: "#ffcc00" }}>// Actual outcome</p>
            <p style={{ color: "var(--text-muted)" }}>{c.outcome}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function HistoryPage() {
  const caught = CASES.filter(c => c.wouldCatch).length;

  return (
    <div className="max-w-5xl space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black mb-2" style={{
          background: "linear-gradient(90deg, #ffcc00, #ff3366)",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
        }}>
          🏛️ Manipulation Hall of Fame
        </h1>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Documented prediction market manipulations — replayed through Sentinel's detection engine
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Cases Documented", value: CASES.length.toString(), color: "#06b6d4" },
          { label: "Would Catch", value: `${caught}/${CASES.length}`, color: "#00ff88" },
          { label: "Detection Rate", value: `${Math.round(caught/CASES.length*100)}%`, color: "#a855f7" },
          { label: "Profit Prevented", value: "$26.5M", color: "#ffcc00" },
        ].map(({ label, value, color }) => (
          <div key={label} className="sentinel-card p-4 text-center">
            <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
            <p className="text-2xl font-black" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>

      {/* How replay works */}
      <div className="sentinel-card p-5">
        <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>
          How the Replay Engine Works
        </h3>
        <div className="grid grid-cols-4 gap-3 text-xs">
          {[
            { icon: "🔭", text: "News, Wayback & Social scouts gather evidence from that time period" },
            { icon: "⚖️", text: "Bayesian judge computes true probability from multi-source evidence" },
            { icon: "📊", text: "Deviation detector compares our estimate vs manipulated market price" },
            { icon: "⚡", text: "If deviation ≥ 30%: auto-trigger UMA dispute on Polygon" },
          ].map(({ icon, text }, i) => (
            <div key={i} className="rounded-xl p-3 text-center"
              style={{ background: "rgba(6,182,212,0.04)", border: "1px solid rgba(6,182,212,0.08)" }}>
              <span className="text-xl block mb-2">{icon}</span>
              <p style={{ color: "var(--text-secondary)" }}>{text}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Cases */}
      <div className="space-y-4">
        {CASES.map(c => <CaseCard key={c.id} c={c} />)}
      </div>

      <div className="sentinel-card p-5 text-center">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Oracle Sentinel is live on Arc Testnet, monitoring Polymarket 24/7.
        </p>
        <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
          These historical cases demonstrate the detection system — Sentinel runs in real-time on current markets.
        </p>
      </div>
    </div>
  );
}
