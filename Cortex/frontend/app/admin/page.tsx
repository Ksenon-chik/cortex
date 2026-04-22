"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog } from "@/components/ui/dialog";
import { Pagination } from "@/components/pagination";
import {
  fetchAdminUsers,
  fetchPendingUsers,
  whitelistUser,
  rejectUser,
  promoteUser,
  fetchAdminModels,
  updateAdminModels,
  searchPolymarket,
  addEventToDb,
  truncateEvents,
  fetchDbSize,
  deleteEvent,
  type User,
  type AdminModel,
  type PolymarketSearchResult,
  type DbSizeInfo,
} from "@/lib/api";

const DB_LIMIT_BYTES = 500 * 1024 * 1024; // 500 MB Railway limit
const EVENTS_PAGE_SIZE = 10;
const CALENDAR_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type CalendarSection = {
  monthKey: string;
  monthLabel: string;
  cells: Array<{
    key: string;
    dayNumber: number;
    isoDate: string;
    inMonth: boolean;
    events: PolymarketSearchResult[];
  }>;
};

function buildCalendarSections(markets: PolymarketSearchResult[]): { months: CalendarSection[]; withoutDeadline: PolymarketSearchResult[] } {
  const datedMarkets = markets.filter((market) => market.end_date);
  const withoutDeadline = markets.filter((market) => !market.end_date);
  const monthMap = new Map<string, PolymarketSearchResult[]>();

  for (const market of datedMarkets) {
    const date = new Date(market.end_date as string);
    const monthKey = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
    const bucket = monthMap.get(monthKey) ?? [];
    bucket.push(market);
    monthMap.set(monthKey, bucket);
  }

  const months = Array.from(monthMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([monthKey, monthMarkets]) => {
      const [year, month] = monthKey.split("-").map(Number);
      const monthStart = new Date(Date.UTC(year, month - 1, 1));
      const monthEnd = new Date(Date.UTC(year, month, 0));
      const firstWeekday = (monthStart.getUTCDay() + 6) % 7;
      const gridStart = new Date(monthStart);
      gridStart.setUTCDate(monthStart.getUTCDate() - firstWeekday);
      const lastWeekday = (monthEnd.getUTCDay() + 6) % 7;
      const trailingDays = 6 - lastWeekday;
      const gridEnd = new Date(monthEnd);
      gridEnd.setUTCDate(monthEnd.getUTCDate() + trailingDays);

      const eventsByDay = new Map<string, PolymarketSearchResult[]>();
      for (const market of monthMarkets) {
        const isoDate = (market.end_date as string).slice(0, 10);
        const bucket = eventsByDay.get(isoDate) ?? [];
        bucket.push(market);
        eventsByDay.set(isoDate, bucket);
      }

      const cells: CalendarSection["cells"] = [];
      const cursor = new Date(gridStart);
      while (cursor <= gridEnd) {
        const isoDate = cursor.toISOString().slice(0, 10);
        cells.push({
          key: `${monthKey}-${isoDate}`,
          dayNumber: cursor.getUTCDate(),
          isoDate,
          inMonth: cursor.getUTCMonth() === monthStart.getUTCMonth(),
          events: eventsByDay.get(isoDate) ?? [],
        });
        cursor.setUTCDate(cursor.getUTCDate() + 1);
      }

      return {
        monthKey,
        monthLabel: monthStart.toLocaleDateString(undefined, { month: "long", year: "numeric", timeZone: "UTC" }),
        cells,
      };
    });

  return { months, withoutDeadline };
}

function AdminContent() {
  const { user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (user && !user.is_admin) {
      router.push("/events");
    }
  }, [user, router]);

  const [activeTab, setActiveTab] = useState<"users" | "models" | "events" | "database">("users");
  const [users, setUsers] = useState<User[]>([]);
  const [pendingUsers, setPendingUsers] = useState<User[]>([]);
  const [models, setModels] = useState<AdminModel[]>([]);
  const [newModelId, setNewModelId] = useState("");
  const [newModelProvider, setNewModelProvider] = useState("openrouter");
  const [loading, setLoading] = useState(true);
  const [modelSearch, setModelSearch] = useState("");
  const [modelProviderFilter, setModelProviderFilter] = useState("");
  const [dialog, setDialog] = useState<{
    open: boolean;
    title: string;
    description: string;
    confirmLabel: string;
    confirmVariant: "default" | "destructive";
    onConfirm: () => void;
  }>({ open: false, title: "", description: "", confirmLabel: "Confirm", confirmVariant: "default", onConfirm: () => {} });

  // Events tab state
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [searchResults, setSearchResults] = useState<PolymarketSearchResult[]>([]);
  const [searchTotal, setSearchTotal] = useState(0);
  const [searchPage, setSearchPage] = useState(0);
  const [searchLoading, setSearchLoading] = useState(false);
  const [addingId, setAddingId] = useState<string | null>(null);
  const [eventSort, setEventSort] = useState<"none" | "soonest" | "latest">("none");
  const [deadlineFilter, setDeadlineFilter] = useState<"all" | "with_deadline" | "without_deadline">("all");
  const [eventView, setEventView] = useState<"list" | "calendar">("list");

  // Database tab state
  const [dbSize, setDbSize] = useState<DbSizeInfo | null>(null);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbEventPage, setDbEventPage] = useState(0);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [eventDeadlineSort, setEventDeadlineSort] = useState<"size" | "soonest" | "latest">("size");
  const [eventCategoryFilter, setEventCategoryFilter] = useState("");

  const loadData = async () => {
    setLoading(true);
    try {
      const [usersData, pendingData, modelsData] = await Promise.all([
        fetchAdminUsers(),
        fetchPendingUsers(),
        fetchAdminModels(),
      ]);
      setUsers(usersData);
      setPendingUsers(pendingData);
      setModels(modelsData);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Search Polymarket
  useEffect(() => {
    const doSearch = async () => {
      setSearchLoading(true);
      try {
        const res = await searchPolymarket(
          debouncedSearch,
          EVENTS_PAGE_SIZE,
          searchPage * EVENTS_PAGE_SIZE,
          eventSort,
          deadlineFilter,
        );
        setSearchResults(res.items);
        setSearchTotal(res.total);
      } catch {
        // fail silently
      } finally {
        setSearchLoading(false);
      }
    };
    if (activeTab === "events") {
      doSearch();
    }
  }, [debouncedSearch, searchPage, eventSort, deadlineFilter, activeTab]);

  // Load DB size
  useEffect(() => {
    const loadDbSize = async () => {
      setDbLoading(true);
      try {
        const size = await fetchDbSize();
        setDbSize(size);
      } catch {
        // fail silently
      } finally {
        setDbLoading(false);
      }
    };
    if (activeTab === "database") {
      loadDbSize();
    }
  }, [activeTab]);

  const handleWhitelist = async (userId: string) => {
    await whitelistUser(userId);
    await loadData();
  };

  const handleReject = (userId: string, email: string) => {
    setDialog({
      open: true,
      title: "Reject user",
      description: `Reject "${email}"? This will deactivate their account and remove them from the whitelist.`,
      confirmLabel: "Reject",
      confirmVariant: "destructive",
      onConfirm: async () => {
        setDialog((d) => ({ ...d, open: false }));
        await rejectUser(userId);
        await loadData();
      },
    });
  };

  const handlePromote = async (userId: string) => {
    await promoteUser(userId);
    await loadData();
  };

  const handleAddModel = async () => {
    if (!newModelId.trim()) return;
    const fullId = newModelId.trim().startsWith(`${newModelProvider}:`)
      ? newModelId.trim()
      : `${newModelProvider}:${newModelId.trim()}`;
    const updated = await updateAdminModels([...models.map((m) => m.id), fullId]);
    setModels(updated);
    setNewModelId("");
  };

  const handleRemoveModel = async (modelId: string) => {
    const updated = await updateAdminModels(models.filter((m) => m.id !== modelId).map((m) => m.id));
    setModels(updated);
  };

  const handleAddEvent = async (marketId: string) => {
    setAddingId(marketId);
    try {
      await addEventToDb(marketId);
      // Refresh DB tab if active
      if (activeTab === "database") {
        const size = await fetchDbSize();
        setDbSize(size);
      }
    } catch (e) {
      console.error("Failed to add event:", e);
    } finally {
      setAddingId(null);
    }
  };

  const handleDeleteEvent = (eventId: string, title: string) => {
    setDialog({
      open: true,
      title: "Delete event",
      description: `Delete "${title.slice(0, 80)}"? This will free up space in the database.`,
      confirmLabel: "Delete",
      confirmVariant: "destructive",
      onConfirm: async () => {
        setDialog((d) => ({ ...d, open: false }));
        setDeletingId(eventId);
        try {
          await deleteEvent(eventId);
          const size = await fetchDbSize();
          setDbSize(size);
        } catch (e) {
          console.error("Failed to delete event:", e);
        } finally {
          setDeletingId(null);
        }
      },
    });
  };

  const handleTruncate = () => {
    setDialog({
      open: true,
      title: "Truncate all events",
      description: "This will permanently delete ALL events from the database. This action cannot be undone.",
      confirmLabel: "Delete All",
      confirmVariant: "destructive",
      onConfirm: async () => {
        setDialog((d) => ({ ...d, open: false }));
        await truncateEvents();
        const size = await fetchDbSize();
        setDbSize(size);
      },
    });
  };

  if (loading) {
    return <div className="flex items-center justify-center min-h-[60vh]">Loading...</div>;
  }

  const pendingIds = new Set(pendingUsers.map((u) => u.id));

  const pctUsed = dbSize ? (dbSize.total_bytes / DB_LIMIT_BYTES) * 100 : 0;
  const barColor = pctUsed > 80 ? "bg-red-500" : pctUsed > 50 ? "bg-yellow-500" : "bg-green-500";

  // Paginated events for DB tab
  const dbEvents = dbSize?.events ?? [];

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <h1 className="text-2xl font-bold mb-6">Admin Panel</h1>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <Button variant={activeTab === "users" ? "default" : "outline"} size="sm" onClick={() => setActiveTab("users")}>Users</Button>
        <Button variant={activeTab === "models" ? "default" : "outline"} size="sm" onClick={() => setActiveTab("models")}>Models</Button>
        <Button variant={activeTab === "events" ? "default" : "outline"} size="sm" onClick={() => setActiveTab("events")}>Events</Button>
        <Button variant={activeTab === "database" ? "default" : "outline"} size="sm" onClick={() => setActiveTab("database")}>Database</Button>
      </div>

      {/* Users Tab */}
      {activeTab === "users" && (
        <Card>
          <CardHeader>
            <CardTitle>Registered Users</CardTitle>
            <CardDescription>{users.length} total, {pendingUsers.length} pending approval</CardDescription>
          </CardHeader>
          <CardContent>
            {pendingUsers.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-medium text-muted-foreground mb-2">Pending Approval</h3>
                <div className="space-y-2">
                  {pendingUsers.map((u) => (
                    <div key={u.id} className="flex items-center justify-between rounded-md border p-3 bg-yellow-50/50">
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium">{u.email}</span>
                        <Badge variant="secondary">pending</Badge>
                        {u.is_admin && <Badge variant="default">admin</Badge>}
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => handleWhitelist(u.id)}>Approve</Button>
                        <Button size="sm" variant="outline" onClick={() => handleReject(u.id, u.email)}>Reject</Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="space-y-2">
              {users.filter((u) => !pendingIds.has(u.id)).map((u) => (
                <div key={u.id} className="flex items-center justify-between rounded-md border p-3">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium">{u.email}</span>
                    <Badge variant={u.whitelisted ? "default" : "secondary"}>{u.whitelisted ? "active" : "inactive"}</Badge>
                    {u.plan === "premium" && <Badge variant="outline">premium</Badge>}
                    {u.is_admin && <Badge variant="default">admin</Badge>}
                  </div>
                  <div className="flex gap-2">
                    {!u.whitelisted && <Button size="sm" onClick={() => handleWhitelist(u.id)}>Approve</Button>}
                    {!u.is_admin && <Button size="sm" variant="outline" onClick={() => handlePromote(u.id)}>Make Admin</Button>}
                    <Button size="sm" variant="outline" onClick={() => handleReject(u.id, u.email)}>Reject</Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Models Tab */}
      {activeTab === "models" && (
        <Card>
          <CardHeader>
            <CardTitle>Available Models</CardTitle>
            <CardDescription>Models available for forecast generation</CardDescription>
          </CardHeader>
          <CardContent>
            {/* Search + Filter */}
            <div className="flex gap-2 mb-4">
              <Input
                placeholder="Search models..."
                value={modelSearch}
                onChange={(e) => setModelSearch(e.target.value)}
                className="flex-1"
              />
              <select
                value={modelProviderFilter}
                onChange={(e) => setModelProviderFilter(e.target.value)}
                className="rounded-md border bg-background px-3 py-2 text-sm"
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
              </select>
            </div>

            {/* Filtered models list */}
            <div className="space-y-2 mb-4">
              {models
                .filter((m) => !modelProviderFilter || m.provider === modelProviderFilter)
                .filter((m) => !modelSearch || m.name.toLowerCase().includes(modelSearch.toLowerCase()) || m.id.toLowerCase().includes(modelSearch.toLowerCase()))
                .map((m) => (
                  <div key={m.id} className="flex items-center justify-between rounded-md border p-3">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium">{m.name}</span>
                      <Badge variant="outline" className="text-xs">{m.provider}</Badge>
                      <Badge variant={m.tier === "free" ? "secondary" : "default"}>{m.tier}</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <code className="text-xs text-muted-foreground">{m.id}</code>
                      <Button size="sm" variant="outline" onClick={() => handleRemoveModel(m.id)}>Remove</Button>
                    </div>
                  </div>
                ))}
              {models.filter((m) => !modelProviderFilter || m.provider === modelProviderFilter)
                .filter((m) => !modelSearch || m.name.toLowerCase().includes(modelSearch.toLowerCase()) || m.id.toLowerCase().includes(modelSearch.toLowerCase())).length === 0 && (
                <p className="text-center text-muted-foreground py-4">No models match your filter.</p>
              )}
            </div>

            {/* Add model */}
            <div className="flex gap-2 mt-4 pt-4 border-t">
              <select
                value={newModelProvider}
                onChange={(e) => setNewModelProvider(e.target.value)}
                className="rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="openrouter">OpenRouter</option>
                <option value="google">Google AI</option>
                <option value="groq">Groq</option>
                <option value="deepseek">DeepSeek</option>
                <option value="mistral">Mistral</option>
                <option value="cerebras">Cerebras</option>
                <option value="fireworks">Fireworks</option>
                <option value="nvidia">NVIDIA</option>
              </select>
              <Input placeholder="Model ID (e.g. gemini-2.0-flash)" value={newModelId} onChange={(e) => setNewModelId(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAddModel()} className="flex-1" />
              <Button onClick={handleAddModel}>Add</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Events Tab — search & add from Polymarket */}
      {activeTab === "events" && (
        <Card>
          <CardHeader>
            <CardTitle>Search Polymarket</CardTitle>
            <CardDescription>Find events on Polymarket and add them to Cortex</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-4 flex-wrap">
              <Input placeholder="Search events on Polymarket..." value={searchQuery} onChange={(e) => { setSearchQuery(e.target.value); setSearchPage(0); }} className="flex-1 min-w-[220px]" />
              <div className="flex rounded-md border bg-background p-1">
                <Button type="button" size="sm" variant={eventView === "list" ? "default" : "ghost"} onClick={() => setEventView("list")}>
                  List
                </Button>
                <Button type="button" size="sm" variant={eventView === "calendar" ? "default" : "ghost"} onClick={() => setEventView("calendar")}>
                  Calendar
                </Button>
              </div>
              <select
                value={deadlineFilter}
                onChange={(e) => { setDeadlineFilter(e.target.value as "all" | "with_deadline" | "without_deadline"); setSearchPage(0); }}
                className="rounded-md border bg-background px-3 py-2 text-sm whitespace-nowrap"
              >
                <option value="all">All deadlines</option>
                <option value="with_deadline">With deadline</option>
                <option value="without_deadline">Without deadline</option>
              </select>
              <select
                value={eventSort}
                onChange={(e) => { setEventSort(e.target.value as "none" | "soonest" | "latest"); setSearchPage(0); }}
                className="rounded-md border bg-background px-3 py-2 text-sm whitespace-nowrap"
              >
                <option value="none">Default</option>
                <option value="soonest">Deadline ↑</option>
                <option value="latest">Deadline ↓</option>
              </select>
            </div>
            {searchLoading ? (
              <p className="text-center text-muted-foreground py-4">Searching...</p>
            ) : searchResults.length === 0 ? (
              <p className="text-center text-muted-foreground py-4">No results found. Try a different search.</p>
            ) : eventView === "list" ? (
              <div className="space-y-2">
                {searchResults.map((market) => (
                  <div key={market.id} className="flex items-center justify-between rounded-md border p-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{market.question}</p>
                      <div className="flex gap-2 mt-1">
                        <Badge variant={market.active ? "default" : "secondary"}>{market.active ? "Active" : "Closed"}</Badge>
                        {market.end_date && <span className="text-xs text-muted-foreground">Ends: {new Date(market.end_date).toLocaleDateString()}</span>}
                      </div>
                    </div>
                    <Button size="sm" onClick={() => handleAddEvent(market.id)} disabled={addingId === market.id}>
                      {addingId === market.id ? "Adding..." : "Add"}
                    </Button>
                  </div>
                ))}
              </div>
            ) : (() => {
              const calendar = buildCalendarSections(searchResults);
              return (
                <div className="space-y-6">
                  {calendar.months.map((month) => (
                    <div key={month.monthKey} className="rounded-lg border bg-muted/20 p-3">
                      <div className="mb-3 flex items-center justify-between">
                        <h3 className="text-sm font-semibold capitalize">{month.monthLabel}</h3>
                        <span className="text-xs text-muted-foreground">{month.cells.reduce((count, cell) => count + cell.events.length, 0)} events</span>
                      </div>
                      <div className="grid grid-cols-7 gap-2 text-xs text-muted-foreground mb-2">
                        {CALENDAR_WEEKDAYS.map((day) => (
                          <div key={`${month.monthKey}-${day}`} className="px-2">{day}</div>
                        ))}
                      </div>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-7">
                        {month.cells.map((cell) => (
                          <div
                            key={cell.key}
                            className={`min-h-28 rounded-md border p-2 ${cell.inMonth ? "bg-background" : "bg-muted/40 text-muted-foreground"}`}
                          >
                            <div className="mb-2 flex items-center justify-between">
                              <span className={`text-xs font-medium ${cell.inMonth ? "text-foreground" : "text-muted-foreground"}`}>
                                {cell.dayNumber}
                              </span>
                              {cell.events.length > 0 && (
                                <Badge variant="outline" className="text-[10px]">{cell.events.length}</Badge>
                              )}
                            </div>
                            <div className="space-y-2">
                              {cell.events.slice(0, 3).map((market) => (
                                <div key={market.id} className="rounded-md border border-border/60 bg-card p-2 shadow-sm">
                                  <p className="text-xs font-medium leading-snug line-clamp-3">{market.question}</p>
                                  <div className="mt-2 flex items-center justify-between gap-2">
                                    <Badge variant={market.active ? "default" : "secondary"} className="text-[10px]">
                                      {market.active ? "Active" : "Closed"}
                                    </Badge>
                                    <Button size="sm" className="h-7 px-2 text-xs" onClick={() => handleAddEvent(market.id)} disabled={addingId === market.id}>
                                      {addingId === market.id ? "..." : "Add"}
                                    </Button>
                                  </div>
                                </div>
                              ))}
                              {cell.events.length > 3 && (
                                <div className="rounded-md border border-dashed px-2 py-1 text-[11px] text-muted-foreground">
                                  +{cell.events.length - 3} more
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}

                  {calendar.withoutDeadline.length > 0 && (
                    <div className="rounded-lg border border-dashed p-3">
                      <div className="mb-3 flex items-center justify-between">
                        <h3 className="text-sm font-semibold">Without deadline</h3>
                        <Badge variant="secondary">{calendar.withoutDeadline.length}</Badge>
                      </div>
                      <div className="space-y-2">
                        {calendar.withoutDeadline.map((market) => (
                          <div key={market.id} className="flex items-center justify-between rounded-md border p-3">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">{market.question}</p>
                              <div className="flex gap-2 mt-1">
                                <Badge variant={market.active ? "default" : "secondary"}>{market.active ? "Active" : "Closed"}</Badge>
                                <span className="text-xs text-muted-foreground">No deadline</span>
                              </div>
                            </div>
                            <Button size="sm" onClick={() => handleAddEvent(market.id)} disabled={addingId === market.id}>
                              {addingId === market.id ? "Adding..." : "Add"}
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}
            {searchTotal > EVENTS_PAGE_SIZE && (
              <div className="mt-4 flex justify-center">
                <Pagination page={searchPage + 1} pageSize={EVENTS_PAGE_SIZE} total={searchTotal} onPageChange={(p) => setSearchPage(p - 1)} />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Database Tab — size, breakdown, delete */}
      {activeTab === "database" && (
        <div className="space-y-6">
          {/* DB Size Overview */}
          <Card>
            <CardHeader>
              <CardTitle>Database Overview</CardTitle>
              <CardDescription>Railway PostgreSQL — 500 MB limit</CardDescription>
            </CardHeader>
            <CardContent>
              {dbLoading ? (
                <p className="text-center text-muted-foreground py-4">Loading...</p>
              ) : dbSize ? (
                <div className="space-y-4">
                  <div className="p-4 rounded-lg border bg-muted/50">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Total Size</span>
                      <span className="text-lg font-bold">{dbSize.total_size}</span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-3 overflow-hidden">
                      <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${Math.min(pctUsed, 100)}%` }} />
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{pctUsed.toFixed(1)}% of 500 MB used</p>
                  </div>

                  {/* Tables breakdown */}
                  <div>
                    <h3 className="text-sm font-medium mb-2">Tables by Size</h3>
                    <div className="rounded-md border overflow-hidden">
                      <table className="w-full text-sm">
                        <thead className="bg-muted">
                          <tr>
                            <th className="text-left px-3 py-2 font-medium">Table</th>
                            <th className="text-right px-3 py-2 font-medium">Size</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dbSize.tables.map((t) => (
                            <tr key={t.table} className="border-t">
                              <td className="px-3 py-2">{t.table}</td>
                              <td className="px-3 py-2 text-right font-mono">{t.size}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-4">Failed to load database info.</p>
              )}
            </CardContent>
          </Card>

          {/* Events in DB */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Events in Database ({dbEvents.length})</span>
                {dbEvents.length > 0 && (
                  <Button size="sm" variant="destructive" onClick={handleTruncate}>Truncate All</Button>
                )}
              </CardTitle>
              <CardDescription>Filter and sort events — delete to free space</CardDescription>
            </CardHeader>
            <CardContent>
              {/* Sort + Filter controls */}
              <div className="flex gap-2 mb-4 flex-wrap">
                <select
                  value={eventDeadlineSort}
                  onChange={(e) => { setEventDeadlineSort(e.target.value as "size" | "soonest" | "latest"); setDbEventPage(0); }}
                  className="rounded-md border bg-background px-3 py-2 text-sm"
                >
                  <option value="size">Sort by size</option>
                  <option value="soonest">Deadline: soonest first</option>
                  <option value="latest">Deadline: latest first</option>
                </select>
                <select
                  value={eventCategoryFilter}
                  onChange={(e) => { setEventCategoryFilter(e.target.value); setDbEventPage(0); }}
                  className="rounded-md border bg-background px-3 py-2 text-sm"
                >
                  <option value="">All categories</option>
                  {Array.from(new Set(dbEvents.map((e) => e.category_normalized))).map((cat) => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>

              {dbLoading ? (
                <p className="text-center text-muted-foreground py-4">Loading...</p>
              ) : dbEvents.length === 0 ? (
                <p className="text-center text-muted-foreground py-4">No events in the database.</p>
              ) : (
                <div className="space-y-2">
                  {(() => {
                    let sorted = [...dbEvents];
                    if (eventCategoryFilter) {
                      sorted = sorted.filter((e) => e.category_normalized === eventCategoryFilter);
                    }
                    if (eventDeadlineSort === "soonest") {
                      sorted.sort((a, b) => {
                        if (!a.end_date && !b.end_date) return 0;
                        if (!a.end_date) return 1;
                        if (!b.end_date) return -1;
                        return new Date(a.end_date).getTime() - new Date(b.end_date).getTime();
                      });
                    } else if (eventDeadlineSort === "latest") {
                      sorted.sort((a, b) => {
                        if (!a.end_date && !b.end_date) return 0;
                        if (!a.end_date) return 1;
                        if (!b.end_date) return -1;
                        return new Date(b.end_date).getTime() - new Date(a.end_date).getTime();
                      });
                    }
                    const page = sorted.slice(dbEventPage * EVENTS_PAGE_SIZE, (dbEventPage + 1) * EVENTS_PAGE_SIZE);
                    return (
                      <>
                        {page.map((ev) => (
                          <div key={ev.id} className="flex items-center justify-between rounded-md border p-3">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">{ev.title}</p>
                              <div className="flex gap-2 mt-1 flex-wrap">
                                <Badge variant="outline">{ev.category_normalized}</Badge>
                                <Badge variant={ev.active ? "default" : "secondary"}>{ev.active ? "Active" : "Closed"}</Badge>
                                {ev.end_date && (
                                  <span className="text-xs text-muted-foreground">
                                    Deadline: {new Date(ev.end_date).toLocaleDateString()}
                                  </span>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-3 ml-2">
                              <span className="text-xs text-muted-foreground whitespace-nowrap font-mono">{ev.size}</span>
                              <Button
                                size="sm"
                                variant="outline"
                                className="text-destructive hover:text-destructive"
                                onClick={() => handleDeleteEvent(ev.id, ev.title)}
                                disabled={deletingId === ev.id}
                              >
                                {deletingId === ev.id ? "..." : "Delete"}
                              </Button>
                            </div>
                          </div>
                        ))}
                        {sorted.length > EVENTS_PAGE_SIZE && (
                          <div className="mt-4 flex justify-center">
                            <Pagination page={dbEventPage + 1} pageSize={EVENTS_PAGE_SIZE} total={sorted.length} onPageChange={(p) => setDbEventPage(p - 1)} />
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <Dialog
        open={dialog.open}
        onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
        title={dialog.title}
        description={dialog.description}
        confirmLabel={dialog.confirmLabel}
        confirmVariant={dialog.confirmVariant}
        onConfirm={dialog.onConfirm}
      />
    </div>
  );
}

export default function AdminPage() {
  return (
    <ProtectedRoute>
      <AdminContent />
    </ProtectedRoute>
  );
}
