import Link from "next/link";
import type { DisputeAlert } from "@/types";
import { formatPercent } from "@/lib/format";

interface Props { alerts: DisputeAlert[]; }

export function AlertBanner({ alerts }: Props) {
  if (alerts.length === 0) return null;
  const latest = alerts[0];
  return (
    <div className="rounded-xl p-4 flex items-center gap-4"
      style={{
        background: "rgba(255,51,102,0.08)",
        border: "1px solid rgba(255,51,102,0.35)",
        animation: "threat-pulse 1.5s ease-in-out infinite",
      }}>
      <div className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center text-xl"
        style={{ background: "rgba(255,51,102,0.15)" }}>
        ⚠️
      </div>
      <div className="flex-1">
        <p className="font-semibold text-sm" style={{ color: "#ff3366" }}>
          {alerts.length} active manipulation alert{alerts.length > 1 ? "s" : ""} detected
        </p>
        <p className="text-xs mt-0.5" style={{ color: "rgba(255,51,102,0.7)" }}>
          Latest: Market <code className="font-mono">{latest.market_id?.slice(0, 12)}…</code>{" "}
          — proposed <strong>{latest.proposed_resolution}</strong> but Sentinel estimates{" "}
          <strong>{formatPercent(latest.our_estimate)}</strong> YES
          ({formatPercent(latest.deviation)} deviation)
        </p>
      </div>
      <Link href="/warroom"
        className="flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
        style={{
          background: "rgba(255,51,102,0.2)",
          color: "#ff3366",
          border: "1px solid rgba(255,51,102,0.4)",
        }}>
        War Room →
      </Link>
    </div>
  );
}
