"use client";

import { FileCheck2, FileWarning } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { fmtDay, t } from "@/i18n";
import { cn } from "@/lib/utils";

export type SourceInfo = {
  code: string;
  statement?: string;
  source_label?: string;
  document?: { title: string; issued_at?: string | null } | null;
  fact_date?: string | null;
  expired?: boolean;
};

/** HR-01: every visible figure carries its source. Hover shows the fact, document and date. */
export function SourceBadge({ fact, className }: { fact: SourceInfo; className?: string }) {
  const warn = !fact.document || fact.expired;
  const Icon = warn ? FileWarning : FileCheck2;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            "inline-flex cursor-help items-center gap-1 rounded border px-1.5 py-0.5 align-middle font-mono text-[10px] leading-none",
            warn ? "border-status-warn/50 bg-status-warn/10" : "border-status-ok/40 bg-status-ok/10",
            className,
          )}
        >
          <Icon className="size-3" />
          {fact.code}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm text-xs">
        {fact.statement ? <p className="font-medium">{fact.statement}</p> : null}
        <p className="mt-1 opacity-80">
          {fact.document ? fact.document.title : t("kb.facts.noDocument")} · {fmtDay(fact.document?.issued_at ?? fact.fact_date)}
        </p>
        {fact.expired ? <p className="mt-1 font-medium">{t("kb.facts.expired")}</p> : null}
      </TooltipContent>
    </Tooltip>
  );
}
