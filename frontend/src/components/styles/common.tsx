"use client";

import { Badge } from "@/components/ui/badge";
import { t, tEnum } from "@/i18n";
import { cn } from "@/lib/utils";

export function TagChips({ tags, free, className }: { tags: Record<string, string[]>; free?: string[]; className?: string }) {
  const entries = Object.entries(tags ?? {}).flatMap(([dim, values]) => (values ?? []).map((v) => ({ dim, v })));
  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {entries.map(({ dim, v }) => (
        <Badge key={`${dim}:${v}`} variant="outline" className="font-normal">
          <span className="text-muted-foreground">{dim}:</span>
          {v.replace(/_/g, " ")}
        </Badge>
      ))}
      {(free ?? []).map((f) => (
        <Badge key={`free:${f}`} variant="secondary" className="font-normal">
          #{f}
        </Badge>
      ))}
    </div>
  );
}

const RISK_CLASS: Record<string, string> = {
  bajo: "border-status-ok/50 text-status-ok",
  medio: "border-status-warn/60 text-status-warn",
  alto: "border-status-block/60 text-status-block",
};

export function RiskBadge({ risk }: { risk: string }) {
  return (
    <Badge variant="outline" className={RISK_CLASS[risk] ?? ""}>
      {tEnum("risk", risk)}
    </Badge>
  );
}

const STATUS_CLASS: Record<string, string> = {
  activo: "bg-status-ok/15 text-status-ok",
  activa: "bg-status-ok/15 text-status-ok",
  borrador: "bg-muted text-muted-foreground",
  revision: "bg-status-info/15 text-status-info",
  en_revision: "bg-status-info/15 text-status-info",
  archivado: "bg-muted text-muted-foreground line-through",
  archivada: "bg-muted text-muted-foreground line-through",
  rechazada: "bg-status-block/15 text-status-block",
};

export function StatusBadge({ status, group }: { status: string; group: "style_status" | "directive_status" }) {
  return <Badge className={cn("border-transparent", STATUS_CLASS[status])}>{tEnum(group, status)}</Badge>;
}

const CONFLICT_CLASS: Record<string, string> = {
  sin_conflicto: "border-status-ok/40 text-status-ok",
  resuelto_por_prioridad: "border-status-info/50 text-status-info",
  advertencia: "border-status-warn/60 text-status-warn",
  conflicto_bloqueante: "border-status-block/60 text-status-block",
  rechazada_por_regla_dura: "bg-status-block text-white border-transparent",
};

export function ConflictBadge({ status }: { status: string }) {
  return (
    <Badge variant="outline" className={CONFLICT_CLASS[status] ?? ""}>
      {tEnum("conflict_status", status)}
    </Badge>
  );
}

const LINT_CLASS: Record<string, string> = {
  ok: "bg-status-ok/15 text-status-ok border-status-ok/30",
  warn: "bg-status-warn/15 text-status-warn border-status-warn/40",
  block: "bg-status-block/15 text-status-block border-status-block/40",
};

export function LintBadge({ status }: { status: string }) {
  return (
    <Badge variant="outline" className={LINT_CLASS[status] ?? ""}>
      {tEnum("lint", status)}
    </Badge>
  );
}

export type FindingLike = { code: string; severity: string; message: string; rule_id?: string | null };

export function FindingList({ findings }: { findings: FindingLike[] }) {
  if (!findings.length) return <p className="text-xs text-muted-foreground">{t("styles.noFindings")}</p>;
  return (
    <ul className="grid gap-1 text-xs">
      {findings.map((f, i) => (
        <li key={i} className="flex items-start gap-2">
          <span className={cn("mt-1 size-2 shrink-0 rounded-full", f.severity === "block" ? "bg-status-block" : f.severity === "warn" ? "bg-status-warn" : "bg-status-info")} />
          <span>
            {f.rule_id ? <span className="mr-1 font-mono text-[10px]">[{f.rule_id}]</span> : null}
            {f.message}
          </span>
        </li>
      ))}
    </ul>
  );
}

export const lines = (v: string) => v.split("\n").map((s) => s.trim()).filter(Boolean);
export const commas = (v: string) => v.split(",").map((s) => s.trim()).filter(Boolean);
