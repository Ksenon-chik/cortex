"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchEvents, fetchCategories } from "@/lib/api";
import { EventTable } from "@/components/event-table";
import { EventGrid } from "@/components/event-grid";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LayoutGrid, List, Search } from "lucide-react";

export default function EventsPage() {
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [viewMode, setViewMode] = useState<"table" | "grid">("table");
  const pageSize = 10;

  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("eventsViewMode") as "table" | "grid" | null;
      if (saved) setViewMode(saved);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading } = useQuery({
    queryKey: ["events", page, category, debouncedSearch],
    queryFn: () =>
      fetchEvents(
        page,
        pageSize,
        category || undefined,
        debouncedSearch || undefined
      ),
  });

  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
  });

  const toggleView = () => {
    const next = viewMode === "table" ? "grid" : "table";
    setViewMode(next);
    localStorage.setItem("eventsViewMode", next);
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <h1 className="text-2xl font-bold">Events</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search events..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-56 pl-9"
            />
          </div>
          <Select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
            className="w-48"
          >
            <option value="">All Categories</option>
            {categories?.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <Button variant="outline" size="icon" onClick={toggleView}>
            {viewMode === "table" ? (
              <LayoutGrid className="h-4 w-4" />
            ) : (
              <List className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-center text-muted-foreground py-12">Loading events...</p>
      ) : data ? (
        viewMode === "table" ? (
          <EventTable
            events={data.items}
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={setPage}
          />
        ) : (
          <EventGrid
            events={data.items}
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={setPage}
          />
        )
      ) : (
        <p className="text-center text-muted-foreground py-12">No events found.</p>
      )}
    </div>
  );
}
