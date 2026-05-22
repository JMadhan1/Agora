"use client";

import { Spinner } from "@/components/ui/Spinner";
import { useCalibration } from "@/hooks/useCalibration";
import { formatPercent, formatCalibrationGrade } from "@/lib/format";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const GRADE_COLORS: Record<string, string> = {
  A: "#00ff88",
  B: "#06b6d4",
  C: "#ffcc00",
  D: "#ff3366",
};

export function CalibrationChart() {
  const { stats, loading } = useCalibration();

  if (loading) {
    return (
      <div className="sentinel-card p-5 flex justify-center items-center h-48">
        <Spinner />
      </div>
    );
  }

  const grade = stats?.calibration_grade ?? "—";
  const gradeColor = GRADE_COLORS[grade] ?? "#94a3b8";

  const chartData = stats ? [
    { name: "7d",  value: Math.round(stats.accuracy_7d * 100) },
    { name: "All", value: Math.round(stats.accuracy_overall * 100) },
    { name: "Tgt", value: 70 },
  ] : [];

  return (
    <div className="sentinel-card p-5">
      <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-secondary)" }}>
        Calibration Score
      </h2>

      {stats ? (
        <div className="space-y-4">
          <div className="text-center py-2">
            <p className="text-7xl font-black" style={{ color: gradeColor }}>{grade}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
              {formatCalibrationGrade(stats.calibration_grade)?.label ?? "Calibration grade"}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "Overall", value: formatPercent(stats.accuracy_overall), color: "var(--sentinel-cyan)" },
              { label: "Last 7d", value: formatPercent(stats.accuracy_7d), color: gradeColor },
              { label: "Markets", value: stats.total_markets.toString(), color: "var(--text-primary)" },
              { label: "Brier", value: stats.avg_brier_score.toFixed(3), color: "#a855f7" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl p-2.5 text-center"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</p>
                <p className="text-sm font-bold mt-0.5" style={{ color }}>{value}</p>
              </div>
            ))}
          </div>

          {chartData.length > 0 && (
            <ResponsiveContainer width="100%" height={100}>
              <BarChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                <XAxis dataKey="name" tick={{ fill: "#475569", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "rgba(3,7,18,0.95)",
                    border: "1px solid rgba(6,182,212,0.2)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(v: number) => [`${v}%`, ""]}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={i === 0 ? "#06b6d4" : i === 1 ? "#a855f7" : "#1e293b"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      ) : (
        <div className="text-center py-8">
          <p className="text-4xl mb-2">📊</p>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            No calibration data yet.
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
            Needs resolved markets to compute score.
          </p>
        </div>
      )}
    </div>
  );
}
