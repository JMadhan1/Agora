import { formatDistanceToNow, parseISO } from "date-fns";

export function formatPercent(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

export function formatUSDC(n: number): string {
  return `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatAddress(addr: string): string {
  if (!addr || addr.length < 10) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

export function formatTimestamp(ts: string): string {
  if (!ts) return "—";
  try {
    const date = typeof ts === "string" ? parseISO(ts) : new Date(ts);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return ts;
  }
}

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 80) return "text-green-400";
  if (confidence >= 60) return "text-yellow-400";
  return "text-red-400";
}

export function getRecommendationColor(rec: string): string {
  switch (rec?.toUpperCase()) {
    case "YES": return "text-green-400";
    case "NO": return "text-red-400";
    default: return "text-yellow-400";
  }
}

export function formatBrier(n: number): string {
  if (n < 0.1) return `${n.toFixed(3)} (Excellent)`;
  if (n < 0.2) return `${n.toFixed(3)} (Good)`;
  if (n < 0.3) return `${n.toFixed(3)} (Fair)`;
  return `${n.toFixed(3)} (Poor)`;
}

export function formatCalibrationGrade(grade: string): { label: string; color: string } {
  const map: Record<string, { label: string; color: string }> = {
    A: { label: "A — Excellent", color: "text-green-400" },
    B: { label: "B — Good", color: "text-cyan-400" },
    C: { label: "C — Fair", color: "text-yellow-400" },
    D: { label: "D — Poor", color: "text-orange-400" },
  };
  return map[grade] || { label: grade, color: "text-slate-400" };
}
