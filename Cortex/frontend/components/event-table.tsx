"use client";

import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import Link from "next/link";
import { type Event as EventType } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/pagination";

const columns: ColumnDef<EventType>[] = [
  {
    accessorKey: "title",
    header: "Event",
    cell: ({ row }) => (
      <Link
        href={`/events/${row.original.id}`}
        className="font-medium hover:underline text-foreground"
      >
        {row.original.title}
      </Link>
    ),
  },
  {
    accessorKey: "category_normalized",
    header: "Category",
    cell: ({ row }) => (
      <Badge variant="secondary">
        {row.original.category_normalized || row.original.category}
      </Badge>
    ),
  },
  {
    accessorKey: "active",
    header: "Status",
    cell: ({ row }) => (
      <Badge variant={row.original.active ? "success" : "outline"}>
        {row.original.active ? "Active" : "Closed"}
      </Badge>
    ),
  },
];

export function EventTable({
  events,
  page,
  pageSize,
  total,
  onPageChange,
}: {
  events: EventType[];
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const table = useReactTable({
    data: events,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div>
      <div className="rounded-md border">
        <table className="w-full">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="border-b bg-muted/50">
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="h-12 px-4 text-left font-medium">
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-b hover:bg-muted/30">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  No events found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={onPageChange}
      />
    </div>
  );
}
