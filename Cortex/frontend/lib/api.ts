/**
 * All requests go through the Next.js middleware proxy as same-origin
 * relative paths. This eliminates CORS issues with Set-Cookie headers —
 * cookies are set on the frontend domain, no cross-origin complications.
 */
function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|; )cortex_csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const method = (init?.method ?? "GET").toUpperCase();
  if (!headers.has("Content-Type") && !["GET", "HEAD"].includes(method)) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = getCsrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const res = await fetch(path, {
    ...init,
    credentials: "include",
    headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `API error: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────

export interface Event {
  id: string;
  polymarket_market_id: string;
  title: string;
  description: string | null;
  category: string;
  category_normalized: string;
  outcomes: string[];
  outcome_prices: Record<string, number>;
  active: boolean;
  closed: boolean;
  end_date: string | null;
  resolved_outcome: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface AvailableModel {
  id: string;
  name: string;
  tier: string;
  provider: string;
}

export interface PredictionJournalEntry {
  id: string;
  model_name: string;
  probability: number;
  predicted_outcome: string | null;
  result_status: "pending" | "won" | "lost";
  verdict: string;
  reasoning: string;
  sources: Array<{ url: string; title?: string }>;
  brier_score: number | null;
  created_at: string;
}

export interface ModelLeaderboardEntry {
  model_name: string;
  total_predictions: number;
  resolved_predictions: number;
  won_predictions: number;
  lost_predictions: number;
  win_rate: number | null;
  mean_brier_score: number | null;
  accuracy: number | null;
}

export interface LeaderboardResponse {
  models: ModelLeaderboardEntry[];
}

export interface User {
  id: string;
  email: string;
  plan: string;
  is_active: boolean;
  is_admin: boolean;
  whitelisted: boolean;
  created_at: string;
}

export interface AuthResponse {
  user: User | null;
  message: string;
}

// ── Events ─────────────────────────────────────────────────────────

export async function fetchEvents(
  page = 1,
  pageSize = 10,
  category?: string,
  search?: string
): Promise<PaginatedResponse<Event>> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    ...(category ? { category } : {}),
    ...(search ? { search } : {}),
  });
  return apiFetch<PaginatedResponse<Event>>(`/api/events?${params}`);
}

export async function fetchAllEvents(
  category?: string,
  search?: string
): Promise<Event[]> {
  const pageSize = 100;
  let page = 1;
  let hasNext = true;
  const items: Event[] = [];

  while (hasNext) {
    const response = await fetchEvents(page, pageSize, category, search);
    items.push(...response.items);
    hasNext = response.has_next;
    page += 1;
  }

  return items;
}

export async function fetchCategories(): Promise<string[]> {
  return apiFetch<{ categories: string[] }>("/api/events/categories").then(
    (r) => r.categories
  );
}

export async function fetchEvent(id: string): Promise<Event> {
  return apiFetch<Event>(`/api/events/${id}`);
}

// ── Forecast ───────────────────────────────────────────────────────

export async function fetchModels(): Promise<AvailableModel[]> {
  return apiFetch<{ models: AvailableModel[] }>("/api/forecast/models").then(
    (r) => r.models
  );
}

export async function fetchPredictions(
  eventId: string
): Promise<PredictionJournalEntry[]> {
  return apiFetch<{ predictions: PredictionJournalEntry[] }>(
    `/api/forecast/${eventId}/predictions`
  ).then((r) => r.predictions);
}

export async function checkEventOutcome(
  eventId: string
): Promise<OutcomeCheckResponse> {
  return apiFetch<OutcomeCheckResponse>(`/api/forecast/${eventId}/check-outcome`, {
    method: "POST",
  });
}

export interface ForecastResult {
  model_name: string;
  probability: number;
  predicted_outcome: string | null;
  result_status: "pending" | "won" | "lost";
  verdict: string;
  reasoning: string;
  sources: Array<{ url: string; title?: string }>;
  confidence_score: number | null;
  brier_score: number | null;
  created_at: string;
}

export interface OutcomeCheckResponse {
  event_id: string;
  resolved: boolean;
  resolved_outcome: string | null;
  message: string;
  updated_predictions: number;
}

export async function generateForecast(
  eventId: string,
  model: string,
  autoFallback = false
): Promise<ForecastResult> {
  return apiFetch<ForecastResult>("/api/forecast", {
    method: "POST",
    body: JSON.stringify({ event_id: eventId, model, auto_fallback: autoFallback }),
  });
}

// ── Leaderboard ────────────────────────────────────────────────────

export async function fetchLeaderboard(): Promise<LeaderboardResponse> {
  return apiFetch<LeaderboardResponse>("/api/forecast/leaderboard");
}

// ── Auth ───────────────────────────────────────────────────────────

export async function register(
  email: string,
  password: string
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(
  email: string,
  password: string
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function logout(): Promise<void> {
  await apiFetch<void>("/api/auth/logout", { method: "POST" });
}

export async function fetchMe(): Promise<User | null> {
  try {
    return await apiFetch<User>("/api/auth/me");
  } catch {
    return null;
  }
}

// ── Admin ──────────────────────────────────────────────────────────

export interface AdminModel {
  id: string;
  name: string;
  tier: string;
  provider: string;
}

export async function fetchAdminUsers(): Promise<User[]> {
  return apiFetch<User[]>("/api/admin/users");
}

export async function fetchPendingUsers(): Promise<User[]> {
  return apiFetch<User[]>("/api/admin/users/pending");
}

export async function whitelistUser(userId: string): Promise<User> {
  return apiFetch<User>(`/api/admin/users/${userId}/whitelist`, { method: "POST" });
}

export async function rejectUser(userId: string): Promise<User> {
  return apiFetch<User>(`/api/admin/users/${userId}/reject`, { method: "POST" });
}

export async function promoteUser(userId: string): Promise<User> {
  return apiFetch<User>(`/api/admin/promote/${userId}`, { method: "POST" });
}

export async function fetchAdminModels(): Promise<AdminModel[]> {
  return apiFetch<{ models: AdminModel[] }>("/api/admin/models").then((r) => r.models);
}

export async function updateAdminModels(models: string[]): Promise<AdminModel[]> {
  return apiFetch<{ models: AdminModel[] }>("/api/admin/models", {
    method: "POST",
    body: JSON.stringify({ models }),
  }).then((r) => r.models);
}

// ── Admin: Events ──────────────────────────────────────────────────

export interface PolymarketSearchResult {
  id: string;
  question: string;
  description: string;
  active: boolean;
  closed: boolean;
  end_date: string | null;
}

export interface PolymarketSearchResponse {
  items: PolymarketSearchResult[];
  total: number;
}

export async function searchPolymarket(
  q: string,
  limit = 20,
  offset = 0,
  sort: "none" | "soonest" | "latest" = "none",
  deadlineFilter: "all" | "with_deadline" | "without_deadline" = "all"
): Promise<PolymarketSearchResponse> {
  const params = new URLSearchParams({
    ...(q ? { q } : {}),
    limit: String(limit),
    offset: String(offset),
    ...(sort !== "none" ? { sort } : {}),
    ...(deadlineFilter !== "all" ? { deadline_filter: deadlineFilter } : {}),
  });
  return apiFetch<PolymarketSearchResponse>(`/api/admin/polymarket/search?${params}`);
}

export async function addEventToDb(marketId: string): Promise<Event> {
  return apiFetch<Event>(`/api/admin/events/add/${marketId}`, { method: "POST" });
}

export async function truncateEvents(): Promise<{ status: string; message: string }> {
  return apiFetch("/api/admin/events/truncate", { method: "POST" });
}

export async function resyncEvent(eventId: string): Promise<Event> {
  return apiFetch<Event>(`/api/admin/events/resync/${eventId}`, { method: "POST" });
}

export interface DbSizeInfo {
  total_size: string;
  total_bytes: number;
  tables: Array<{ table: string; size: string; size_bytes: number }>;
  events: Array<{
    id: string;
    polymarket_market_id: string;
    title: string;
    category_normalized: string;
    active: boolean;
    closed: boolean;
    end_date: string | null;
    size: string;
    size_bytes: number;
  }>;
}

export async function fetchDbSize(): Promise<DbSizeInfo> {
  return apiFetch<DbSizeInfo>("/api/admin/db-size");
}

export async function deleteEvent(eventId: string): Promise<{ status: string; message: string }> {
  return apiFetch(`/api/admin/events/${eventId}`, { method: "DELETE" });
}

// ── User API Keys ──────────────────────────────────────────────────

export interface UserApiKey {
  id: string;
  provider: string;
  is_active: boolean;
  created_at: string;
}

export async function fetchUserApiKeys(): Promise<UserApiKey[]> {
  return apiFetch<UserApiKey[]>("/api/user/api-keys");
}

export async function createUserApiKey(
  provider: string,
  api_key: string
): Promise<UserApiKey> {
  return apiFetch<UserApiKey>("/api/user/api-keys", {
    method: "POST",
    body: JSON.stringify({ provider, api_key }),
  });
}

export async function deleteUserApiKey(keyId: string): Promise<UserApiKey> {
  return apiFetch<UserApiKey>(`/api/user/api-keys/${keyId}`, { method: "DELETE" });
}
