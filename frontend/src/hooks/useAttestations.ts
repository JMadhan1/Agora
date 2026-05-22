"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchAttestations } from "@/lib/api";
import type { Attestation } from "@/types";

export function useAttestations(marketId?: string, limit = 50) {
  const [attestations, setAttestations] = useState<Attestation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchAttestations(marketId, limit);
      setAttestations(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load attestations");
    } finally {
      setLoading(false);
    }
  }, [marketId, limit]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [load]);

  return { attestations, loading, error, refetch: load };
}
