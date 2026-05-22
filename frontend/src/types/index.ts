export interface Market {
  id: string;
  question: string;
  category: string;
  resolution_date: string;
  current_yes_price: number;
  yes_price: number;
  our_latest_estimate: number;
  our_confidence: number;
  last_scouted: string;
  resolved: boolean;
  actual_resolution: string | null;
  created_at: string;
}

export interface Attestation {
  id: number;
  market_id: string;
  trace_hash: string;
  ipfs_cid: string;
  arc_tx_hash: string;
  arc_scan_url: string;
  arc_block_number: number | null;
  confidence: number;
  recommendation: "YES" | "NO" | "UNCERTAIN";
  probability_estimate: number;
  timestamp: string;
}

export interface AgentProfile {
  wallet: string;
  wallet_address?: string;
  name?: string;
  agentType: string;
  erc8004MetadataUri: string;
  jobsCompleted: number;
  correctCalls: number;
  bondAmount: number;
  calibration_rate?: number;
  active: boolean;
  registeredAt: number;
}

export interface DisputeAlert {
  id: number;
  market_id: string;
  proposed_resolution: string;
  our_estimate: number;
  sentinel_estimate: number;
  deviation: number;
  reason?: string;
  manipulation_suspected: boolean;
  dispute_triggered: boolean;
  dispute_tx_hash: string | null;
  dispute_won: boolean | null;
  reward_usdc: number;
  timestamp: string;
  created_at: string;
}

export interface CalibrationStats {
  accuracy_overall: number;
  accuracy_7d: number;
  total_markets: number;
  correct_calls: number;
  avg_brier_score: number;
  calibration_grade: string;
}

export interface SystemStats {
  total_attestations: number;
  total_markets_monitored: number;
  total_disputes_triggered: number;
  total_disputes_won: number;
  calibration_accuracy: number;
  usdc_earned: number;
  usyc_deployed: number;
}

export interface AgentJob {
  id: string;
  market_id: string;
  budget_usdc: number;
  payment_usdc?: number;
  status: "open" | "completed" | "failed" | "CREATED" | "FUNDED" | "AGENT_ASSIGNED" | "DELIVERABLE_SUBMITTED" | "COMPLETED" | "FAILED";
  deliverable_hash?: string;
  deliverable_cid?: string;
  arc_create_tx?: string;
  arc_complete_tx?: string;
  usdc_earned: number;
  created_at: string;
  completed_at?: string;
}
