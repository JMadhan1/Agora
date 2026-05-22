"use client";

import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useAttestations } from "@/hooks/useAttestations";
import { formatPercent } from "@/lib/format";

const SCOUT_ICONS: Record<string, string> = {
  news: "📰",
  onchain: "⛓️",
  wayback: "🕰️",
  market_data: "📊",
  social: "💬",
};

interface Props { marketId: string; }

export function EvidencePanel({ marketId }: Props) {
  const { attestations, loading } = useAttestations(marketId, 1);
  const latest = attestations[0];

  if (loading) return <Card title="Scout Evidence"><div className="flex justify-center py-6"><Spinner /></div></Card>;
  if (!latest) return <Card title="Scout Evidence"><p className="text-slate-500 text-sm py-4">No evidence gathered yet.</p></Card>;

  // Parse evidence from IPFS trace if available, otherwise show placeholder
  const scouts = [
    { type: "news", label: "News Scout", reliability: 0.75 },
    { type: "onchain", label: "On-chain Scout", reliability: 0.95 },
    { type: "wayback", label: "Wayback Machine", reliability: 0.85 },
    { type: "market_data", label: "Market Data", reliability: 0.70 },
    { type: "social", label: "Social Sentiment", reliability: 0.55 },
  ];

  return (
    <Card title="Scout Evidence">
      <div className="space-y-3">
        {scouts.map(({ type, label, reliability }) => (
          <div key={type} className="flex items-center gap-3">
            <span className="text-xl w-8">{SCOUT_ICONS[type]}</span>
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-white">{label}</span>
                <span className="text-xs text-slate-400">Reliability: {formatPercent(reliability)}</span>
              </div>
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-600 to-violet-600 rounded-full"
                  style={{ width: `${reliability * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
        {latest.ipfs_cid && (
          <a
            href={`https://gateway.irys.xyz/${latest.ipfs_cid}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-purple-400 hover:text-purple-300 block mt-2"
          >
            View full reasoning trace on IPFS ↗
          </a>
        )}
      </div>
    </Card>
  );
}
