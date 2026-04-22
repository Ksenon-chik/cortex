"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import {
  checkEventOutcome,
  fetchEvent,
  fetchPredictions,
  fetchModels,
  type AvailableModel,
  type ForecastResult,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { PredictionBadge } from "@/components/prediction-badge";
import { useAuth } from "@/lib/auth-context";

function ResultStatusBadge({ status }: { status: "pending" | "won" | "lost" }) {
  const label =
    status === "won" ? "Fulfilled" : status === "lost" ? "Missed" : "Pending";
  const variant =
    status === "won" ? "success" : status === "lost" ? "destructive" : "secondary";
  return <Badge variant={variant}>{label}</Badge>;
}

export default function EventDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuth();
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [forecasting, setForecasting] = useState(false);
  const [outcomeMessage, setOutcomeMessage] = useState("");
  const [autoFallback, setAutoFallback] = useState(false);
  const [logs, setLogs] = useState<Array<{ time: string; message: string; status: "running" | "done" | "error" }>>([]);

  const { data: event, isLoading: eventLoading } = useQuery({
    queryKey: ["event", id],
    queryFn: () => fetchEvent(id),
  });

  const { data: predictions } = useQuery({
    queryKey: ["predictions", id],
    queryFn: () => fetchPredictions(id),
  });

  const { data: models } = useQuery<AvailableModel[]>({
    queryKey: ["models"],
    queryFn: () => fetchModels(),
  });

  const forecastMutation = useMutation({
    mutationFn: async () => {
      const t = () => new Date().toLocaleTimeString();
      setLogs([]);

      const getCsrfToken = () => {
        const match = document.cookie.match(/(?:^|; )cortex_csrf_token=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
      };

      return new Promise<ForecastResult>((resolve, reject) => {
        void (async () => {
          const response = await fetch("/api/forecast/stream", {
            method: "POST",
            credentials: "include",
            headers: {
              "Content-Type": "application/json",
              "X-CSRF-Token": getCsrfToken(),
            },
            body: JSON.stringify({
              event_id: id,
              model: selectedModel,
              auto_fallback: autoFallback,
            }),
          });

          if (!response.ok || !response.body) {
            const body = await response.json().catch(() => ({}));
            reject(new Error(body.detail ?? "Unable to start forecast stream"));
            return;
          }

          const decoder = new TextDecoder();
          const reader = response.body.getReader();
          let buffer = "";

          const handleEvent = (type: string, rawData: string) => {
            const data = JSON.parse(rawData);
            if (type === "result") {
              resolve(data);
              return;
            }
            if (type === "error") {
              reject(new Error(data));
              return;
            }
            if (type === "end") {
              return;
            }

            const status =
              type === "research_done" || type === "model_success"
                ? "done"
                : type === "model_ratelimited"
                  ? "error"
                  : "running";

            setLogs((prev) => [...prev, { time: t(), message: data, status }]);
          };

          try {
            while (true) {
              const { value, done } = await reader.read();
              if (done) break;
              buffer += decoder.decode(value, { stream: true });

              const chunks = buffer.split("\n\n");
              buffer = chunks.pop() ?? "";

              for (const chunk of chunks) {
                const lines = chunk.split("\n");
                const eventLine = lines.find((line) => line.startsWith("event: "));
                const dataLine = lines.find((line) => line.startsWith("data: "));
                if (!eventLine || !dataLine) continue;
                handleEvent(
                  eventLine.slice("event: ".length),
                  dataLine.slice("data: ".length)
                );
              }
            }
          } catch {
            reject(new Error("Connection lost"));
          }
        })().catch((err: Error) => reject(err));
      });
    },
    onMutate: () => {
      setForecasting(true);
      setLogs([]);
    },
    onSettled: () => {
      setForecasting(false);
      queryClient.invalidateQueries({ queryKey: ["predictions", id] });
    },
    onError: (err) => {
      const t = () => new Date().toLocaleTimeString();
      setLogs((prev) => [
        ...prev,
        { time: t(), message: err.message, status: "error" },
      ]);
    },
  });

  const outcomeMutation = useMutation({
    mutationFn: () => checkEventOutcome(id),
    onSuccess: (result) => {
      setOutcomeMessage(result.message);
      queryClient.invalidateQueries({ queryKey: ["event", id] });
      queryClient.invalidateQueries({ queryKey: ["predictions", id] });
      queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
    },
    onError: (err: Error) => {
      setOutcomeMessage(err.message);
    },
  });

  if (eventLoading) {
    return <p className="text-center text-muted-foreground py-12">Loading event...</p>;
  }

  if (!event) {
    return <p className="text-center text-muted-foreground py-12">Event not found.</p>;
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Event Info */}
      <Card className="mb-8">
        <CardHeader>
          <div className="flex items-center gap-3">
            <Badge variant={event.active ? "success" : "outline"}>
              {event.active ? "Active" : "Closed"}
            </Badge>
            <Badge variant="secondary">{event.category}</Badge>
          </div>
          <CardTitle className="mt-2">{event.title}</CardTitle>
        </CardHeader>
        <CardContent>
          {event.description && (
            <p className="text-muted-foreground mb-4">{event.description}</p>
          )}
          <div className="flex flex-wrap gap-2">
            {event.outcomes.map((outcome: string) => (
              <Badge key={outcome} variant="outline">
                {outcome}
                {event.outcome_prices[outcome] != null &&
                  ` — $${(event.outcome_prices[outcome] * 100).toFixed(0)}¢`}
              </Badge>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Badge variant={event.resolved_outcome ? "success" : "secondary"}>
              {event.resolved_outcome
                ? `Resolved: ${event.resolved_outcome}`
                : "Outcome pending"}
            </Badge>
            {event.end_date && (
              <Badge variant="outline">
                Deadline: {new Date(event.end_date).toLocaleString()}
              </Badge>
            )}
          </div>
          {isAuthenticated && (
            <div className="mt-4 flex flex-col items-start gap-2">
              <Button
                variant="outline"
                onClick={() => outcomeMutation.mutate()}
                disabled={outcomeMutation.isPending}
              >
                {outcomeMutation.isPending ? "Checking outcome..." : "Check Outcome"}
              </Button>
              {outcomeMessage && (
                <p className="text-sm text-muted-foreground">{outcomeMessage}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Forecast Generation + Live Log */}
      {isAuthenticated && event.active && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          {/* Left: Generate controls */}
          <Card>
            <CardHeader>
              <CardTitle>Generate Forecast</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-3">
                <div>
                  <label className="text-sm text-muted-foreground mb-1 block">Provider</label>
                  <Select
                    value={selectedProvider}
                    onChange={(e) => {
                      setSelectedProvider(e.target.value);
                      setSelectedModel("");
                    }}
                  >
                    <option value="">All providers</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="google">Google AI</option>
                    <option value="groq">Groq</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="mistral">Mistral</option>
                    <option value="cerebras">Cerebras</option>
                    <option value="fireworks">Fireworks</option>
                    <option value="nvidia">NVIDIA</option>
                  </Select>
                </div>
                <div>
                  <label className="text-sm text-muted-foreground mb-1 block">Model</label>
                  <Select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                  >
                    <option value="">Select a model...</option>
                    {models
                      ?.filter((m) => !selectedProvider || m.provider === selectedProvider)
                      .map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({m.tier})
                        </option>
                      ))}
                  </Select>
                </div>
                <Button
                  disabled={!selectedModel || forecasting}
                  onClick={() => forecastMutation.mutate()}
                  className="w-full"
                >
                  {forecasting ? "Working…" : "Generate"}
                </Button>
              </div>
              <label className="flex items-center gap-2 mt-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoFallback}
                  onChange={(e) => setAutoFallback(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm text-muted-foreground">
                  Auto-fallback — try all free models if selected model is unavailable
                </span>
              </label>
              {forecastMutation.error && (
                <p className="text-sm text-destructive mt-2">
                  {forecastMutation.error.message}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Right: Live log */}
          <Card>
            <CardHeader>
              <CardTitle>Processing Log</CardTitle>
            </CardHeader>
            <CardContent>
              {logs.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Waiting for forecast…
                </p>
              ) : (
                <div className="max-h-64 overflow-y-auto space-y-2 font-mono text-sm pr-1">
                  {logs.map((entry, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="text-muted-foreground shrink-0">
                        {entry.time}
                      </span>
                      {entry.status === "running" && (
                        <span className="text-yellow-500 shrink-0">⏳</span>
                      )}
                      {entry.status === "done" && (
                        <span className="text-green-500 shrink-0">✓</span>
                      )}
                      {entry.status === "error" && (
                        <span className="text-red-500 shrink-0">✗</span>
                      )}
                      <span
                        className={
                          entry.status === "error"
                            ? "text-destructive"
                            : entry.status === "done"
                              ? "text-green-600"
                              : ""
                        }
                      >
                        {entry.message}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Predictions Journal */}
      <Card>
        <CardHeader>
          <CardTitle>Predictions Journal</CardTitle>
        </CardHeader>
        <CardContent>
          {!predictions || predictions.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No predictions yet. {isAuthenticated ? "Generate a forecast above." : "Register to generate forecasts."}
            </p>
          ) : (
            <div className="space-y-4">
              {predictions.map((pred) => (
                <div key={pred.id} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{pred.model_name.split("/").pop()}</span>
                      <PredictionBadge verdict={pred.verdict} />
                      <ResultStatusBadge status={pred.result_status} />
                      {pred.predicted_outcome && (
                        <Badge variant="outline">Pick: {pred.predicted_outcome}</Badge>
                      )}
                      <span className="text-sm text-muted-foreground">
                        {new Date(pred.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <span className="text-lg font-semibold">
                      {(pred.probability * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">{pred.reasoning}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    {pred.brier_score != null && (
                      <span>Brier: {pred.brier_score.toFixed(4)}</span>
                    )}
                    <span>Status: {pred.result_status}</span>
                  </div>
                  {pred.sources.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {pred.sources.slice(0, 3).map((s, i) => (
                        <a
                          key={i}
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-500 hover:underline truncate max-w-xs"
                        >
                          {s.title || s.url}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
