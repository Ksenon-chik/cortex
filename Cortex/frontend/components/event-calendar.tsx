"use client";

import Link from "next/link";
import { type Event } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

const CALENDAR_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type CalendarMonth = {
  monthKey: string;
  monthLabel: string;
  cells: Array<{
    key: string;
    dayNumber: number;
    isoDate: string;
    inMonth: boolean;
    events: Event[];
  }>;
};

function formatDeadlineLabel(value: string | null) {
  if (!value) return "No deadline";
  return new Date(value).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function calendarStatusLabel(event: Event) {
  if (event.resolved_outcome) return `Resolved: ${event.resolved_outcome}`;
  return event.active ? "Active" : "Outcome pending";
}

function buildCalendarMonths(events: Event[]): {
  months: CalendarMonth[];
  withoutDeadline: Event[];
} {
  const datedEvents = events.filter((event) => event.end_date);
  const withoutDeadline = events.filter((event) => !event.end_date);
  const monthMap = new Map<string, Event[]>();

  for (const event of datedEvents) {
    const date = new Date(event.end_date as string);
    const monthKey = `${date.getUTCFullYear()}-${String(
      date.getUTCMonth() + 1
    ).padStart(2, "0")}`;
    const bucket = monthMap.get(monthKey) ?? [];
    bucket.push(event);
    monthMap.set(monthKey, bucket);
  }

  const months = Array.from(monthMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([monthKey, monthEvents]) => {
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

      const eventsByDay = new Map<string, Event[]>();
      for (const event of monthEvents) {
        const isoDate = (event.end_date as string).slice(0, 10);
        const bucket = eventsByDay.get(isoDate) ?? [];
        bucket.push(event);
        eventsByDay.set(isoDate, bucket);
      }

      const cells: CalendarMonth["cells"] = [];
      const cursor = new Date(gridStart);
      while (cursor <= gridEnd) {
        const isoDate = cursor.toISOString().slice(0, 10);
        cells.push({
          key: `${monthKey}-${isoDate}`,
          dayNumber: cursor.getUTCDate(),
          isoDate,
          inMonth: cursor.getUTCMonth() === monthStart.getUTCMonth(),
          events: (eventsByDay.get(isoDate) ?? []).sort((a, b) => {
            if (!a.end_date || !b.end_date) return 0;
            return (
              new Date(a.end_date).getTime() - new Date(b.end_date).getTime()
            );
          }),
        });
        cursor.setUTCDate(cursor.getUTCDate() + 1);
      }

      return {
        monthKey,
        monthLabel: monthStart.toLocaleDateString(undefined, {
          month: "long",
          year: "numeric",
          timeZone: "UTC",
        }),
        cells,
      };
    });

  return { months, withoutDeadline };
}

export function EventCalendar({ events }: { events: Event[] }) {
  const calendar = buildCalendarMonths(events);

  if (events.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-12">
        No forecast events match the current filters.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      {calendar.months.map((month) => (
        <section key={month.monthKey} className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold capitalize">{month.monthLabel}</h2>
            <Badge variant="secondary">
              {month.cells.reduce((sum, cell) => sum + cell.events.length, 0)} deadlines
            </Badge>
          </div>

          <div className="grid grid-cols-7 gap-2 text-xs font-medium text-muted-foreground">
            {CALENDAR_WEEKDAYS.map((weekday) => (
              <div key={weekday} className="rounded-md border bg-muted/40 px-2 py-2 text-center">
                {weekday}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-7">
            {month.cells.map((cell) => (
              <div
                key={cell.key}
                className={[
                  "min-h-36 rounded-xl border p-3",
                  cell.inMonth ? "bg-background" : "bg-muted/20 text-muted-foreground",
                ].join(" ")}
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-semibold">{cell.dayNumber}</span>
                  {cell.events.length > 0 && (
                    <Badge variant="outline" className="text-[10px]">
                      {cell.events.length}
                    </Badge>
                  )}
                </div>

                <div className="space-y-2">
                  {cell.events.slice(0, 3).map((event) => (
                    <Link
                      key={event.id}
                      href={`/events/${event.id}`}
                      className="block rounded-lg border bg-muted/30 px-2 py-2 transition-colors hover:bg-muted/60"
                    >
                      <div className="mb-1 flex items-center gap-1.5">
                        <Badge
                          variant={event.resolved_outcome ? "default" : event.active ? "success" : "outline"}
                          className="text-[10px]"
                        >
                          {calendarStatusLabel(event)}
                        </Badge>
                        <Badge variant="secondary" className="text-[10px]">
                          {event.category_normalized || event.category}
                        </Badge>
                      </div>
                      <p className="line-clamp-2 text-xs font-medium text-foreground">
                        {event.title}
                      </p>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        {formatDeadlineLabel(event.end_date)}
                      </p>
                    </Link>
                  ))}

                  {cell.events.length > 3 && (
                    <p className="text-[11px] text-muted-foreground">
                      +{cell.events.length - 3} more forecasts
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}

      {calendar.withoutDeadline.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Without deadline</h2>
            <Badge variant="secondary">{calendar.withoutDeadline.length}</Badge>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {calendar.withoutDeadline.map((event) => (
              <Link
                key={event.id}
                href={`/events/${event.id}`}
                className="rounded-xl border p-4 transition-colors hover:bg-muted/30"
              >
                <div className="mb-2 flex items-center gap-2">
                  <Badge variant={event.active ? "success" : "outline"}>
                    {calendarStatusLabel(event)}
                  </Badge>
                  <Badge variant="secondary">
                    {event.category_normalized || event.category}
                  </Badge>
                </div>
                <p className="font-medium">{event.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">No deadline</p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
