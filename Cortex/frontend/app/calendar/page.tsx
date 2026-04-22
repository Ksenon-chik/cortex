"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAllEvents, fetchCategories } from "@/lib/api";
import { EventCalendar } from "@/components/event-calendar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";

export default function CalendarPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState<"all" | "active" | "closed">("all");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data: allEvents, isLoading } = useQuery({
    queryKey: ["calendar-events"],
    queryFn: () => fetchAllEvents(),
  });

  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
  });

  const filteredEvents = useMemo(() => {
    const searchLower = debouncedSearch.trim().toLowerCase();
    return (allEvents ?? []).filter((event) => {
      const matchesCategory = !category || event.category_normalized === category;
      const matchesStatus =
        status === "all" ||
        (status === "active" && event.active) ||
        (status === "closed" && !event.active);
      const haystack = `${event.title} ${event.description ?? ""}`.toLowerCase();
      const matchesSearch = !searchLower || haystack.includes(searchLower);
      return matchesCategory && matchesStatus && matchesSearch;
    });
  }, [allEvents, category, status, debouncedSearch]);

  const withDeadline = filteredEvents.filter((event) => event.end_date).length;

  return (
    <div className="container mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Forecast Calendar</h1>
          <p className="mt-2 text-muted-foreground">
            Browse imported forecast events by date and jump straight to the event details page.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{filteredEvents.length} total</Badge>
          <Badge variant="outline">{withDeadline} with deadline</Badge>
          <Badge variant="outline">
            {filteredEvents.length - withDeadline} without deadline
          </Badge>
        </div>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 lg:flex-row">
          <div className="relative w-full lg:max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search forecast events..."
              className="pl-9"
            />
          </div>

          <Select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full lg:w-56"
          >
            <option value="">All categories</option>
            {categories?.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>

          <Select
            value={status}
            onChange={(e) =>
              setStatus(e.target.value as "all" | "active" | "closed")
            }
            className="w-full lg:w-48"
          >
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="closed">Closed only</option>
          </Select>
        </CardContent>
      </Card>

      {isLoading ? (
        <p className="py-12 text-center text-muted-foreground">
          Loading forecast calendar...
        </p>
      ) : (
        <EventCalendar events={filteredEvents} />
      )}
    </div>
  );
}
