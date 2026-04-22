"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  fetchUserApiKeys,
  createUserApiKey,
  deleteUserApiKey,
  type UserApiKey,
} from "@/lib/api";

const PROVIDERS = [
  { value: "openrouter", label: "OpenRouter", help: "https://openrouter.ai/keys" },
  { value: "google", label: "Google AI Studio", help: "https://aistudio.google.com/app/apikey" },
  { value: "groq", label: "Groq", help: "https://console.groq.com/keys" },
  { value: "deepseek", label: "DeepSeek", help: "https://platform.deepseek.com/" },
  { value: "mistral", label: "Mistral", help: "https://console.mistral.ai/" },
  { value: "cerebras", label: "Cerebras", help: "https://cloud.cerebras.ai/" },
  { value: "fireworks", label: "Fireworks", help: "https://fireworks.ai/" },
  { value: "nvidia", label: "NVIDIA", help: "https://build.nvidia.com/" },
  { value: "tavily", label: "Tavily", help: "https://tavily.com/" },
];

function ProviderStatus({ keys, onDelete }: { keys: UserApiKey[]; onDelete: (id: string) => void }) {
  const keySet = new Set(keys.map((k) => k.provider));
  const llmProviders = PROVIDERS.filter((p) => p.value !== "tavily");
  const hasAnyLlm = llmProviders.some((p) => keySet.has(p.value));

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">Connected Providers</h3>
      <div className="grid grid-cols-2 gap-2">
        {PROVIDERS.map((p) => {
          const connected = keySet.has(p.value);
          const key = keys.find((k) => k.provider === p.value);
          return (
            <div
              key={p.value}
              className={`flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm ${
                connected
                  ? "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-400"
                  : "bg-muted/50 text-muted-foreground"
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className={`h-2 w-2 rounded-full flex-shrink-0 ${connected ? "bg-green-500" : "bg-muted-foreground/40"}`} />
                <span className="truncate">{p.label}</span>
              </div>
              {connected && key && (
                <button
                  onClick={() => onDelete(key.id)}
                  className="text-xs text-red-500 hover:text-red-700 flex-shrink-0"
                >
                  ✕
                </button>
              )}
            </div>
          );
        })}
      </div>
      {!hasAnyLlm && keys.length > 0 && (
        <p className="text-xs text-amber-600 mt-2">
          Tavily is connected but no LLM provider. Add at least one LLM to generate forecasts.
        </p>
      )}
      {keys.length === 0 && (
        <p className="text-xs text-muted-foreground mt-2">
          No providers connected. Add at least Tavily + one LLM provider to generate forecasts.
        </p>
      )}
    </div>
  );
}

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const queryClient = useQueryClient();
  const [selectedProvider, setSelectedProvider] = useState("openrouter");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [saveMsg, setSaveMsg] = useState("");

  const { data: keys, isLoading: keysLoading } = useQuery<UserApiKey[]>({
    queryKey: ["user-api-keys"],
    queryFn: fetchUserApiKeys,
  });

  const saveMutation = useMutation({
    mutationFn: () => createUserApiKey(selectedProvider, apiKeyInput),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-api-keys"] });
      setApiKeyInput("");
      setSaveMsg("Key saved!");
      setTimeout(() => setSaveMsg(""), 3000);
    },
    onError: (err: Error) => {
      setSaveMsg(err.message);
      setTimeout(() => setSaveMsg(""), 5000);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (keyId: string) => deleteUserApiKey(keyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-api-keys"] });
    },
  });

  if (!user) return null;

  return (
    <ProtectedRoute>
      <div className="container mx-auto px-4 py-8 max-w-5xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
          {/* Account Info */}
          <Card>
            <CardHeader>
              <CardTitle>Profile</CardTitle>
              <CardDescription>Your account information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm text-muted-foreground">Email</p>
                <p className="font-medium">{user.email}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Plan</p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant={user.plan === "premium" ? "default" : "secondary"}>
                    {user.plan}
                  </Badge>
                </div>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Status</p>
                <Badge variant={user.is_active ? "success" : "outline"}>
                  {user.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
              <Button variant="outline" className="w-full mt-4" onClick={() => logout()}>
                Logout
              </Button>
            </CardContent>
          </Card>

          {/* API Keys */}
          <Card>
            <CardHeader>
              <CardTitle>API Keys</CardTitle>
              <CardDescription>
                Connect your own API keys for LLM providers. Your keys are used first.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Provider Status Grid */}
              {!keysLoading && keys && (
                <ProviderStatus keys={keys} onDelete={deleteMutation.mutate} />
              )}

              {/* Add new key */}
              <div className="border-t pt-4">
                <p className="text-sm font-medium mb-2">Add API Key</p>
                <div className="flex flex-wrap gap-2 mb-2">
                  {PROVIDERS.map((p) => (
                    <Button
                      key={p.value}
                      variant={selectedProvider === p.value ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSelectedProvider(p.value)}
                    >
                      {p.label}
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mb-2">
                  Get your key at{" "}
                  <a
                    href={PROVIDERS.find((p) => p.value === selectedProvider)?.help}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline"
                  >
                    {PROVIDERS.find((p) => p.value === selectedProvider)?.help}
                  </a>
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder="sk-..."
                    className="flex-1 px-3 py-2 border rounded-md text-sm bg-background"
                  />
                  <Button
                    onClick={() => saveMutation.mutate()}
                    disabled={!apiKeyInput.trim() || saveMutation.isPending}
                  >
                    {saveMutation.isPending ? "Saving..." : "Save"}
                  </Button>
                </div>
                {saveMsg && (
                  <p
                    className={`text-sm mt-2 ${
                      saveMsg === "Key saved!" ? "text-green-600" : "text-destructive"
                    }`}
                  >
                    {saveMsg}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </ProtectedRoute>
  );
}
