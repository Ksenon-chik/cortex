"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchLeaderboard } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LeaderboardChart } from "@/components/leaderboard-chart";

export default function LeaderboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["leaderboard"],
    queryFn: () => fetchLeaderboard(),
  });

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <h1 className="text-2xl font-bold mb-6">Model Leaderboard</h1>

      {isLoading ? (
        <p className="text-center text-muted-foreground py-12">Loading leaderboard...</p>
      ) : !data || data.models.length === 0 ? (
        <p className="text-center text-muted-foreground py-12">
          No models ranked yet. Predictions will appear here once events are resolved.
        </p>
      ) : (
        <>
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Brier Score Comparison</CardTitle>
            </CardHeader>
            <CardContent>
              <LeaderboardChart models={data.models} />
            </CardContent>
          </Card>

          <div className="rounded-md border">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="h-12 px-4 text-left font-medium">#</th>
                  <th className="h-12 px-4 text-left font-medium">Model</th>
                  <th className="h-12 px-4 text-right font-medium">Predictions</th>
                  <th className="h-12 px-4 text-right font-medium">Resolved</th>
                  <th className="h-12 px-4 text-right font-medium">Won</th>
                  <th className="h-12 px-4 text-right font-medium">Lost</th>
                  <th className="h-12 px-4 text-right font-medium">Win Rate</th>
                  <th className="h-12 px-4 text-right font-medium">Brier Score</th>
                  <th className="h-12 px-4 text-right font-medium">Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {data.models
                  .sort(
                    (a, b) =>
                      (a.mean_brier_score ?? Infinity) - (b.mean_brier_score ?? Infinity)
                  )
                  .map((entry, i) => (
                    <tr key={entry.model_name} className="border-b hover:bg-muted/30">
                      <td className="px-4 py-3 font-medium">{i + 1}</td>
                      <td className="px-4 py-3 font-medium">
                        {entry.model_name.split("/").pop()}
                      </td>
                      <td className="px-4 py-3 text-right">{entry.total_predictions}</td>
                      <td className="px-4 py-3 text-right">{entry.resolved_predictions}</td>
                      <td className="px-4 py-3 text-right">{entry.won_predictions}</td>
                      <td className="px-4 py-3 text-right">{entry.lost_predictions}</td>
                      <td className="px-4 py-3 text-right font-mono">
                        {entry.win_rate != null
                          ? `${(entry.win_rate * 100).toFixed(1)}%`
                          : "N/A"}
                      </td>
                      <td className="px-4 py-3 text-right font-mono">
                        {entry.mean_brier_score != null
                          ? entry.mean_brier_score.toFixed(4)
                          : "N/A"}
                      </td>
                      <td className="px-4 py-3 text-right font-mono">
                        {entry.accuracy != null
                          ? `${(entry.accuracy * 100).toFixed(1)}%`
                          : "N/A"}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
