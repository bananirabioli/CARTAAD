"use client";

import { Trophy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { FormDialog } from "@/components/app/form-dialog";
import { useSession } from "@/components/app/session";
import { errMsg } from "@/components/pieces/parts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtNum, t, tEnum } from "@/i18n";
import { api, refresh, useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type RankRow = { value: string; n: number; ok: number; rate: number; sufficient: boolean; avg_reach_ratio?: number | null; avg_sentiment_delta?: number | null };

export function RankingTable({ rows, kind }: { rows: RankRow[]; kind: "formats" | "styles" | "strategies" | "creatives" }) {
  const label = (v: string) => (kind === "formats" ? tEnum("format", v) : kind === "strategies" ? tEnum("strategy", v) : kind === "creatives" ? tEnum("creative", v) : v);
  if (!rows.length) return <p className="text-xs text-muted-foreground">{t("common.empty")}</p>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t(`metrics.${kind}`)}</TableHead>
          <TableHead className="w-40">{t("metrics.rate")}</TableHead>
          <TableHead className="w-20 text-right">{t("metrics.sample")}</TableHead>
          <TableHead className="w-24 text-right">{t("metrics.reach")}</TableHead>
          <TableHead className="w-24 text-right">{t("metrics.sentiment")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.value} className={r.sufficient ? "" : "text-muted-foreground"}>
            <TableCell className="text-sm">{label(r.value)}{!r.sufficient ? <span className="ml-2 text-[10px] uppercase">{t("metrics.insufficient")}</span> : null}</TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"><div className={cn("h-full rounded-full", r.sufficient ? "bg-status-ok" : "bg-muted-foreground/40")} style={{ width: `${r.rate * 100}%` }} /></div>
                <span className="w-10 text-right font-mono text-xs">{fmtNum(r.rate * 100, 0)}%</span>
              </div>
            </TableCell>
            <TableCell className="text-right font-mono text-xs">{r.ok}/{r.n}</TableCell>
            <TableCell className="text-right font-mono text-xs">{r.avg_reach_ratio !== null && r.avg_reach_ratio !== undefined ? `${fmtNum(r.avg_reach_ratio, 1)}×` : t("common.none")}</TableCell>
            <TableCell className="text-right font-mono text-xs">{r.avg_sentiment_delta !== null && r.avg_sentiment_delta !== undefined ? fmtNum(r.avg_sentiment_delta, 2) : t("common.none")}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function variantLabel(v: Record<string, unknown>) {
  return String(v.label).startsWith("copy") ? String(v.label) : tEnum("creative", String(v.label));
}

/** Stacked variant list for narrow columns (case sidebar). */
function VariantsList({ variants }: { variants: Record<string, unknown>[] }) {
  return (
    <div className="grid gap-2">
      {variants.map((v) => (
        <div key={String(v.piece_id)} className="grid gap-1 rounded-md border p-2">
          <div className="flex flex-wrap items-center gap-1.5 text-sm">
            {variantLabel(v)}
            {v.winner ? <Badge className="gap-1 border-transparent bg-status-ok/15 text-status-ok"><Trophy className="size-3" />{t("metrics.winner")}</Badge> : null}
            {v.source === "simulado" ? <Badge variant="outline">sim</Badge> : null}
          </div>
          <p className="text-xs text-muted-foreground">{String(v.style)} · {tEnum("strategy", String(v.strategy))}</p>
          <div className="grid grid-cols-3 gap-2 font-mono text-xs">
            <span title={t("metrics.reach")}>{v.reach_ratio !== null ? `${fmtNum(Number(v.reach_ratio), 1)}×` : t("common.none")}</span>
            <span title={t("metrics.engagement")}>{fmtNum(Number(v.engagement_rate) * 100, 1)}%</span>
            <span title={t("metrics.sentiment")} className={cn(Number(v.sentiment_delta) > 0 ? "text-status-ok" : Number(v.sentiment_delta) < 0 ? "text-status-block" : "")}>Δ {fmtNum(Number(v.sentiment_delta), 2)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function VariantsTable({ variants, compact = false }: { variants: Record<string, unknown>[]; compact?: boolean }) {
  if (!variants.length) return <p className="text-xs text-muted-foreground">{t("metrics.noExperiments")}</p>;
  if (compact) return <VariantsList variants={variants} />;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("metrics.variant")}</TableHead>
          <TableHead className="text-right">{t("metrics.fields.reach")}</TableHead>
          <TableHead className="text-right">{t("metrics.reach")}</TableHead>
          <TableHead className="text-right">{t("metrics.engagement")}</TableHead>
          <TableHead className="text-right">{t("metrics.sentiment")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {variants.map((v) => (
          <TableRow key={String(v.piece_id)}>
            <TableCell className="text-sm">
              {variantLabel(v)}
              <span className="ml-2 text-xs text-muted-foreground">{String(v.style)} · {tEnum("strategy", String(v.strategy))}</span>
              {v.winner ? <Badge className="ml-2 gap-1 border-transparent bg-status-ok/15 text-status-ok"><Trophy className="size-3" />{t("metrics.winner")}</Badge> : null}
              {v.source === "simulado" ? <Badge variant="outline" className="ml-2">sim</Badge> : null}
            </TableCell>
            <TableCell className="text-right font-mono text-xs">{fmtNum(Number(v.reach))}</TableCell>
            <TableCell className="text-right font-mono text-xs">{v.reach_ratio !== null ? `${fmtNum(Number(v.reach_ratio), 1)}×` : t("common.none")}</TableCell>
            <TableCell className="text-right font-mono text-xs">{fmtNum(Number(v.engagement_rate) * 100, 1)}%</TableCell>
            <TableCell className={cn("text-right font-mono text-xs", Number(v.sentiment_delta) > 0 ? "text-status-ok" : Number(v.sentiment_delta) < 0 ? "text-status-block" : "")}>{fmtNum(Number(v.sentiment_delta), 2)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function CaseMetricsPanel({ caseId, onChanged }: { caseId: number; onChanged: () => void }) {
  const { can } = useSession();
  const { data, mutate } = useApi<Schemas["CaseMetricsOut"]>(`/cases/${caseId}/metrics`);
  const { data: published } = useApi<Schemas["Page_InboxItem_"]>(`/inbox?status=publicado&case_id=${caseId}`);
  const [recording, setRecording] = useState(false);
  if (!data) return null;
  async function act(path: string, body?: unknown) {
    try {
      await api.post(path, body);
      await mutate();
      onChanged();
      await refresh("/metrics", "/dashboard");
    } catch (err) {
      toast.error(errMsg(err));
    }
  }
  return (
    <div className="grid gap-3 text-sm">
      <p className="text-xs text-muted-foreground">{t("metrics.originalReach", { reach: fmtNum(data.original_reach) })}</p>
      <p className="text-[11px] text-muted-foreground">{t("metrics.reach")} · {t("metrics.engagement")} · {t("metrics.sentiment")}</p>
      <VariantsTable variants={data.variants} compact />
      {data.rating ? <Badge className={cn("w-fit border-transparent", data.rating === "funciono" ? "bg-status-ok/15 text-status-ok" : "bg-status-block/15 text-status-block")}>{t("metrics.rated", { outcome: tEnum("outcome", data.rating) })}</Badge> : null}
      <div className="flex flex-wrap gap-2">
        {can("metrics.record") && ["publicado", "medido"].includes(data.status) ? (
          <>
            <Button size="sm" variant="outline" onClick={() => setRecording(true)}>{t("metrics.record")}</Button>
            <Button size="sm" variant="ghost" onClick={() => act(`/cases/${caseId}/metrics/simulate`)}>{t("metrics.simulate")}</Button>
          </>
        ) : null}
        {can("case.rate") && data.status === "medido" ? (
          <>
            <Button size="sm" onClick={() => act(`/cases/${caseId}/rate`, { outcome: "funciono" })}>{t("metrics.rateWorked")}</Button>
            <Button size="sm" variant="outline" onClick={() => act(`/cases/${caseId}/rate`, { outcome: "no_funciono" })}>{t("metrics.rateFailed")}</Button>
          </>
        ) : null}
      </div>
      <FormDialog
        open={recording}
        onOpenChange={setRecording}
        title={t("metrics.record")}
        fields={[
          { name: "piece_id", label: t("metrics.fields.piece"), type: "select", required: true, options: (published?.items ?? []).map((p) => ({ value: String(p.id), label: p.kind === "copy" ? `Copy ${p.style_slug}` : tEnum("creative", p.creative_slug) })) },
          { name: "reach", label: t("metrics.fields.reach"), type: "number", required: true, colSpan: 1 },
          { name: "impressions", label: t("metrics.fields.impressions"), type: "number", colSpan: 1 },
          { name: "likes", label: t("metrics.fields.likes"), type: "number", colSpan: 1 },
          { name: "comments", label: t("metrics.fields.comments"), type: "number", colSpan: 1 },
          { name: "shares", label: t("metrics.fields.shares"), type: "number", colSpan: 1 },
          { name: "sentiment_pos", label: t("metrics.fields.pos"), type: "number", colSpan: 1 },
          { name: "sentiment_neg", label: t("metrics.fields.neg"), type: "number", colSpan: 1 },
          { name: "sentiment_neu", label: t("metrics.fields.neu"), type: "number", colSpan: 1 },
        ]}
        onSubmit={async (v) => {
          const body = Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x === null ? 0 : Number(x)]));
          await act(`/cases/${caseId}/metrics`, body);
        }}
      />
    </div>
  );
}
