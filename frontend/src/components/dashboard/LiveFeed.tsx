"use client";

import { useEffect, useState } from "react";
import { ArcTxLink } from "@/components/markets/ArcTxLink";
import { Spinner } from "@/components/ui/Spinner";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAttestations } from "@/hooks/useAttestations";
import { formatPercent, formatTimestamp } from "@/lib/format";
import type { Attestation } from "@/types";

function RecBadge({ rec }: { rec: string }) {
  const map: Record<string, { color: string; bg: string; label: string }> = {
    YES:       { color: "#00ff88", bg: "rgba(0,255,136,0.1)",  label: "YES" },
    NO:        { color: "#ff3366", bg: "rgba(255,51,102,0.1)", label: "NO" },
    UNCERTAIN: { color: "#ffcc00", bg: "rgba(255,204,0,0.1)",  label: "UNCERTAIN" },
  };
  const style = map[rec?.toUpperCase()] ?? map.UNCERTAIN;
  return (
    <span className="text-xs font-bold px-2 py-0.5 rounded flex-shrink-0"
      style={{ background: style.bg, color: style.color, border: `1px solid ${style.color}30` }}>
      {style.label}
    </span>
  );
}

export function LiveFeed() {
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
  const { lastMessage } = useWebSocket(wsUrl);
  const { attestations, loading } = useAttestations(undefined, 20);
  const [live, setLive] = useState<Attestation[]>([]);
  const [newIds, setNewIds] = useState<Set<string | number>>(new Set());

  useEffect(() => { setLive(attestations); }, [attestations]);

  useEffect(() => {
    if (lastMessage && typeof lastMessage === "object" && (lastMessage as any).type === "attestation") {
      const item = (lastMessage as any).data as Attestation;
      setLive(prev => [item, ...prev].slice(0, 20));
      setNewIds(prev => new Set(prev).add(item.id));
      setTimeout(() => setNewIds(prev => { const s = new Set(prev); s.delete(item.id); return s; }), 2000);
    }
  }, [lastMessage]);

  return (
    <div className="sentinel-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="status-dot live" />
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
            Live Attestation Feed
          </h2>
        </div>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {live.length} records
        </span>
      </div>

      <div className="space-y-1.5 max-h-[520px] overflow-y-auto">
        {loading && live.length === 0 ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : live.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-3xl mb-2">🔭</p>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              No attestations yet — start agents to see live feed.
            </p>
          </div>
        ) : (
          live.map((att) => (
            <div key={att.id}
              className="flex items-center gap-3 p-3 rounded-xl transition-all"
              style={{
                background: newIds.has(att.id) ? "rgba(6,182,212,0.08)" : "rgba(255,255,255,0.02)",
                border: newIds.has(att.id) ? "1px solid rgba(6,182,212,0.3)" : "1px solid rgba(255,255,255,0.04)",
                transition: "background 0.5s ease, border-color 0.5s ease",
              }}>
              <RecBadge rec={att.recommendation} />
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate" style={{ color: "var(--text-primary)" }}>
                  {att.market_id?.slice(0, 32)}…
                </p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {formatPercent(att.probability_estimate)} ·{" "}
                  <span style={{ color: "#06b6d4" }}>{att.confidence}%</span> conf ·{" "}
                  {formatTimestamp(att.timestamp)}
                </p>
              </div>
              <ArcTxLink txHash={att.arc_tx_hash} compact />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
