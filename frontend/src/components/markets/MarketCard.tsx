import Link from "next/link";
import { formatPercent, formatTimestamp } from "@/lib/format";
import type { Market } from "@/types";

interface Props { market: Market; }

export function MarketCard({ market }: Props) {
  const deviation = Math.abs((market.our_latest_estimate || 0.5) - market.current_yes_price);
  const deviationHigh = deviation > 0.15;
  const deviationCritical = deviation > 0.3;

  const borderColor = deviationCritical ? "rgba(255,51,102,0.4)" : deviationHigh ? "rgba(255,204,0,0.3)" : "rgba(6,182,212,0.12)";

  return (
    <Link href={`/markets/${market.id}`}>
      <div className="sentinel-card p-4 h-full cursor-pointer"
        style={{ borderColor }}>
        <div className="space-y-3">
          <p className="text-sm font-medium leading-snug line-clamp-2"
            style={{ color: "var(--text-primary)" }}>
            {market.question}
          </p>

          <div className="flex items-center justify-between">
            <span className="text-xs px-2 py-0.5 rounded-full"
              style={{ background: "rgba(255,255,255,0.06)", color: "var(--text-muted)" }}>
              {market.category || "General"}
            </span>
            {market.resolved ? (
              <span className="text-xs font-bold px-2 py-0.5 rounded"
                style={{
                  background: market.actual_resolution === "YES" ? "rgba(0,255,136,0.1)" : "rgba(255,51,102,0.1)",
                  color: market.actual_resolution === "YES" ? "#00ff88" : "#ff3366",
                }}>
                RESOLVED {market.actual_resolution}
              </span>
            ) : deviationHigh ? (
              <span className="text-xs font-bold px-2 py-0.5 rounded"
                style={{ background: "rgba(255,51,102,0.1)", color: "#ff3366" }}>
                ⚠ {formatPercent(deviation)} gap
              </span>
            ) : null}
          </div>

          <div className="space-y-2">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span style={{ color: "var(--text-muted)" }}>Market</span>
                <span style={{ color: "#a855f7" }}>{formatPercent(market.current_yes_price)}</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                <div className="h-full rounded-full progress-fill"
                  style={{ width: `${market.current_yes_price * 100}%`, background: "#a855f7" }} />
              </div>
            </div>

            {market.our_latest_estimate > 0 && (
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span style={{ color: "var(--text-muted)" }}>Sentinel</span>
                  <span style={{ color: "#06b6d4" }}>{formatPercent(market.our_latest_estimate)}</span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                  <div className="h-full rounded-full progress-fill"
                    style={{ width: `${market.our_latest_estimate * 100}%`, background: "#06b6d4" }} />
                </div>
              </div>
            )}
          </div>

          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Scouted {formatTimestamp(market.last_scouted)}
          </p>
        </div>
      </div>
    </Link>
  );
}
