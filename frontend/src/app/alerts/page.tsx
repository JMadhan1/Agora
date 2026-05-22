"use client";

import { useEffect, useState } from "react";
import { fetchDisputeAlerts } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ArcTxLink } from "@/components/markets/ArcTxLink";
import { Spinner } from "@/components/ui/Spinner";
import { formatPercent, formatTimestamp, formatUSDC } from "@/lib/format";
import type { DisputeAlert } from "@/types";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<DisputeAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDisputeAlerts(100).then(setAlerts).catch(console.error).finally(() => setLoading(false));
    const interval = setInterval(() => fetchDisputeAlerts(100).then(setAlerts).catch(console.error), 10000);
    return () => clearInterval(interval);
  }, []);

  const triggered = alerts.filter(a => a.dispute_triggered).length;
  const won = alerts.filter(a => a.dispute_won).length;
  const totalReward = alerts.reduce((s, a) => s + (a.reward_usdc || 0), 0);

  if (loading) return <div className="flex justify-center mt-20"><Spinner size="lg" /></div>;

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Watchdog Alerts</h1>
        <p className="text-slate-400 mt-1">UMA manipulation detection · {alerts.length} total · {triggered} disputes triggered</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Alerts", value: alerts.length, color: "text-white" },
          { label: "Disputes Triggered", value: triggered, color: "text-red-400" },
          { label: "Disputes Won", value: won, color: "text-green-400" },
          { label: "USDC Rewards", value: formatUSDC(totalReward), color: "text-cyan-400" },
        ].map(({ label, value, color }) => (
          <Card key={label}>
            <p className="text-slate-400 text-sm">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </Card>
        ))}
      </div>

      <Card>
        {alerts.length === 0 ? (
          <p className="text-slate-500 text-center py-10">No alerts yet — Watchdog is monitoring {">"}200 markets.</p>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`p-4 rounded-lg border ${
                  alert.manipulation_suspected
                    ? "border-red-800 bg-red-950/30"
                    : "border-slate-700 bg-slate-800/50"
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      {alert.manipulation_suspected && (
                        <Badge variant="no">⚠️ MANIPULATION SUSPECTED</Badge>
                      )}
                      {alert.dispute_triggered && (
                        <Badge variant="arc">DISPUTE TRIGGERED</Badge>
                      )}
                      {alert.dispute_won === true && (
                        <Badge variant="yes">WON</Badge>
                      )}
                    </div>
                    <p className="text-white text-sm">
                      Market <code className="text-cyan-400">{alert.market_id?.slice(0, 16)}...</code>
                    </p>
                    <p className="text-slate-400 text-sm">
                      Proposed: <span className={alert.proposed_resolution === "YES" ? "text-green-400" : "text-red-400"}>{alert.proposed_resolution}</span>
                      {" · "}
                      Sentinel: <span className="text-white">{formatPercent(alert.our_estimate)}</span>
                      {" · "}
                      Deviation: <span className="text-orange-400 font-bold">{formatPercent(alert.deviation)}</span>
                    </p>
                    <p className="text-slate-500 text-xs">{formatTimestamp(alert.timestamp)}</p>
                  </div>
                  {alert.dispute_tx_hash && (
                    <ArcTxLink txHash={alert.dispute_tx_hash} />
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
