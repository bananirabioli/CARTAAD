"use client";

import { Plus, RefreshCw, ShieldAlert, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState, Loading } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { enumOptions, fmtDate, fmtDay, t, tEnum } from "@/i18n";
import { api, ApiError, refresh, useApi, type Schemas } from "@/lib/api/client";
import { useStateResetOn, useTopics } from "@/lib/hooks";
import { cn } from "@/lib/utils";

import { commas, ConflictBadge, StatusBadge } from "./common";

type Directive = Schemas["DirectiveOut"];
type Finding = { id: string; kind: string; other: string; severity: string; explanation: string; resolution?: string; ai_suggested?: boolean; confirmed?: boolean | null };

function errMsg(err: unknown) {
  return err instanceof ApiError ? err.message : String(err);
}

function scopeSummary(scope: Record<string, unknown[]>) {
  const parts = Object.entries(scope ?? {}).filter(([, v]) => (v ?? []).length).map(([k, v]) => `${k}: ${(v as unknown[]).join(", ")}`);
  return parts.length ? parts.join(" · ") : t("directives.scopeAll");
}

export function DirectivesTab() {
  const { can } = useSession();
  const { data, isLoading, mutate } = useApi<Directive[]>("/directives");
  const [selected, setSelected] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="max-w-3xl text-xs text-muted-foreground">{t("directives.precedence")}</p>
        <div className="ml-auto flex gap-2">
          {can("directive.activate") ? (
            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                await api.post("/directives/recheck-all");
                await mutate();
              }}
            >
              <RefreshCw />
              {t("directives.recheckAll")}
            </Button>
          ) : null}
          {can("directive.propose") ? (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus />
              {t("directives.new")}
            </Button>
          ) : null}
        </div>
      </div>
      {isLoading ? <Loading /> : !data?.length ? <EmptyState /> : (
        <div className="rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-20">{t("directives.code")}</TableHead>
                <TableHead>{t("directives.titleField")}</TableHead>
                <TableHead className="w-32">{t("directives.type")}</TableHead>
                <TableHead className="w-24">{t("directives.mandatory")}</TableHead>
                <TableHead className="w-16 text-right">{t("directives.priority")}</TableHead>
                <TableHead className="w-28">{t("directives.status")}</TableHead>
                <TableHead className="w-48">{t("directives.conflicts")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((d) => (
                <TableRow key={d.id} className="cursor-pointer" onClick={() => setSelected(d.id)}>
                  <TableCell className="font-mono text-xs">
                    {d.code}
                    <span className="text-muted-foreground"> v{d.version}</span>
                  </TableCell>
                  <TableCell className="whitespace-normal">
                    <div className="text-sm">{d.title}</div>
                    <div className="text-xs text-muted-foreground">{scopeSummary(d.scope as Record<string, unknown[]>)}</div>
                  </TableCell>
                  <TableCell className="text-xs">{tEnum("directive_type", d.dtype)}</TableCell>
                  <TableCell className="text-xs">{tEnum("mandatory", d.mandatory)}</TableCell>
                  <TableCell className="text-right font-mono text-xs">{d.priority}</TableCell>
                  <TableCell>
                    <StatusBadge status={d.status} group="directive_status" />
                    {d.status === "activa" && !d.in_force ? <div className="mt-1 text-[10px] text-muted-foreground">{t("directives.notInForce")}</div> : null}
                  </TableCell>
                  <TableCell>
                    <ConflictBadge status={d.conflict_status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <DirectiveSheet id={selected} onClose={() => setSelected(null)} onSelect={setSelected} />
      <DirectiveEditor open={creating} onOpenChange={setCreating} onSaved={(d) => setSelected(d.id)} />
    </div>
  );
}

function DirectiveSheet({ id, onClose, onSelect }: { id: number | null; onClose: () => void; onSelect: (id: number) => void }) {
  const { can, me } = useSession();
  const { data: d, mutate } = useApi<Directive>(id ? `/directives/${id}` : null);
  const { data: versions } = useApi<Directive[]>(id ? `/directives/${id}/versions` : null);
  const [editing, setEditing] = useState(false);
  const canActivate = d ? can("directive.activate") || (can("directive.activate_kb") && ["narrativa", "vocabulario"].includes(d.dtype)) : false;

  async function act(path: string, body: unknown = {}) {
    try {
      await api.post(path, body);
      await mutate();
      await refresh("/directives");
    } catch (err) {
      toast.error(errMsg(err));
      await mutate();
    }
  }

  const report = (d?.conflict_report ?? {}) as { hard_rules?: { rule_id: string; snippet: string; message: string }[]; findings?: Finding[]; checked_at?: string };

  return (
    <Sheet open={id !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        {!d ? <Loading className="p-6" /> : (
          <>
            <SheetHeader>
              <SheetTitle className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm">{d.code} v{d.version}</span>
                {d.title}
              </SheetTitle>
              <SheetDescription className="flex flex-wrap items-center gap-2">
                <StatusBadge status={d.status} group="directive_status" />
                <ConflictBadge status={d.conflict_status} />
                <Badge variant="outline">{tEnum("directive_type", d.dtype)}</Badge>
                <Badge variant="outline">{tEnum("mandatory", d.mandatory)} · {d.priority}</Badge>
              </SheetDescription>
            </SheetHeader>
            <div className="grid gap-4 px-4 pb-8 text-sm">
              <p>{d.text}</p>
              <div className="grid gap-1 text-xs">
                <p><span className="text-muted-foreground">{t("directives.scope")}: </span>{scopeSummary(d.scope as Record<string, unknown[]>)}</p>
                <p><span className="text-muted-foreground">{t("directives.validFrom")}: </span>{fmtDay(d.valid_from)} · <span className="text-muted-foreground">{t("directives.validUntil")}: </span>{fmtDay(d.valid_until)}</p>
                {Object.keys(d.structured ?? {}).length ? (
                  <p><span className="text-muted-foreground">{t("directives.structured")}: </span><code className="text-[11px]">{JSON.stringify(d.structured)}</code></p>
                ) : null}
                {d.created_by_name ? <p className="text-muted-foreground">{t("directives.createdBy", { name: d.created_by_name })}</p> : null}
                {d.approved_by_name ? <p className="text-muted-foreground">{t("directives.approvedBy", { name: d.approved_by_name })}</p> : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {can("directive.propose") ? <Button size="sm" variant="outline" onClick={() => setEditing(true)}>{t("common.edit")}</Button> : null}
                <Button size="sm" variant="outline" onClick={() => act(`/directives/${d.id}/check`)}><RefreshCw />{t("directives.recheck")}</Button>
                {d.status === "borrador" && can("directive.propose") ? <Button size="sm" variant="outline" onClick={() => act(`/directives/${d.id}/transition`, { status: "en_revision" })}>{t("directives.submit")}</Button> : null}
                {["borrador", "en_revision"].includes(d.status) && canActivate ? <Button size="sm" onClick={() => act(`/directives/${d.id}/transition`, { status: "activa" })}>{t("directives.activate")}</Button> : null}
                {d.status === "en_revision" && canActivate ? <Button size="sm" variant="outline" onClick={() => act(`/directives/${d.id}/transition`, { status: "rechazada" })}>{t("directives.reject")}</Button> : null}
                {d.status === "activa" && canActivate ? <Button size="sm" variant="outline" onClick={() => act(`/directives/${d.id}/transition`, { status: "archivada" })}>{t("directives.archive")}</Button> : null}
                {["rechazada", "archivada"].includes(d.status) && can("directive.propose") ? <Button size="sm" variant="ghost" onClick={() => act(`/directives/${d.id}/transition`, { status: "borrador" })}>{t("directives.toDraft")}</Button> : null}
              </div>
              {d.rejection_reason ? (
                <div className="rounded-md border border-status-block/40 bg-status-block/5 p-3 text-xs">
                  <p className="font-medium">{t("directives.rejectionReason")}</p>
                  <p>{d.rejection_reason}</p>
                </div>
              ) : null}
              <div className="grid gap-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {t("directives.report")} {report.checked_at ? `· ${t("directives.checkedAt", { date: fmtDate(report.checked_at) })}` : ""}
                </p>
                {(report.hard_rules ?? []).map((h) => (
                  <div key={h.rule_id} className="flex gap-2 rounded-md border border-status-block/50 bg-status-block/5 p-2 text-xs">
                    <ShieldAlert className="size-4 shrink-0 text-status-block" />
                    <span>{h.message}</span>
                  </div>
                ))}
                {(report.findings ?? []).map((f) => (
                  <div
                    key={f.id}
                    className={cn(
                      "grid gap-1 rounded-md border p-2 text-xs",
                      f.severity === "bloqueante" && "border-status-block/50 bg-status-block/5",
                      f.severity === "advertencia" && "border-status-warn/50 bg-status-warn/5",
                      f.severity === "resuelto" && "border-status-info/40 bg-status-info/5",
                    )}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{tEnum("finding_kind", f.kind)}</Badge>
                      <Badge variant="outline">{tEnum("finding_severity", f.severity)}</Badge>
                      <span className="font-mono">{f.other}</span>
                      {f.ai_suggested ? <Badge className="gap-1 border-transparent bg-status-info/15 text-status-info"><Sparkles className="size-3" />{t("directives.aiSuggested")}</Badge> : null}
                    </div>
                    <p>{f.explanation}</p>
                    {f.resolution ? <p className="text-muted-foreground">{t("directives.resolution")}: {f.resolution}</p> : null}
                    {f.ai_suggested ? (
                      f.confirmed ? <p className="text-status-ok">{t("directives.confirmed")}</p> : canActivate || can("legal.review") ? (
                        <div className="flex gap-2">
                          <Button size="xs" variant="outline" onClick={() => act(`/directives/${d.id}/findings`, { finding_id: f.id, confirmed: true })}>{t("directives.confirm")}</Button>
                          <Button size="xs" variant="ghost" onClick={() => act(`/directives/${d.id}/findings`, { finding_id: f.id, confirmed: false })}>{t("directives.dismiss")}</Button>
                        </div>
                      ) : null
                    ) : null}
                  </div>
                ))}
                {!(report.hard_rules ?? []).length && !(report.findings ?? []).length ? <p className="text-xs text-status-ok">{tEnum("conflict_status", "sin_conflicto")}</p> : null}
              </div>
              {versions && versions.length > 1 ? (
                <div className="grid gap-1">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("directives.versions")}</p>
                  {versions.map((v) => (
                    <button key={v.id} onClick={() => onSelect(v.id)} className={cn("flex items-center gap-2 rounded px-2 py-1 text-left text-xs hover:bg-muted", v.id === d.id && "bg-muted")}>
                      <span className="font-mono">v{v.version}</span>
                      <StatusBadge status={v.status} group="directive_status" />
                      <ConflictBadge status={v.conflict_status} />
                      <span className="ml-auto text-muted-foreground">{fmtDate(v.updated_at)}</span>
                    </button>
                  ))}
                </div>
              ) : null}
              <span className="hidden">{me?.user.id}</span>
            </div>
            <DirectiveEditor open={editing} onOpenChange={setEditing} directive={d} onSaved={(nd) => { void mutate(); onSelect(nd.id); }} />
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

type DraftD = {
  dtype: string; title: string; text: string; mandatory: string; priority: number; valid_from: string; valid_until: string;
  prohibited: string; required: string; legend: string; max_intensity: string; required_intensity: string; priority_topics: string;
  topics: string[]; formats: string[]; styles: string[]; flows: string[];
};

function toDraftD(d?: Directive): DraftD {
  const s = (d?.structured ?? {}) as Record<string, unknown>;
  const sc = (d?.scope ?? {}) as Record<string, string[]>;
  const list = (k: string) => ((s[k] as string[] | undefined) ?? []).join(", ");
  return {
    dtype: d?.dtype ?? "narrativa", title: d?.title ?? "", text: d?.text ?? "", mandatory: d?.mandatory ?? "sugerida", priority: d?.priority ?? 50,
    valid_from: d?.valid_from?.slice(0, 10) ?? "", valid_until: d?.valid_until?.slice(0, 10) ?? "",
    prohibited: list("vocabulario_prohibido"), required: list("vocabulario_obligatorio"), legend: String(s.leyenda_texto ?? ""),
    max_intensity: s.intensidad_maxima ? String(s.intensidad_maxima) : "", required_intensity: s.intensidad_requerida ? String(s.intensidad_requerida) : "",
    priority_topics: list("temas_prioritarios"),
    topics: sc.topics ?? [], formats: sc.formats ?? [], styles: sc.styles ?? [], flows: sc.flows ?? [],
  };
}

function fromDraftD(d: DraftD) {
  const structured: Record<string, unknown> = {};
  if (commas(d.prohibited).length) structured.vocabulario_prohibido = commas(d.prohibited);
  if (commas(d.required).length) structured.vocabulario_obligatorio = commas(d.required);
  if (d.legend.trim()) structured.leyenda_texto = d.legend.trim();
  if (d.max_intensity) structured.intensidad_maxima = Number(d.max_intensity);
  if (d.required_intensity) structured.intensidad_requerida = Number(d.required_intensity);
  if (commas(d.priority_topics).length) structured.temas_prioritarios = commas(d.priority_topics);
  const scope: Record<string, string[]> = {};
  for (const k of ["topics", "formats", "styles", "flows"] as const) if (d[k].length) scope[k] = d[k];
  return {
    dtype: d.dtype, title: d.title, text: d.text, mandatory: d.mandatory, priority: Number(d.priority), structured, scope,
    valid_from: d.valid_from ? `${d.valid_from}T00:00:00Z` : null, valid_until: d.valid_until ? `${d.valid_until}T23:59:59Z` : null,
  };
}

function MultiCheck({ label, options, value, onChange }: { label: string; options: { value: string; label: string }[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="col-span-2 grid gap-1">
      <Label>{label}</Label>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {options.map((o) => (
          <label key={o.value} className="flex items-center gap-1.5 text-xs">
            <Checkbox checked={value.includes(o.value)} onCheckedChange={(c) => onChange(c ? [...value, o.value] : value.filter((x) => x !== o.value))} />
            {o.label}
          </label>
        ))}
      </div>
    </div>
  );
}

function F({ label, children, span = 2 }: { label: string; children: React.ReactNode; span?: 1 | 2 }) {
  return (
    <div className={cn("grid gap-1.5", span === 2 ? "col-span-2" : "col-span-1")}>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function DirectiveEditor({ open, onOpenChange, directive, onSaved }: { open: boolean; onOpenChange: (o: boolean) => void; directive?: Directive; onSaved: (d: Directive) => void }) {
  const topics = useTopics();
  const { data: styles } = useApi<Schemas["StyleOut"][]>("/styles");
  const resetKey = open ? (directive ?? "new") : "closed";
  const [d, setD] = useStateResetOn<DraftD>(resetKey, () => toDraftD(directive));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useStateResetOn<string | null>(resetKey, () => null);
  const set = <K extends keyof DraftD>(k: K, v: DraftD[K]) => setD((p) => ({ ...p, [k]: v }));
  async function save() {
    setBusy(true);
    setError(null);
    try {
      const body = fromDraftD(d);
      const saved = directive ? await api.patch<Directive>(`/directives/${directive.id}`, body) : await api.post<Directive>("/directives", body);
      await refresh("/directives");
      onSaved(saved);
      onOpenChange(false);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{directive ? `${directive.code} · ${t("common.edit")}` : t("directives.new")}</DialogTitle>
        </DialogHeader>
        <div className="grid max-h-[65vh] grid-cols-2 gap-3 overflow-y-auto pr-1">
          <F label={t("directives.type")} span={1}>
            <Select value={d.dtype} onValueChange={(v) => set("dtype", v)}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{enumOptions("directive_type").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
            </Select>
          </F>
          <F label={t("directives.mandatory")} span={1}>
            <Select value={d.mandatory} onValueChange={(v) => set("mandatory", v)}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{enumOptions("mandatory").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
            </Select>
          </F>
          <F label={t("directives.titleField")}><Input value={d.title} onChange={(e) => set("title", e.target.value)} /></F>
          <F label={t("directives.text")}><Textarea rows={3} value={d.text} onChange={(e) => set("text", e.target.value)} /></F>
          <F label={t("directives.priority")} span={1}><Input type="number" min={1} max={100} value={d.priority} onChange={(e) => set("priority", Number(e.target.value))} /></F>
          <div />
          <F label={t("directives.validFrom")} span={1}><Input type="date" value={d.valid_from} onChange={(e) => set("valid_from", e.target.value)} /></F>
          <F label={t("directives.validUntil")} span={1}><Input type="date" value={d.valid_until} onChange={(e) => set("valid_until", e.target.value)} /></F>
          <p className="col-span-2 mt-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("directives.structured")}</p>
          <F label={t("directives.prohibited")} span={1}><Input value={d.prohibited} onChange={(e) => set("prohibited", e.target.value)} /></F>
          <F label={t("directives.required")} span={1}><Input value={d.required} onChange={(e) => set("required", e.target.value)} /></F>
          <F label={t("directives.legend")}><Input value={d.legend} onChange={(e) => set("legend", e.target.value)} /></F>
          <F label={t("directives.maxIntensity")} span={1}><Input type="number" min={1} max={5} value={d.max_intensity} onChange={(e) => set("max_intensity", e.target.value)} /></F>
          <F label={t("directives.requiredIntensity")} span={1}><Input type="number" min={1} max={5} value={d.required_intensity} onChange={(e) => set("required_intensity", e.target.value)} /></F>
          <F label={t("directives.priorityTopics")}><Input value={d.priority_topics} onChange={(e) => set("priority_topics", e.target.value)} /></F>
          <p className="col-span-2 mt-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("directives.scope")}</p>
          <MultiCheck label={t("directives.scopeTopics")} options={topics.list.map((x) => ({ value: x.slug, label: x.name }))} value={d.topics} onChange={(v) => set("topics", v)} />
          <MultiCheck label={t("directives.scopeFormats")} options={enumOptions("format")} value={d.formats} onChange={(v) => set("formats", v)} />
          <MultiCheck label={t("directives.scopeStyles")} options={(styles ?? []).map((s) => ({ value: s.slug, label: s.name }))} value={d.styles} onChange={(v) => set("styles", v)} />
          <MultiCheck label={t("directives.scopeFlows")} options={[{ value: "A", label: "A" }, { value: "B", label: "B" }]} value={d.flows} onChange={(v) => set("flows", v)} />
        </div>
        {error ? <p className="text-sm text-status-block">{error}</p> : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t("common.cancel")}</Button>
          <Button disabled={busy || d.title.length < 3} onClick={save}>{busy ? t("common.saving") : t("common.save")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
