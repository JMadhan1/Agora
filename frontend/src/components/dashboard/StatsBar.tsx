import { formatPercent, formatUSDC } from "@/lib/format";
import type { SystemStats } from "@/types";

interface Props { stats: SystemStats | null; }

const ITEMS = [
  {
    key: "total_attestations",
    label: "Attestations",
    sub: "Arc Testnet",
    icon: "🔐",
    accent: "#06b6d4",
    format: (v: number) => v.toLocaleString(),
  },
  {
    key: "total_markets_monitored",
    label: "Markets Watched",
    sub: "Polymarket",
    icon: "📊",
    accent: "#a855f7",
    format: (v: number) => v.toLocaleString(),
  },
  {
    key: "calibration_accuracy",
    label: "Accuracy",
    sub: "Calibration",
    icon: "🎯",
    accent: "#00ff88",
    format: (v: number) => formatPercent(v),
  },
  {
    key: "total_disputes_triggered",
    label: "Disputes",
    sub: "manipulation flags",
    icon: "⚡",
    accent: "#ff3366",
    format: (v: number) => v.toLocaleString(),
  },
  {
    key: "usdc_earned",
    label: "USDC Earned",
    sub: "ERC-8183 jobs",
    icon: "💵",
    accent: "#06b6d4",
    format: (v: number) => formatUSDC(v),
  },
  {
    key: "usyc_deployed",
    label: "USYC Yield",
    sub: "idle capital",
    icon: "📈",
    accent: "#ffcc00",
    format: (v: number) => formatUSDC(v),
  },
] as const;

export function StatsBar({ stats }: Props) {
  return (
    <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
      {ITEMS.map(({ key, label, sub, icon, accent, format }) => {
        const raw = stats?.[key as keyof SystemStats];
        const value = raw !== undefined && raw !== null ? format(raw as number) : "—";
        return (
          <div key={key} className="sentinel-card p-4 flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</span>
              <span className="text-sm">{icon}</span>
            </div>
            <p className="text-xl font-black" style={{ color: accent }}>{value}</p>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>{sub}</p>
          </div>
        );
      })}
    </div>
  );
}
