"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchMarkets } from "@/lib/api";
import type { Market } from "@/types";

export function useMarkets(resolved?: boolean, limit = 100) {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchMarkets(resolved, limit);
      setMarkets(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load markets");
    } finally {
      setLoading(false);
    }
  }, [resolved, limit]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, [load]);

  return { markets, loading, error, refetch: load };
}
