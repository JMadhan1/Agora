"use client";

import { useState } from "react";
import Link from "next/link";
import { formatPercent, formatTimestamp } from "@/lib/format";
import type { Market } from "@/types";

interface Props { markets: Market[]; }

type SortKey = "volume" | "deviation" | "scouted";

export function MarketTable({ markets }: Props) {
  const [sort, setSort] = useState<SortKey>("scouted");

  const sorted = [...markets].sort((a, b) => {
    if (sort === "deviation") {
      const da = Math.abs((a.our_latest_estimate || 0.5) - a.current_yes_price);
      const db = Math.abs((b.our_latest_estimate || 0.5) - b.current_yes_price);
      return db - da;
    }
    if (sort === "scouted") return new Date(b.last_scouted || 0).getTime() - new Date(a.last_scouted || 0).getTime();
    return 0;
  });

  const thStyle = (key: SortKey) => ({
    cursor: "pointer",
    color: sort === key ? "#06b6d4" : "var(--text-muted)",
    fontSize: "0.65rem",
    fontWeight: 600,
    letterSpacing: "0.1em",
    textTransform: "uppercase" as const,
    userSelect: "none" as const,
    paddingBottom: "0.75rem",
    paddingRight: "1rem",
  });

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr style={{ borderBottom: "1px solid rgba(6,182,212,0.1)" }}>
            <th style={{ ...thStyle("scouted"), cursor: "default" }} className="text-left pr-4">Question</th>
            <th style={thStyle("deviation")} className="text-left pr-4" onClick={() => setSort("deviation")}>
              Deviation {sort === "deviation" ? "↓" : "↕"}
            </th>
            <th style={{ ...thStyle("scouted"), cursor: "default" }} className="text-left pr-4">Market</th>
            <th style={{ ...thStyle("scouted"), cursor: "default" }} className="text-left pr-4">Sentinel</th>
            <th style={thStyle("scouted")} className="text-left pr-4" onClick={() => setSort("scouted")}>
              Scouted {sort === "scouted" ? "↓" : "↕"}
            </th>
            <th style={{ ...thStyle("scouted"), cursor: "default" }} className="text-left">Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((m) => {
            const deviation = Math.abs((m.our_latest_estimate || 0.5) - m.current_yes_price);
            const isCritical = deviation > 0.3;
            const isHigh = deviation > 0.15;
            const devColor = isCritical ? "#ff3366" : isHigh ? "#ffcc00" : "var(--text-muted)";

            return (
              <tr key={m.id} className="sentinel-row"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                <td className="py-3 pr-4 max-w-xs">
                  <Link href={`/markets/${m.id}`}
                    className="block line-clamp-1 transition-colors hover:text-cyan-400"
                    style={{ color: "var(--text-primary)" }}>
                    {m.question}
                  </Link>
                </td>
                <td className="py-3 pr-4">
                  <span className="font-mono font-bold text-xs" style={{ color: devColor }}>
                    {isCritical && "⚠ "}{formatPercent(deviation)}
                  </span>
                </td>
                <td className="py-3 pr-4 font-mono text-xs" style={{ color: "#a855f7" }}>
                  {formatPercent(m.current_yes_price)}
                </td>
                <td className="py-3 pr-4 font-mono text-xs" style={{ color: "#06b6d4" }}>
                  {m.our_latest_estimate ? formatPercent(m.our_latest_estimate) : "—"}
                </td>
                <td className="py-3 pr-4 text-xs" style={{ color: "var(--text-muted)" }}>
                  {formatTimestamp(m.last_scouted)}
                </td>
                <td className="py-3">
                  {m.resolved ? (
                    <span className="text-xs font-bold px-2 py-0.5 rounded"
                      style={{
                        background: m.actual_resolution === "YES" ? "rgba(0,255,136,0.1)" : "rgba(255,51,102,0.1)",
                        color: m.actual_resolution === "YES" ? "#00ff88" : "#ff3366",
                      }}>
                      {m.actual_resolution}
                    </span>
                  ) : (
                    <span className="text-xs font-bold px-2 py-0.5 rounded"
                      style={{ background: "rgba(6,182,212,0.1)", color: "#06b6d4" }}>
                      LIVE
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
