import { ReputationBadge } from "./ReputationBadge";
import { arcScanAddressUrl } from "@/lib/arc";
import { formatAddress, formatUSDC } from "@/lib/format";
import type { AgentProfile } from "@/types";

const AGENT_META: Record<string, { icon: string; color: string; desc: string }> = {
  scout:    { icon: "🔭", color: "#06b6d4", desc: "5 parallel scouts — news, on-chain, social, Wayback, market data" },
  judge:    { icon: "⚖️", color: "#a855f7", desc: "LangGraph + Bayesian inference, commits attestations to Arc Testnet" },
  watchdog: { icon: "🐕", color: "#00ff88", desc: "Monitors deviation, auto-triggers UMA disputes on Polygon" },
};

interface Props { agent: AgentProfile; }

export function AgentCard({ agent }: Props) {
  const calibration = agent.jobsCompleted > 0
    ? Math.round((agent.correctCalls / agent.jobsCompleted) * 100)
    : (agent.calibration_rate ?? 0);

  const grade = calibration >= 75 ? "A" : calibration >= 65 ? "B" : calibration >= 55 ? "C" : "D";
  const meta = AGENT_META[agent.agentType] ?? { icon: "◎", color: "#06b6d4", desc: "" };

  return (
    <div className="sentinel-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
            style={{ background: `${meta.color}15`, border: `1px solid ${meta.color}30` }}>
            {meta.icon}
          </div>
          <div>
            <p className="font-bold capitalize" style={{ color: "var(--text-primary)" }}>
              {agent.agentType} Agent
            </p>
            <p className="text-xs" style={{ color: meta.color }}>ERC-8004 Identity</p>
          </div>
        </div>
        <ReputationBadge grade={grade} />
      </div>

      <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
        {meta.desc}
      </p>

      <div className="grid grid-cols-2 gap-2">
        {[
          { label: "Wallet", value: (
            <a href={arcScanAddressUrl(agent.wallet)} target="_blank" rel="noopener noreferrer"
              className="font-mono hover:opacity-80 transition-opacity"
              style={{ color: meta.color }}>
              {formatAddress(agent.wallet)} ↗
            </a>
          )},
          { label: "Bond", value: <span style={{ color: "var(--text-primary)" }}>{formatUSDC(Number(agent.bondAmount) / 1e6)}</span> },
          { label: "Jobs Done", value: <span className="font-bold" style={{ color: "var(--text-primary)" }}>{agent.jobsCompleted}</span> },
          { label: "Accuracy", value: <span className="font-bold" style={{ color: meta.color }}>{calibration}%</span> },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg p-2.5"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
            <p className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
            <div className="text-xs">{value}</div>
          </div>
        ))}
      </div>

      <div>
        <div className="flex justify-between text-xs mb-1.5">
          <span style={{ color: "var(--text-muted)" }}>Calibration Rate</span>
          <span style={{ color: meta.color }}>{calibration}%</span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
          <div className="h-full rounded-full progress-fill" style={{ width: `${calibration}%`, background: meta.color }} />
        </div>
      </div>

      {agent.erc8004MetadataUri && (
        <a href={agent.erc8004MetadataUri} target="_blank" rel="noopener noreferrer"
          className="text-xs block transition-opacity hover:opacity-70"
          style={{ color: "#a855f7" }}>
          ERC-8004 metadata ↗
        </a>
      )}
    </div>
  );
}
