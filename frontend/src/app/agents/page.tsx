"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchAgents } from "@/lib/api";
import { AgentCard } from "@/components/agents/AgentCard";
import { Spinner } from "@/components/ui/Spinner";
import type { AgentProfile } from "@/types";

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAgents().then(setAgents).catch(console.error).finally(() => setLoading(false));
    const iv = setInterval(() => fetchAgents().then(setAgents).catch(console.error), 30_000);
    return () => clearInterval(iv);
  }, []);

  if (loading) return <div className="flex justify-center mt-20"><Spinner size="lg" /></div>;

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-black mb-1" style={{
            background: "linear-gradient(90deg, #a855f7, #06b6d4)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>
            Agent Network
          </h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            ERC-8004 identities on Arc Testnet · {agents.length} registered
          </p>
        </div>
        <Link href="/circle"
          className="px-4 py-2 rounded-xl text-xs font-semibold"
          style={{
            background: "rgba(168,85,247,0.1)",
            color: "#a855f7",
            border: "1px solid rgba(168,85,247,0.25)",
          }}>
          💎 Circle Tools →
        </Link>
      </div>

      {agents.length === 0 ? (
        <div className="sentinel-card p-12 text-center">
          <p className="text-4xl mb-4">🤖</p>
          <p className="text-lg font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
            No agents registered yet.
          </p>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Run <code className="font-mono px-2 py-1 rounded"
              style={{ background: "rgba(6,182,212,0.1)", color: "#06b6d4" }}>
              python agents/main.py
            </code>{" "}
            to start the agent network.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <AgentCard key={agent.wallet} agent={agent} />
          ))}
        </div>
      )}
    </div>
  );
}
