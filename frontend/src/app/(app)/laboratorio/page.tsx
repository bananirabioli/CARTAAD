"use client";

import { CheckCircle2, Eye, Lock, RefreshCw, RotateCcw, Save } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState, Loading, PageHeader } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { AiRunsTable, LAYERS, ModelPicker, useLabConfig, type LabConfig, type LabRule, type Layer } from "@/components/lab/parts";
import { errMsg } from "@/components/pieces/parts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { fmtDate, t } from "@/i18n";
import { api, refresh, useApi } from "@/lib/api/client";
import { useStateResetOn } from "@/lib/hooks";

// ------------------------------------------------------------------ models

function ModelsTab({ data, onSaved }: { data: LabConfig; onSaved: (c: LabConfig) => void }) {
  const { can } = useSession();
  const [values, setValues] = useStateResetOn<Record<Layer, string>>(data, () =>
    Object.fromEntries(LAYERS.map((l) => [l, data.models[l].client ?? ""])) as Record<Layer, string>);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    try {
      onSaved(await api.put<LabConfig>("/lab/models", { models: values }));
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="grid gap-3">
      {data.key_present ? (
        <p className="flex items-center gap-2 text-sm text-status-ok"><CheckCircle2 className="size-4" />{t("mvp.keyPresent")}</p>
      ) : (
        <p className="rounded-md border border-status-warn/50 bg-status-warn/10 p-3 text-sm">{t("mvp.keyMissing")}</p>
      )}
      <p className="max-w-3xl text-xs text-muted-foreground">{t("lab.modelsHelp")}</p>
      <div className="grid gap-3 md:grid-cols-2">
        {LAYERS.map((layer) => (
          <Card key={layer} className="gap-2 py-4">
            <CardHeader className="px-4">
              <CardTitle className="flex items-center justify-between gap-2 text-sm">
                {t(`lab.layers.${layer}`)}
                <span className="font-mono text-[11px] font-normal text-muted-foreground">{t("lab.effective")}: {values[layer] || data.models[layer].default}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4">
              <ModelPicker kind={layer} value={values[layer]} fallback={data.models[layer].default} onChange={(v) => setValues({ ...values, [layer]: v })} />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={save} disabled={busy || !can("config.manage")}><Save />{t("common.save")}</Button>
        <Button variant="outline" onClick={() => LAYERS.forEach((k) => refresh(`/lab/models?kind=${k}`))}><RefreshCw />{t("lab.refreshCatalog")}</Button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ guides + preview

type Preview = { step: string; prompt_version: string; based_on_run: number; model: string; system: string; user: string; approx_tokens: number };
type HistoryRow = { id: number; at: string; who: string; action: string; note: string };

function GuidesTab({ data, onSaved }: { data: LabConfig; onSaved: (c: LabConfig) => void }) {
  const { can } = useSession();
  const [guides, setGuides] = useStateResetOn<Record<Layer, string>>(data, () => ({ ...data.guides }));
  const [topK, setTopK] = useStateResetOn<string>(data, () => String(data.facts_top_k));
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<"analyze_capture" | "generate_content">("generate_content");
  const [caseId, setCaseId] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const { data: history, mutate: reloadHistory } = useApi<HistoryRow[]>("/lab/history");

  async function save() {
    setBusy(true);
    try {
      onSaved(await api.put<LabConfig>("/lab/guides", { guides, facts_top_k: Number(topK) || undefined }));
      await reloadHistory();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }
  async function showPreview() {
    try {
      setPreview(await api.post<Preview>("/lab/preview", { step, case_id: caseId ? Number(caseId) : null }));
    } catch (err) {
      setPreview(null);
      toast.error(errMsg(err));
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <div className="grid content-start gap-3">
        <p className="text-xs text-muted-foreground">{t("lab.guidesHelp")}</p>
        {LAYERS.map((layer) => (
          <div key={layer} className="grid gap-1.5">
            <Label htmlFor={`g-${layer}`}>{t(`lab.layers.${layer}`)}</Label>
            <Textarea id={`g-${layer}`} rows={4} value={guides[layer]} placeholder={t(`lab.guidePlaceholder.${layer}`)} onChange={(e) => setGuides({ ...guides, [layer]: e.target.value })} />
          </div>
        ))}
        <div className="grid max-w-xs gap-1.5">
          <Label htmlFor="topk">{t("lab.factsTopK")}</Label>
          <Input id="topk" type="number" min={1} max={25} value={topK} onChange={(e) => setTopK(e.target.value)} />
          <p className="text-[11px] text-muted-foreground">{t("lab.factsTopKHelp")}</p>
        </div>
        <div><Button onClick={save} disabled={busy || !can("config.manage")}><Save />{t("common.save")}</Button></div>
        <Card className="gap-2 py-4">
          <CardHeader className="px-4"><CardTitle className="text-sm">{t("lab.history")}</CardTitle></CardHeader>
          <CardContent className="grid gap-1 px-4 text-xs">
            {!history?.length ? <span className="text-muted-foreground">{t("common.none")}</span> : history.map((h) => (
              <div key={h.id} className="flex flex-wrap gap-2"><span className="text-muted-foreground">{fmtDate(h.at)}</span><span>{h.who}</span><Badge variant="outline" className="font-mono text-[10px]">{h.action}</Badge><span className="truncate text-muted-foreground">{h.note}</span></div>
            ))}
          </CardContent>
        </Card>
      </div>
      <div className="grid content-start gap-3">
        <div className="flex flex-wrap items-end gap-2">
          <div className="grid gap-1.5">
            <Label>{t("lab.previewStep")}</Label>
            <Select value={step} onValueChange={(v) => setStep(v as typeof step)}>
              <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="analyze_capture">analyze_capture</SelectItem>
                <SelectItem value="generate_content">generate_content</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="pc">{t("lab.previewCase")}</Label>
            <Input id="pc" className="w-32" value={caseId} onChange={(e) => setCaseId(e.target.value.replace(/\D/g, ""))} />
          </div>
          <Button variant="outline" onClick={showPreview}><Eye />{t("lab.preview")}</Button>
        </div>
        <p className="text-xs text-muted-foreground">{t("lab.previewHelp")}</p>
        {preview ? (
          <div className="grid gap-2">
            <p className="text-xs">{t("lab.previewInfo", { run: preview.based_on_run, model: preview.model, tokens: preview.approx_tokens })}</p>
            <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-[11px] leading-relaxed">{preview.system}</pre>
            <pre className="max-h-[20rem] overflow-auto whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-[11px] leading-relaxed">{preview.user}</pre>
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ rules

function RuleCard({ rule, onSaved }: { rule: LabRule; onSaved: (c: LabConfig) => void }) {
  const { can } = useSession();
  const [text, setText] = useStateResetOn<string>(rule, () => rule.text);
  const [busy, setBusy] = useState(false);
  async function put(patch: Record<string, { enabled: boolean; text?: string | null }>) {
    setBusy(true);
    try {
      onSaved(await api.put<LabConfig>("/lab/rules", { rules: patch }));
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }
  const editable = can("config.manage");
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4">
        <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-mono text-xs text-muted-foreground">{rule.id}</span>{rule.title}
          {rule.locked ? <Badge variant="outline" className="gap-1 text-[10px]"><Lock className="size-3" />{t("lab.locked")}</Badge> : null}
          {rule.custom ? <Badge variant="secondary" className="text-[10px]">{t("lab.customText")}</Badge> : null}
          {rule.can_disable ? (
            <label className="ml-auto flex items-center gap-2 text-xs font-normal">
              {t("lab.ruleActive")}
              <Switch checked={rule.active} disabled={busy || !editable} onCheckedChange={(v) => put({ [rule.id]: { enabled: v, text: rule.custom ? rule.text : null } })} />
            </label>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2 px-4">
        <Textarea rows={2} value={text} disabled={!editable} onChange={(e) => setText(e.target.value)} className="text-xs" />
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={busy || !editable || text === rule.text} onClick={() => put({ [rule.id]: { enabled: rule.active, text } })}><Save />{t("lab.saveRule")}</Button>
          {rule.custom ? <Button size="sm" variant="ghost" disabled={busy || !editable} onClick={() => put({ [rule.id]: { enabled: rule.active, text: null } })}><RotateCcw />{t("lab.resetText")}</Button> : null}
        </div>
        {rule.switches.length ? (
          <div className="grid gap-2 rounded-md border p-3">
            {rule.switches.map((sw) => (
              <label key={sw.id} className="flex items-start gap-3">
                <Switch checked={sw.enabled} disabled={busy || !editable} onCheckedChange={(v) => put({ [sw.id]: { enabled: v } })} />
                <span className="grid gap-0.5"><span className="text-xs font-medium">{sw.title} <span className="font-mono text-muted-foreground">{sw.id}</span></span><span className="text-[11px] text-muted-foreground">{sw.help}</span></span>
              </label>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function RulesTab({ data, onSaved }: { data: LabConfig; onSaved: (c: LabConfig) => void }) {
  return (
    <div className="grid gap-3">
      <p className="max-w-4xl text-xs text-muted-foreground">{t("lab.rulesHelp")}</p>
      <div className="grid gap-3 lg:grid-cols-2">{data.rules.map((r) => <RuleCard key={r.id} rule={r} onSaved={onSaved} />)}</div>
    </div>
  );
}

// ------------------------------------------------------------------ page

export default function LabPage() {
  const { data, mutate, error } = useLabConfig();
  const onSaved = (c: LabConfig) => { void mutate(c, { revalidate: false }); };
  return (
    <div>
      <PageHeader title={t("lab.title")} subtitle={t("lab.subtitle")} />
      {error ? <EmptyState label={errMsg(error)} /> : !data ? <Loading /> : (
        <Tabs defaultValue="models">
          <TabsList className="h-auto flex-wrap">
            <TabsTrigger value="models">{t("lab.tabs.models")}</TabsTrigger>
            <TabsTrigger value="guides">{t("lab.tabs.guides")}</TabsTrigger>
            <TabsTrigger value="rules">{t("lab.tabs.rules")}</TabsTrigger>
            <TabsTrigger value="runs">{t("lab.tabs.runs")}</TabsTrigger>
          </TabsList>
          <TabsContent value="models" className="mt-3"><ModelsTab data={data} onSaved={onSaved} /></TabsContent>
          <TabsContent value="guides" className="mt-3"><GuidesTab data={data} onSaved={onSaved} /></TabsContent>
          <TabsContent value="rules" className="mt-3"><RulesTab data={data} onSaved={onSaved} /></TabsContent>
          <TabsContent value="runs" className="mt-3"><AiRunsTable /></TabsContent>
        </Tabs>
      )}
    </div>
  );
}
