import Link from "next/link";
import { type Event } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/pagination";

export function EventGrid({
  events,
  page,
  pageSize,
  total,
  onPageChange,
}: {
  events: Event[];
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <div>
      {events.length === 0 ? (
        <p className="text-center text-muted-foreground py-12">No events found.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {events.map((event) => (
            <Link key={event.id} href={`/events/${event.id}`}>
              <Card className="hover:shadow-md transition-shadow h-full cursor-pointer">
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant="secondary">
                      {event.category_normalized || event.category}
                    </Badge>
                    <Badge
                      variant={event.active ? "success" : "outline"}
                      className="ml-auto"
                    >
                      {event.active ? "Active" : "Closed"}
                    </Badge>
                  </div>
                  <CardTitle className="text-base line-clamp-2">
                    {event.title}
                  </CardTitle>
                </CardHeader>
                {event.description && (
                  <CardContent>
                    <CardDescription className="line-clamp-3">
                      {event.description}
                    </CardDescription>
                  </CardContent>
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}

      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={onPageChange}
      />
    </div>
  );
}
