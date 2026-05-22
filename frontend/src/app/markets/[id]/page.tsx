"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchMarket, fetchAttestations } from "@/lib/api";
import type { Market, Attestation } from "@/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { ArcTxLink } from "@/components/markets/ArcTxLink";
import { ReasoningTrace } from "@/components/markets/ReasoningTrace";
import { EvidencePanel } from "@/components/markets/EvidencePanel";
import { formatPercent, formatTimestamp, getRecommendationColor } from "@/lib/format";

export default function MarketDetailPage() {
  const params = useParams();
  const marketId = params.id as string;
  const [market, setMarket] = useState<Market | null>(null);
  const [attestations, setAttestations] = useState<Attestation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [m, atts] = await Promise.all([
          fetchMarket(marketId),
          fetchAttestations(marketId, 20),
        ]);
        setMarket(m);
        setAttestations(atts);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load market");
      } finally {
        setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [marketId]);

  if (loading) return <div className="flex justify-center mt-20"><Spinner size="lg" /></div>;
  if (error) return <div className="text-red-400 mt-10 text-center">{error}</div>;
  if (!market) return null;

  const latestAtt = attestations[0];
  const deviationFromMarket = latestAtt
    ? Math.abs(latestAtt.probability_estimate - market.current_yes_price)
    : 0;

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-2xl font-bold text-white leading-tight">
            {market.question}
          </h1>
          {latestAtt && (
            <Badge variant={latestAtt.recommendation.toLowerCase() as any} className="shrink-0 text-lg px-4 py-2">
              {latestAtt.recommendation}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-4 text-sm text-slate-400">
          <span>Category: <span className="text-white">{market.category}</span></span>
          <span>Resolves: <span className="text-white">{formatTimestamp(market.resolution_date)}</span></span>
          <span>Last scouted: <span className="text-white">{formatTimestamp(market.last_scouted)}</span></span>
          {market.resolved && (
            <Badge variant={market.actual_resolution === "YES" ? "yes" : "no"}>
              RESOLVED: {market.actual_resolution}
            </Badge>
          )}
        </div>
      </div>

      {/* Price Comparison */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <p className="text-slate-400 text-sm">Market Price (YES)</p>
          <p className="text-3xl font-bold text-white mt-1">
            {formatPercent(market.current_yes_price)}
          </p>
          <p className="text-slate-500 text-xs mt-1">Polymarket consensus</p>
        </Card>

        <Card>
          <p className="text-slate-400 text-sm">Sentinel Estimate</p>
          <p className={`text-3xl font-bold mt-1 ${latestAtt ? getRecommendationColor(latestAtt.recommendation) : "text-white"}`}>
            {latestAtt ? formatPercent(latestAtt.probability_estimate) : "—"}
          </p>
          <p className="text-slate-500 text-xs mt-1">Bayesian inference</p>
        </Card>

        <Card>
          <p className="text-slate-400 text-sm">Deviation</p>
          <p className={`text-3xl font-bold mt-1 ${deviationFromMarket > 0.3 ? "text-red-400" : deviationFromMarket > 0.15 ? "text-yellow-400" : "text-green-400"}`}>
            {formatPercent(deviationFromMarket)}
          </p>
          <p className="text-slate-500 text-xs mt-1">
            {deviationFromMarket > 0.4 ? "⚠️ Dispute threshold exceeded" : "Within normal range"}
          </p>
        </Card>
      </div>

      {/* Evidence Panel */}
      <EvidencePanel marketId={marketId} />

      {/* Attestation History */}
      <Card title="Attestation History (Arc Testnet)">
        <div className="space-y-3">
          {attestations.length === 0 ? (
            <p className="text-slate-500 text-sm">No attestations yet</p>
          ) : (
            attestations.map((att) => (
              <div
                key={att.id}
                className="flex items-center justify-between p-3 bg-slate-800 rounded-lg border border-slate-700"
              >
                <div className="flex items-center gap-3">
                  <Badge variant={att.recommendation.toLowerCase() as any}>
                    {att.recommendation}
                  </Badge>
                  <div>
                    <p className="text-white text-sm font-mono">
                      {formatPercent(att.probability_estimate)} probability
                    </p>
                    <p className="text-slate-400 text-xs">
                      Confidence: {att.confidence}% · {formatTimestamp(att.timestamp)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <ArcTxLink txHash={att.arc_tx_hash} />
                  {att.ipfs_cid && (
                    <a
                      href={`https://gateway.irys.xyz/${att.ipfs_cid}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-purple-400 hover:text-purple-300"
                    >
                      IPFS ↗
                    </a>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* Reasoning Trace */}
      {latestAtt && (
        <ReasoningTrace attestation={latestAtt} />
      )}
    </div>
  );
}
