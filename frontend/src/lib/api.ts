import type { Market, Attestation, CalibrationStats, AgentProfile, DisputeAlert, SystemStats, AgentJob } from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    });
  }
  const resp = await fetch(url.toString(), { cache: "no-store" });
  if (!resp.ok) {
    throw new ApiError(resp.status, `API error ${resp.status}: ${path}`);
  }
  return resp.json();
}

export async function fetchMarkets(resolved?: boolean, limit = 100): Promise<Market[]> {
  const params: Record<string, string | number | boolean> = { limit };
  if (resolved !== undefined) params.resolved = resolved;
  return apiFetch<Market[]>("/api/markets", params);
}

export async function fetchMarket(id: string): Promise<Market> {
  return apiFetch<Market>(`/api/markets/${id}`);
}

export async function fetchAttestations(marketId?: string, limit = 50): Promise<Attestation[]> {
  const params: Record<string, string | number> = { limit };
  if (marketId) params.market_id = marketId;
  return apiFetch<Attestation[]>("/api/attestations", params);
}

export async function fetchCalibrationStats(): Promise<CalibrationStats> {
  return apiFetch<CalibrationStats>("/api/calibration/stats");
}

export async function fetchAgents(): Promise<AgentProfile[]> {
  return apiFetch<AgentProfile[]>("/api/agents");
}

export async function fetchDisputeAlerts(limit = 50): Promise<DisputeAlert[]> {
  return apiFetch<DisputeAlert[]>("/api/watchdog/alerts", { limit });
}

export async function fetchSystemStats(): Promise<SystemStats> {
  try {
    const [attStats, calStats, alertStats, jobStats] = await Promise.all([
      apiFetch<{ total: number }>("/api/attestations/stats"),
      apiFetch<CalibrationStats>("/api/calibration/stats"),
      apiFetch<{ total_alerts: number; triggered: number; won: number; total_reward_usdc: number }>("/api/watchdog/stats"),
      apiFetch<{ total_jobs: number; total_usdc_earned: number }>("/api/jobs/stats"),
    ]);
    return {
      total_attestations: attStats.total || 0,
      total_markets_monitored: calStats.total_markets || 0,
      total_disputes_triggered: alertStats.triggered || 0,
      total_disputes_won: alertStats.won || 0,
      calibration_accuracy: calStats.accuracy_overall || 0,
      usdc_earned: jobStats.total_usdc_earned || 0,
      usyc_deployed: 0,
    };
  } catch {
    return { total_attestations: 0, total_markets_monitored: 0, total_disputes_triggered: 0, total_disputes_won: 0, calibration_accuracy: 0, usdc_earned: 0, usyc_deployed: 0 };
  }
}

export async function fetchJobs(status?: string, limit = 50): Promise<AgentJob[]> {
  const params: Record<string, string | number> = { limit };
  if (status) params.status = status;
  return apiFetch<AgentJob[]>("/api/jobs", params);
}
