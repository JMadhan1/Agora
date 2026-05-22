"use client";

import { useEffect, useState } from "react";
import { fetchJobs } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ArcTxLink } from "@/components/markets/ArcTxLink";
import { Spinner } from "@/components/ui/Spinner";
import { formatUSDC, formatTimestamp } from "@/lib/format";
import type { AgentJob } from "@/types";

function statusVariant(status: string): "yes" | "no" | "uncertain" | "arc" {
  if (status === "COMPLETED") return "yes";
  if (status === "FAILED") return "no";
  if (status === "FUNDED") return "arc";
  return "uncertain";
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<AgentJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchJobs(undefined, 100).then(setJobs).catch(console.error).finally(() => setLoading(false));
    const interval = setInterval(() => fetchJobs(undefined, 100).then(setJobs).catch(console.error), 15000);
    return () => clearInterval(interval);
  }, []);

  const totalEarned = jobs.filter(j => j.status === "COMPLETED").reduce((s, j) => s + (j.usdc_earned || 0), 0);

  if (loading) return <div className="flex justify-center mt-20"><Spinner size="lg" /></div>;

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">ERC-8183 Jobs</h1>
          <p className="text-slate-400 mt-1">Agentic Commerce on Arc Testnet · {jobs.length} total jobs</p>
        </div>
        <div className="text-right">
          <p className="text-slate-400 text-sm">Total USDC Earned</p>
          <p className="text-2xl font-bold text-green-400">{formatUSDC(totalEarned)}</p>
        </div>
      </div>

      <Card>
        {jobs.length === 0 ? (
          <p className="text-slate-500 text-center py-10">No jobs yet — agents create jobs when market creators post requests.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="pb-3 pr-4">Market ID</th>
                  <th className="pb-3 pr-4">Budget</th>
                  <th className="pb-3 pr-4">Earned</th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3 pr-4">Created</th>
                  <th className="pb-3">Arc TX</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-800/50 transition-colors">
                    <td className="py-3 pr-4 font-mono text-xs text-slate-300">{job.market_id?.slice(0, 12)}...</td>
                    <td className="py-3 pr-4 text-white">{formatUSDC(job.budget_usdc)}</td>
                    <td className="py-3 pr-4 text-green-400">{formatUSDC(job.usdc_earned || 0)}</td>
                    <td className="py-3 pr-4">
                      <Badge variant={statusVariant(job.status)}>{job.status}</Badge>
                    </td>
                    <td className="py-3 pr-4 text-slate-400">{formatTimestamp(job.created_at)}</td>
                    <td className="py-3">
                      <ArcTxLink txHash={job.arc_create_tx || ""} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
