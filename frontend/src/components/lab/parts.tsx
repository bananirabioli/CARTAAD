"use client";

import { Cpu } from "lucide-react";
import { useId, useState } from "react";

import { JsonBlock, Loading, Pagination } from "@/components/app/common";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import messages from "@/i18n/es-MX.json";
import { fmtDate, t } from "@/i18n";
import { qs, useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export type Layer = "analysis" | "text" | "image" | "video";
export const LAYERS: Layer[] = ["analysis", "text", "image", "video"];
export const ENGAGEMENT_CHIPS: string[] = messages.lab.chips;

export type CatalogModel = { id: string; name: string; price?: string | null; notes?: string; structured?: boolean };
export type LabRule = {
  id: string; title: string; locked: boolean; default_text: string; text: string; custom: boolean; active: boolean; can_disable: boolean;
  switches: { id: string; title: string; help: string; enabled: boolean }[];
};
export type LabConfig = {
  providers: { llm: string; image: string; video: string };
  key_present: boolean;
  models: Record<Layer, { default: string; client: string | null; effective: string }>;
  guides: Record<Layer, string>;
  rules: LabRule[];
  facts_top_k: number;
  video_seconds: number;
};

export function useLabConfig() {
  return useApi<LabConfig>("/lab/config");
}

/** Free-text input with the OpenRouter catalog as suggestions (native datalist: searchable, accepts any id). */
export function ModelPicker({ kind, value, onChange, fallback, className }: { kind: Layer; value: string; onChange: (v: string) => void; fallback?: string; className?: string }) {
  const listId = useId();
  const { data } = useApi<CatalogModel[]>(`/lab/models?kind=${kind}`, { revalidateOnFocus: false });
  const current = data?.find((m) => m.id === value);
  return (
    <div className={cn("grid gap-1", className)}>
      <Input list={listId} value={value} onChange={(e) => onChange(e.target.value)} placeholder={fallback ? `${t("lab.modelDefault")}: ${fallback}` : t("lab.modelPlaceholder")} className="font-mono text-xs" />
      <datalist id={listId}>
        {(data ?? []).map((m) => <option key={m.id} value={m.id}>{[m.name, m.price].filter(Boolean).join(" · ")}</option>)}
      </datalist>
      {current ? <p className="text-[11px] text-muted-foreground">{[current.price, current.notes].filter(Boolean).join(" · ")}</p> : null}
    </div>
  );
}

/** Which model produced a result: shown on pieces and on the analysis card. */
export function ModelBadge({ model, className }: { model?: string | null; className?: string }) {
  if (!model) return null;
  return (
    <Badge variant="outline" className={cn("gap-1 font-mono text-[10px] font-normal", className)} title={`${t("lab.madeBy")} ${model}`}>
      <Cpu className="size-3" />{model}
    </Badge>
  );
}

export function AiRunsTable() {
  const [page, setPage] = useState(1);
  const [step, setStep] = useState("");
  const [model, setModel] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const { data } = useApi<Schemas["Page_AiRunOut_"]>(`/ai-runs${qs({ page, page_size: 30, step })}`);
  const { data: detail } = useApi<Schemas["AiRunDetail"]>(openId ? `/ai-runs/${openId}` : null);
  const items = (data?.items ?? []).filter((r) => !model || r.model.toLowerCase().includes(model.toLowerCase()));
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-xs text-muted-foreground">{t("settings.ai.help")}</p>
        <Input className="ml-auto w-48" placeholder={t("settings.ai.step")} value={step} onChange={(e) => { setStep(e.target.value); setPage(1); }} />
        <Input className="w-56" placeholder={t("lab.runsFilterModel")} value={model} onChange={(e) => setModel(e.target.value)} />
      </div>
      <div className="overflow-x-auto rounded-lg border bg-card">
        <Table>
          <TableHeader><TableRow><TableHead>{t("common.date")}</TableHead><TableHead>{t("settings.ai.step")}</TableHead><TableHead>{t("settings.ai.prompt")}</TableHead><TableHead>{t("settings.ai.provider")}</TableHead><TableHead>{t("kb.history.style")}</TableHead><TableHead className="text-right">{t("settings.ai.latency")}</TableHead><TableHead>{t("settings.ai.status")}</TableHead></TableRow></TableHeader>
          <TableBody>
            {items.map((r) => (
              <TableRow key={r.id} className="cursor-pointer" onClick={() => setOpenId(r.id)}>
                <TableCell className="text-xs">{fmtDate(r.created_at)}</TableCell>
                <TableCell className="font-mono text-xs">{r.step}{r.case_id ? ` · caso ${r.case_id}` : ""}</TableCell>
                <TableCell className="font-mono text-xs">v{r.prompt_version}</TableCell>
                <TableCell className="text-xs">{r.provider} · <span className="font-mono">{r.model}</span></TableCell>
                <TableCell className="text-xs">{r.style_slug ? `${r.style_slug} v${r.style_version}` : t("common.none")}</TableCell>
                <TableCell className="text-right font-mono text-xs">{r.latency_ms} ms</TableCell>
                <TableCell><Badge variant={r.status === "ok" ? "outline" : "destructive"}>{r.status}</Badge></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {data ? <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} /> : null}
      <Sheet open={openId !== null} onOpenChange={(o) => !o && setOpenId(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
          <SheetHeader><SheetTitle className="font-mono">{detail?.step} #{detail?.id} · {detail?.model}</SheetTitle></SheetHeader>
          {detail ? <div className="grid gap-3 px-4 pb-6"><p className="text-xs">{detail.error}</p><p className="text-xs font-medium">Input</p><JsonBlock value={detail.input} /><p className="text-xs font-medium">Output</p><JsonBlock value={detail.output} /></div> : <Loading />}
        </SheetContent>
      </Sheet>
    </div>
  );
}
