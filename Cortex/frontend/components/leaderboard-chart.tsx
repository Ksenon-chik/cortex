"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { ModelLeaderboardEntry } from "@/lib/api";

export function LeaderboardChart({ models }: { models: ModelLeaderboardEntry[] }) {
  const data = models
    .filter((m) => m.mean_brier_score != null)
    .map((m) => ({
      name: m.model_name.split("/").pop() ?? m.model_name,
      score: Math.round((m.mean_brier_score ?? 0) * 1000) / 1000,
    }))
    .slice(0, 10);

  if (data.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No resolved predictions yet. Models will appear here once events are resolved.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
        <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
        <Tooltip
          formatter={(value) => [`${Number(value).toFixed(3)}`, "Brier Score"]}
          labelFormatter={(label) => `Model: ${label}`}
        />
        <Bar dataKey="score" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
