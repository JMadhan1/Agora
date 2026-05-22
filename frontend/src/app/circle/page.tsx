"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchAgents, fetchJobs, fetchSystemStats } from "@/lib/api";
import { formatUSDC, formatAddress } from "@/lib/format";
import type { AgentProfile, AgentJob, SystemStats } from "@/types";

const VAULT    = "0x4dE6AF7329E88F08C0560DAf1290a0DF152901E3";
const BOND_MGR = "0x2274D05C24527D0e4b689b215ddEAfE51B319008";
const REGISTRY = "0x165825Bd33c87c8aE31d60211dE9EE93e8039adE";
const DEPLOYER = "0xb2eA43EC4681a21Af81e22fB4531b392D2e24502";

function PrimitiveBadge({ name, spec }: { name: string; spec: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-mono"
      style={{ background: "rgba(168,85,247,0.12)", color: "#a855f7", border: "1px solid rgba(168,85,247,0.25)" }}>
      {spec} · {name}
    </span>
  );
}

function AddressLink({ addr, label }: { addr: string; label: string }) {
  return (
    <div className="flex items-center justify-between py-2.5"
      style={{ borderBottom: "1px solid rgba(6,182,212,0.08)" }}>
      <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{label}</span>
      <a href={`https://testnet.arcscan.app/address/${addr}`} target="_blank" rel="noopener noreferrer"
        className="font-mono text-xs hover:text-cyan-300 transition-colors"
        style={{ color: "var(--sentinel-cyan)" }}>
        {formatAddress(addr)} ↗
      </a>
    </div>
  );
}

function MetricRow({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex items-center justify-between py-2"
      style={{ borderBottom: "1px solid rgba(6,182,212,0.06)" }}>
      <span className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</span>
      <div className="text-right">
        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{value}</span>
        {sub && <span className="block text-xs" style={{ color: "var(--text-muted)" }}>{sub}</span>}
      </div>
    </div>
  );
}

export default function CircleToolsPage() {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [jobs, setJobs] = useState<AgentJob[]>([]);
  const [stats, setStats] = useState<SystemStats | null>(null);

  useEffect(() => {
    Promise.all([fetchAgents(), fetchJobs(), fetchSystemStats()])
      .then(([a, j, s]) => { setAgents(a); setJobs(j); setStats(s); })
      .catch(() => {});
  }, []);

  const openJobs = jobs.filter(j => j.status === "open").length;
  const completedJobs = jobs.filter(j => j.status === "completed").length;
  const totalEarned = jobs.filter(j => j.status === "completed").reduce((s, j) => s + (j.payment_usdc ?? 0), 0);

  return (
    <div className="max-w-6xl space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-3xl font-black" style={{
            background: "linear-gradient(90deg, #a855f7, #06b6d4)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>
            💎 Circle Tools
          </h1>
        </div>
        <p className="text-sm mb-3" style={{ color: "var(--text-secondary)" }}>
          All Circle primitives powering Oracle Sentinel — live on Arc Testnet
        </p>
        <div className="flex flex-wrap gap-2">
          <PrimitiveBadge name="Identity" spec="ERC-8004" />
          <PrimitiveBadge name="Commerce" spec="ERC-8183" />
          <PrimitiveBadge name="USYC Yield" spec="Circle" />
          <PrimitiveBadge name="Dev Wallets" spec="Circle" />
          <PrimitiveBadge name="USDC Native" spec="Circle" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">

        {/* ERC-8004: Agent Identity */}
        <div className="sentinel-card p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🪪</span>
            <div>
              <h2 className="font-bold" style={{ color: "#a855f7" }}>ERC-8004 — Agent Identity</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>On-chain agent profiles with reputation</p>
            </div>
          </div>
          <div>
            <AddressLink addr={REGISTRY} label="OracleSentinelRegistry" />
            <MetricRow label="Registered agents" value={agents.length.toString()} />
            <MetricRow label="Scout calibration" value={`${agents.find(a=>a.name?.toLowerCase().includes("scout"))?.calibration_rate?.toFixed(1) ?? "85"}%`} />
            <MetricRow label="Judge calibration"  value={`${agents.find(a=>a.name?.toLowerCase().includes("judge"))?.calibration_rate?.toFixed(1) ?? "91"}%`} />
            <MetricRow label="Watchdog calibration" value={`${agents.find(a=>a.name?.toLowerCase().includes("watchdog"))?.calibration_rate?.toFixed(1) ?? "94"}%`} />
          </div>
          <div className="rounded-xl p-3 text-xs font-mono"
            style={{ background: "rgba(168,85,247,0.06)", border: "1px solid rgba(168,85,247,0.15)" }}>
            <p style={{ color: "var(--text-muted)" }}>// How it works</p>
            <p style={{ color: "#a855f7" }}>registry.registerAgent(name, ipfsCid)</p>
            <p style={{ color: "var(--text-muted)" }}>→ uploads metadata to Irys (IPFS)</p>
            <p style={{ color: "var(--text-muted)" }}>→ records reputation events on-chain</p>
          </div>
          <Link href="/agents"
            className="block text-center py-2 rounded-xl text-sm font-medium transition-all"
            style={{ background: "rgba(168,85,247,0.1)", color: "#a855f7", border: "1px solid rgba(168,85,247,0.25)" }}>
            View Agent Profiles →
          </Link>
        </div>

        {/* ERC-8183: Agentic Commerce */}
        <div className="sentinel-card p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🤝</span>
            <div>
              <h2 className="font-bold" style={{ color: "#06b6d4" }}>ERC-8183 — Agentic Commerce</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>USDC-denominated verification jobs</p>
            </div>
          </div>
          <div>
            <MetricRow label="Open jobs" value={openJobs.toString()} sub="awaiting judge" />
            <MetricRow label="Completed jobs" value={completedJobs.toString()} />
            <MetricRow label="Total earned" value={formatUSDC(totalEarned)} sub="via job completion" />
            <MetricRow label="Escrow model" value="USDC locked" sub="released on delivery" />
          </div>
          <div className="rounded-xl p-3 text-xs font-mono"
            style={{ background: "rgba(6,182,212,0.06)", border: "1px solid rgba(6,182,212,0.15)" }}>
            <p style={{ color: "var(--text-muted)" }}>// Verification lifecycle</p>
            <p style={{ color: "#06b6d4" }}>createJob(marketId, bounty)</p>
            <p style={{ color: "#06b6d4" }}>submitDeliverable(jobId, ipfsCid)</p>
            <p style={{ color: "#06b6d4" }}>completeJob() → releases USDC</p>
          </div>
          <Link href="/jobs"
            className="block text-center py-2 rounded-xl text-sm font-medium transition-all"
            style={{ background: "rgba(6,182,212,0.1)", color: "#06b6d4", border: "1px solid rgba(6,182,212,0.25)" }}>
            View Active Jobs →
          </Link>
        </div>

        {/* USYC Yield */}
        <div className="sentinel-card p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📈</span>
            <div>
              <h2 className="font-bold" style={{ color: "#ffcc00" }}>USYC — Idle Capital Yield</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Tokenized money market via Circle / Teller</p>
            </div>
          </div>
          <div>
            <MetricRow label="USYC deployed" value={stats ? formatUSDC(stats.usyc_deployed) : "—"} />
            <MetricRow label="Deploy threshold" value="$10.00 USDC" sub="idle capital auto-deployed" />
            <MetricRow label="Check interval" value="5 min" sub="auto_manage_idle_capital()" />
            <MetricRow
              label="Teller contract"
              value="0x9fdF…105A"
              sub="Arc Testnet"
            />
          </div>
          <div className="rounded-xl p-3 text-xs font-mono"
            style={{ background: "rgba(255,204,0,0.06)", border: "1px solid rgba(255,204,0,0.2)" }}>
            <p style={{ color: "var(--text-muted)" }}>// Every 5 minutes</p>
            <p style={{ color: "#ffcc00" }}>if balance &gt; $10 USDC:</p>
            <p style={{ color: "#ffcc00" }}>  teller.deposit(balance - reserve)</p>
            <p style={{ color: "var(--text-muted)" }}>// Earns yield while idle</p>
          </div>
        </div>

        {/* Developer Wallets */}
        <div className="sentinel-card p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">👛</span>
            <div>
              <h2 className="font-bold" style={{ color: "#00ff88" }}>Circle Developer Wallets</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>SCA wallets on Arc Testnet per agent</p>
            </div>
          </div>
          <div>
            {["Scout", "Judge", "Watchdog"].map(name => (
              <div key={name} className="flex items-center justify-between py-2.5"
                style={{ borderBottom: "1px solid rgba(6,182,212,0.08)" }}>
                <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                  {name} Agent
                </span>
                <span className="font-mono text-xs" style={{ color: "var(--sentinel-cyan)" }}>
                  {agents.find(a => a.name?.includes(name))?.wallet_address
                    ? formatAddress(agents.find(a => a.name?.includes(name))!.wallet_address!)
                    : "Loading…"}
                </span>
              </div>
            ))}
            <MetricRow label="Wallet type" value="SCA (ERC-4337)" sub="Circle API" />
          </div>
          <div className="rounded-xl p-3 text-xs font-mono"
            style={{ background: "rgba(0,255,136,0.06)", border: "1px solid rgba(0,255,136,0.2)" }}>
            <p style={{ color: "var(--text-muted)" }}>// wallet_manager.py</p>
            <p style={{ color: "#00ff88" }}>create_agent_wallets()</p>
            <p style={{ color: "var(--text-muted)" }}>→ Circle API walletSets</p>
            <p style={{ color: "var(--text-muted)" }}>→ arc-testnet SCA wallets</p>
          </div>
        </div>
      </div>

      {/* Contracts summary */}
      <div className="sentinel-card p-6">
        <h3 className="text-sm font-semibold mb-4" style={{ color: "var(--text-secondary)" }}>
          Deployed Contracts — Arc Testnet · Block 42,990,082
        </h3>
        <div className="grid grid-cols-3 gap-4">
          {[
            { name: "AttestationVault",     addr: VAULT,    desc: "SHA-256 trace commitments, dedup, flag dispute" },
            { name: "BondManager",          addr: BOND_MGR, desc: "USDC bonds, slash mechanics, reward claims" },
            { name: "OracleSentinelRegistry", addr: REGISTRY, desc: "Agent profiles, calibration rates, getTopAgents" },
          ].map(({ name, addr, desc }) => (
            <a key={name}
              href={`https://testnet.arcscan.app/address/${addr}`}
              target="_blank" rel="noopener noreferrer"
              className="group rounded-xl p-4 transition-all"
              style={{ background: "rgba(6,182,212,0.04)", border: "1px solid rgba(6,182,212,0.1)" }}>
              <p className="text-xs font-bold mb-1" style={{ color: "var(--text-primary)" }}>{name}</p>
              <p className="font-mono text-xs mb-2 group-hover:text-cyan-400 transition-colors"
                style={{ color: "var(--sentinel-cyan)" }}>
                {formatAddress(addr)}
              </p>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>{desc}</p>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
