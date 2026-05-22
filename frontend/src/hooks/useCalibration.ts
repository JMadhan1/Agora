"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchCalibrationStats } from "@/lib/api";
import type { CalibrationStats } from "@/types";

export function useCalibration() {
  const [stats, setStats] = useState<CalibrationStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchCalibrationStats();
      setStats(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load calibration");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, [load]);

  return { stats, loading, error, refetch: load };
}
