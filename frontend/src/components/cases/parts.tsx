"use client";

import { AlertCircle, CheckCircle2, CircleHelp, CircleSlash } from "lucide-react";

import { SourceBadge } from "@/components/app/source-badge";
import { Badge } from "@/components/ui/badge";
import { fmtNum, t, tEnum } from "@/i18n";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const STATUS_CLASS: Record<string, string> = {
  interpretado: "bg-status-info/15 text-status-info",
  revision_legal: "bg-veda/15 text-veda",
  listo_para_generar: "bg-primary/10 text-primary",
  generando: "bg-primary/10 text-primary",
  generado: "bg-status-warn/15 text-status-warn",
  en_revision: "bg-status-warn/15 text-status-warn",
  aprobado: "bg-status-ok/15 text-status-ok",
  programado: "bg-status-ok/15 text-status-ok",
  publicado: "bg-status-ok/25 text-status-ok",
  medido: "bg-status-ok/25 text-status-ok",
  calificado: "bg-muted text-foreground",
  monitoreando: "bg-muted text-muted-foreground",
  ignorado: "bg-muted text-muted-foreground",
  canalizado: "bg-muted text-muted-foreground",
  descartado: "bg-muted text-muted-foreground line-through",
};

export function CaseStatusBadge({ status }: { status: string }) {
  return <Badge className={cn("border-transparent", STATUS_CLASS[status] ?? "bg-muted")}>{tEnum("case_status", status)}</Badge>;
}

const VERDICT: Record<string, { cls: string; Icon: React.ComponentType<{ className?: string }> }> = {
  cierta: { cls: "border-status-ok/50 text-status-ok", Icon: CheckCircle2 },
  falsa: { cls: "border-status-block/50 text-status-block", Icon: CircleSlash },
  incompleta: { cls: "border-status-warn/60 text-status-warn", Icon: AlertCircle },
  no_verificable: { cls: "border-muted-foreground/40 text-muted-foreground", Icon: CircleHelp },
};

export function VerdictBadge({ verdict }: { verdict: string }) {
  const v = VERDICT[verdict] ?? VERDICT.no_verificable;
  return (
    <Badge variant="outline" className={cn("gap-1", v.cls)}>
      <v.Icon className="size-3" />
      {tEnum("verdict", verdict)}
    </Badge>
  );
}

export function RiskMeter({ score, className }: { score: number | null | undefined; className?: string }) {
  if (score === null || score === undefined) return <span className="text-xs text-muted-foreground">{t("common.none")}</span>;
  const color = score >= 60 ? "bg-status-block" : score >= 35 ? "bg-status-warn" : "bg-status-ok";
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${Math.min(100, score)}%` }} />
      </div>
      <span className="font-mono text-xs">{score}</span>
    </div>
  );
}

export function RiskBreakdown({ items }: { items: Record<string, unknown>[] }) {
  const max = Math.max(1, ...items.map((i) => Number(i.weight)));
  return (
    <div className="grid gap-2">
      {items.map((i) => (
        <div key={String(i.factor)} className="grid gap-0.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium">{String(i.label)}</span>
            <span className="font-mono text-muted-foreground">
              {fmtNum(Number(i.points), 1)} / {fmtNum(Number(i.weight), 0)}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary/70" style={{ width: `${(Number(i.points) / max) * 100}%` }} />
          </div>
          <p className="text-[11px] text-muted-foreground">{String(i.explanation)}</p>
        </div>
      ))}
    </div>
  );
}

export function ClaimList({ claims, facts }: { claims: Schemas["ClaimOut"][]; facts: Schemas["FactOut"][] }) {
  const byId = new Map(facts.map((f) => [f.id, f]));
  if (!claims.length) return <p className="text-xs text-muted-foreground">{t("cases.noClaims")}</p>;
  return (
    <ul className="grid gap-2">
      {claims.map((c) => (
        <li key={c.id} className="grid gap-1 rounded-md border p-2 text-sm">
          <div className="flex items-start gap-2">
            <VerdictBadge verdict={c.verdict} />
            <span className="flex-1">«{c.text}»</span>
          </div>
          <p className="text-xs text-muted-foreground">{c.explanation}</p>
          <div className="flex flex-wrap gap-1">
            {c.fact_ids.map((id) => {
              const f = byId.get(id);
              return f ? <SourceBadge key={id} fact={f} /> : null;
            })}
          </div>
          {c.missing_data ? <p className="text-xs text-status-warn">{t("cases.askKbOwner")}: {c.missing_data}</p> : null}
        </li>
      ))}
    </ul>
  );
}

export function LearningTable({ learning }: { learning: Record<string, unknown> }) {
  const groups = ["styles", "strategies", "formats"] as const;
  const label = { styles: t("kb.history.style"), strategies: t("kb.history.strategy"), formats: t("kb.history.format") };
  return (
    <div className="grid gap-2 text-xs">
      <p className="text-muted-foreground">
        {t("cases.sample", { n: Number(learning.sample_size ?? 0), min: Number(learning.min_sample ?? 5) })}
        {!learning.sufficient ? ` · ${t("cases.insufficient")}` : ""}
      </p>
      {groups.map((g) => {
        const rows = (learning[g] as { value: string; n: number; ok: number; rate: number; sufficient: boolean }[] | undefined) ?? [];
        if (!rows.length) return null;
        return (
          <div key={g} className="grid gap-1">
            <p className="font-medium">{label[g]}</p>
            {rows.slice(0, 4).map((r) => (
              <div key={r.value} className="flex items-center gap-2">
                <span className="w-36 truncate">{g === "formats" ? tEnum("format", r.value) : g === "strategies" ? tEnum("strategy", r.value) : r.value}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <div className={cn("h-full rounded-full", r.sufficient ? "bg-status-ok" : "bg-muted-foreground/40")} style={{ width: `${r.rate * 100}%` }} />
                </div>
                <span className="w-14 text-right font-mono">
                  {r.ok}/{r.n}
                </span>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
