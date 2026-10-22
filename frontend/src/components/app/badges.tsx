"use client";

import { Badge } from "@/components/ui/badge";
import { fmtNum, t, tEnum } from "@/i18n";
import { cn } from "@/lib/utils";

const ALERT_CLASS: Record<string, string> = {
  bajo: "bg-alert-bajo/15 text-alert-bajo border-alert-bajo/40",
  medio: "bg-alert-medio/20 text-[color-mix(in_oklch,var(--alert-medio),black_35%)] border-alert-medio/50",
  alto: "bg-alert-alto/15 text-alert-alto border-alert-alto/50",
  critico: "bg-alert-critico text-white border-transparent",
  sin_linea_base: "bg-alert-sin-base/10 text-alert-sin-base border-alert-sin-base/40",
};

export function AlertBadge({ level, ratio, className }: { level: string | null | undefined; ratio?: number | null; className?: string }) {
  if (!level) return <span className="text-xs text-muted-foreground">{t("common.none")}</span>;
  return (
    <Badge variant="outline" className={cn("gap-1", ALERT_CLASS[level], className)}>
      {tEnum("alert_level", level)}
      {ratio !== null && ratio !== undefined ? <span className="font-mono text-[10px] opacity-80">{t("monitoring.ratio", { value: fmtNum(ratio, 1) })}</span> : null}
    </Badge>
  );
}

export const ALERT_ORDER = ["critico", "alto", "medio", "bajo", "sin_linea_base"];

/** Tiny inline sparkline for interaction snapshots (cumulative totals). */
export function Sparkline({ points, width = 160, height = 36 }: { points: { x: number; y: number }[]; width?: number; height?: number }) {
  if (points.length < 2) return null;
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
  const sx = (x: number) => ((x - x0) / Math.max(1, x1 - x0)) * (width - 4) + 2;
  const sy = (y: number) => height - 2 - ((y - y0) / Math.max(1, y1 - y0)) * (height - 4);
  const d = points.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(" ");
  return (
    <svg width={width} height={height} className="text-primary" aria-hidden>
      <path d={d} fill="none" stroke="currentColor" strokeWidth={1.5} />
    </svg>
  );
}
