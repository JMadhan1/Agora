"use client";

import { useState } from "react";
import Link from "next/link";
import { MarketTable } from "@/components/markets/MarketTable";
import { MarketCard } from "@/components/markets/MarketCard";
import { Spinner } from "@/components/ui/Spinner";
import { useMarkets } from "@/hooks/useMarkets";

export default function MarketsPage() {
  const { markets, loading, error } = useMarkets(false, 100);
  const [view, setView] = useState<"grid" | "table">("table");
  const [search, setSearch] = useState("");

  const filtered = search
    ? markets.filter(m => m.question?.toLowerCase().includes(search.toLowerCase()))
    : markets;

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black mb-1" style={{
            background: "linear-gradient(90deg, #06b6d4, #a855f7)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>
            Active Markets
          </h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            {loading ? "Loading…" : `${markets.length} markets monitored`} — updating every 10s
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/warroom"
            className="px-3 py-1.5 rounded-lg text-xs font-semibold"
            style={{ background: "rgba(255,51,102,0.1)", color: "#ff3366", border: "1px solid rgba(255,51,102,0.25)" }}>
            🔴 Threat Grid
          </Link>
          <div className="flex gap-1 rounded-lg p-0.5"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            {(["table","grid"] as const).map(v => (
              <button key={v} onClick={() => setView(v)}
                className="px-3 py-1.5 text-xs rounded-md font-medium transition-all capitalize"
                style={{
                  background: view === v ? "rgba(6,182,212,0.15)" : "transparent",
                  color: view === v ? "#06b6d4" : "var(--text-muted)",
                }}>
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Search */}
      <input
        type="text"
        placeholder="Search markets…"
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
        style={{
          background: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(6,182,212,0.15)",
          color: "var(--text-primary)",
        }}
      />

      {error && (
        <div className="rounded-xl p-3 text-sm"
          style={{ background: "rgba(255,51,102,0.08)", color: "#ff3366", border: "1px solid rgba(255,51,102,0.2)" }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center mt-20"><Spinner size="lg" /></div>
      ) : view === "table" ? (
        <div className="sentinel-card overflow-hidden">
          <MarketTable markets={filtered} />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(m => <MarketCard key={m.id} market={m} />)}
        </div>
      )}
    </div>
  );
}
