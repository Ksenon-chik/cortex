import { Badge, type BadgeProps } from "@/components/ui/badge";

const VERDICT_COLORS: Record<string, NonNullable<BadgeProps["variant"]>> = {
  yes: "success",
  no: "destructive",
  uncertain: "secondary",
};

export function PredictionBadge({ verdict }: { verdict: string }) {
  const variant = VERDICT_COLORS[verdict.toLowerCase()] ?? "outline";
  return <Badge variant={variant}>{verdict}</Badge>;
}
