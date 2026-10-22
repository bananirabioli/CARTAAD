"use client";

import { Copy, Download, FlaskConical, Plus, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { EmptyState, Loading } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { fmtDate, t, tEnum } from "@/i18n";
import { api, ApiError, refresh, useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

import { commas, FindingList, lines, LintBadge, RiskBadge, StatusBadge, TagChips } from "./common";

type Style = Schemas["StyleOut"];
type Dim = Schemas["TagDimensionOut"];

function errMsg(err: unknown) {
  return err instanceof ApiError ? err.message : String(err);
}

export function StylesTab() {
  const { can } = useSession();
  const [showBase, setShowBase] = useState(false);
  const { data, isLoading } = useApi<Style[]>(`/styles?include_base=${showBase}`);
  const [selected, setSelected] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const own = (data ?? []).filter((s) => !s.is_base);
  const base = (data ?? []).filter((s) => s.is_base);

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={showBase} onCheckedChange={setShowBase} />
          {t("styles.showBase")}
        </label>
        <div className="ml-auto flex gap-2">
          {can("style.edit") ? (
            <>
              <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>
                <Upload />
                {t("styles.import")}
              </Button>
              <Button size="sm" onClick={() => setCreating(true)}>
                <Plus />
                {t("styles.new")}
              </Button>
            </>
          ) : null}
        </div>
      </div>
      {isLoading ? <Loading /> : !own.length ? <EmptyState /> : <StyleGrid styles={own} onOpen={setSelected} />}
      {showBase && base.length ? (
        <>
          <Separator />
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("styles.base")}</p>
          <StyleGrid styles={base} onOpen={setSelected} />
        </>
      ) : null}
      <StyleSheet styleId={selected} onClose={() => setSelected(null)} onSelect={setSelected} />
      <StyleEditor open={creating} onOpenChange={setCreating} onSaved={(s) => setSelected(s.id)} />
      <ImportDialog open={importOpen} onOpenChange={setImportOpen} onSaved={(s) => setSelected(s.id)} />
    </div>
  );
}

function StyleGrid({ styles, onOpen }: { styles: Style[]; onOpen: (id: number) => void }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {styles.map((s) => (
        <Card key={s.id} className="cursor-pointer gap-2 transition-colors hover:border-ring" onClick={() => onOpen(s.id)}>
          <CardHeader className="gap-1">
            <div className="flex items-start justify-between gap-2">
              <CardTitle className="text-sm">
                {s.name} <span className="font-mono text-xs font-normal text-muted-foreground">v{s.version}</span>
              </CardTitle>
              <div className="flex gap-1">
                {s.is_base ? <Badge variant="secondary">{t("styles.base")}</Badge> : <StatusBadge status={s.status} group="style_status" />}
              </div>
            </div>
            <p className="text-xs text-muted-foreground">{s.description}</p>
          </CardHeader>
          <CardContent className="grid gap-2">
            <TagChips tags={s.tags} free={s.free_tags} />
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <RiskBadge risk={s.risk} />
              <Badge variant="outline">{t("styles.intensity", { min: s.intensity_min, max: s.intensity_max })}</Badge>
              {s.requires_legal ? <Badge variant="outline" className="border-status-block/50 text-status-block">{t("styles.requiresLegal")}</Badge> : null}
              <div className="ml-auto flex gap-0.5">
                {s.palette.map((c) => (
                  <span key={c} className="size-3 rounded-sm border" style={{ background: c }} />
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function StyleSheet({ styleId, onClose, onSelect }: { styleId: number | null; onClose: () => void; onSelect: (id: number) => void }) {
  const { can } = useSession();
  const { data: style, mutate } = useApi<Style>(styleId ? `/styles/${styleId}` : null);
  const [editing, setEditing] = useState(false);
  const [cloneOpen, setCloneOpen] = useState(false);

  async function transition(status: string) {
    if (!style) return;
    try {
      await api.post(`/styles/${style.id}/transition`, { status });
      await mutate();
      await refresh("/styles");
    } catch (err) {
      toast.error(errMsg(err));
    }
  }

  async function legalApprove() {
    if (!style) return;
    try {
      await api.post(`/styles/${style.id}/legal-approve`);
      await mutate();
      await refresh("/styles");
    } catch (err) {
      toast.error(errMsg(err));
    }
  }

  async function exportJson() {
    if (!style) return;
    const data = await api.get(`/styles/${style.id}/export`);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `estilo-${style.slug}-v${style.version}.json`;
    a.click();
  }

  return (
    <Sheet open={styleId !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-3xl">
        {!style ? (
          <Loading className="p-6" />
        ) : (
          <>
            <SheetHeader>
              <SheetTitle className="flex flex-wrap items-center gap-2">
                {style.name}
                <span className="font-mono text-xs text-muted-foreground">
                  {style.slug} · v{style.version}
                </span>
                {style.is_base ? <Badge variant="secondary">{t("styles.base")}</Badge> : <StatusBadge status={style.status} group="style_status" />}
                <RiskBadge risk={style.risk} />
              </SheetTitle>
              <SheetDescription>{style.description}</SheetDescription>
            </SheetHeader>
            <div className="grid gap-4 px-4 pb-8">
              <div className="flex flex-wrap gap-2">
                {!style.is_base && (can("style.edit") || can("style.visual_guide")) ? (
                  <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                    {t("styles.edit")}
                  </Button>
                ) : null}
                {can("style.edit") ? (
                  <Button size="sm" variant="outline" onClick={() => setCloneOpen(true)}>
                    <Copy />
                    {style.is_base ? t("styles.clone") : t("styles.cloneAs")}
                  </Button>
                ) : null}
                <Button size="sm" variant="ghost" onClick={exportJson}>
                  <Download />
                  {t("styles.export")}
                </Button>
                {!style.is_base ? (
                  <div className="ml-auto flex flex-wrap gap-2">
                    {style.status === "borrador" && can("style.edit") ? (
                      <Button size="sm" variant="outline" onClick={() => transition("revision")}>
                        {t("styles.toReview")}
                      </Button>
                    ) : null}
                    {(style.requires_legal || style.risk === "alto") && !style.legal_approved_at && can("style.approve_high_risk") ? (
                      <Button size="sm" variant="outline" onClick={legalApprove}>
                        {t("styles.legalApprove")}
                      </Button>
                    ) : null}
                    {["borrador", "revision"].includes(style.status) && can("style.activate") ? (
                      <Button size="sm" onClick={() => transition("activo")}>
                        {t("styles.activate")}
                      </Button>
                    ) : null}
                    {style.status === "activo" && can("style.activate") ? (
                      <Button size="sm" variant="outline" onClick={() => transition("archivado")}>
                        {t("styles.archive")}
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </div>
              {style.status === "activo" ? <p className="text-xs text-muted-foreground">{t("styles.editActiveHint")}</p> : null}
              {style.legal_approved_at ? (
                <p className="text-xs text-status-ok">{t("styles.legalApproved", { name: style.legal_approved_by_name ?? "" })}</p>
              ) : null}

              <TagChips tags={style.tags} free={style.free_tags} />
              <div className="grid gap-3 md:grid-cols-2">
                <Detail label={t("styles.fields.haz")} items={style.guidelines?.haz ?? []} />
                <Detail label={t("styles.fields.evita")} items={style.guidelines?.evita ?? []} />
                <Detail label={t("styles.fields.prohibited")} items={style.prohibited_vocab} inline />
                <Detail label={t("styles.fields.preferred")} items={style.preferred_vocab} inline />
                <Detail label={t("styles.fields.good")} items={style.good_examples} />
                <Detail label={t("styles.fields.bad")} items={style.bad_examples} />
              </div>
              <div className="grid gap-1">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("styles.fields.visualGuide")}</p>
                <p className="text-sm">{style.visual_guide}</p>
                <div className="flex gap-1">
                  {style.palette.map((c) => (
                    <span key={c} className="h-5 w-8 rounded border" style={{ background: c }} title={c} />
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-1 text-xs">
                <span className="text-muted-foreground">{t("styles.fields.formats")}:</span>
                {style.allowed_formats.map((f) => (
                  <Badge key={f} variant="outline">
                    {tEnum("format", f)}
                  </Badge>
                ))}
              </div>
              {!style.is_base ? <TestPanel styleId={style.id} /> : null}
              {style.versions?.length ? (
                <div className="grid gap-1">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("styles.versions")}</p>
                  {style.versions.map((v) => (
                    <button
                      key={String(v.id)}
                      onClick={() => onSelect(Number(v.id))}
                      className={cn("flex items-center gap-2 rounded px-2 py-1 text-left text-xs hover:bg-muted", Number(v.id) === style.id && "bg-muted")}
                    >
                      <span className="font-mono">v{String(v.version)}</span>
                      <StatusBadge status={String(v.status)} group="style_status" />
                      <span className="text-muted-foreground">{String(v.change_note ?? "")}</span>
                      <span className="ml-auto text-muted-foreground">{fmtDate(String(v.updated_at))}</span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            <StyleEditor
              open={editing}
              onOpenChange={setEditing}
              style={style}
              onSaved={(s) => {
                void mutate();
                onSelect(s.id);
              }}
            />
            <CloneDialog open={cloneOpen} onOpenChange={setCloneOpen} style={style} onSaved={(s) => onSelect(s.id)} />
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Detail({ label, items, inline }: { label: string; items: string[]; inline?: boolean }) {
  return (
    <div className="grid gap-1">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      {inline ? (
        <div className="flex flex-wrap gap-1">
          {items.length ? items.map((i) => <Badge key={i} variant="outline">{i}</Badge>) : <span className="text-xs text-muted-foreground">{t("common.none")}</span>}
        </div>
      ) : (
        <ul className="list-disc space-y-0.5 pl-4 text-sm">
          {items.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TestPanel({ styleId }: { styleId: number }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Schemas["StyleTestOut"] | null>(null);
  useEffect(() => setResult(null), [styleId]);
  async function run() {
    setBusy(true);
    try {
      setResult(await api.post<Schemas["StyleTestOut"]>(`/styles/${styleId}/test`, { text: text || null }));
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card className="gap-3 border-dashed py-4">
      <CardHeader className="px-4">
        <CardTitle className="flex items-center gap-2 text-sm">
          <FlaskConical className="size-4" />
          {t("styles.test")}
        </CardTitle>
        <p className="text-xs text-muted-foreground">{t("styles.testHelp")}</p>
      </CardHeader>
      <CardContent className="grid gap-3 px-4">
        <Textarea rows={2} placeholder={t("styles.testText")} value={text} onChange={(e) => setText(e.target.value)} />
        <div>
          <Button size="sm" onClick={run} disabled={busy}>
            {busy ? t("common.loading") : t("styles.testRun")}
          </Button>
        </div>
        {result ? (
          <div className="grid gap-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <LintBadge status={result.lint_status} />
              {result.topic ? <Badge variant="outline">{t("styles.detectedTopic", { topic: result.topic })}</Badge> : null}
              <Badge variant="outline">{tEnum("strategy", result.strategy)}</Badge>
            </div>
            <div className="rounded-md border bg-background p-3 text-sm leading-relaxed whitespace-pre-line">{result.text}</div>
            <div className="grid gap-1">
              {result.segments.map((s, i) => (
                <div key={i} className="flex gap-2 text-xs">
                  <Badge variant="secondary" className="shrink-0">{tEnum("segment_type", String(s.type))}</Badge>
                  <span className="text-muted-foreground">{String(s.text)}</span>
                </div>
              ))}
            </div>
            {result.missing_data.length ? (
              <p className="text-xs text-status-warn">
                {t("styles.missingData")}: {result.missing_data.join("; ")}
              </p>
            ) : null}
            <p className="text-xs">
              <span className="font-medium">{t("styles.why")}: </span>
              {result.why}
            </p>
            <div className="grid gap-1">
              <p className="text-xs font-medium">{t("styles.findings")}</p>
              <FindingList findings={result.findings as never} />
            </div>
            <AppliedList applied={(result.resolved.applied_directives as Record<string, unknown>[]) ?? []} />
            <details className="text-xs">
              <summary className="cursor-pointer text-muted-foreground">{t("styles.styleBlock")}</summary>
              <pre className="mt-1 overflow-auto rounded bg-muted p-2 font-mono text-[11px] whitespace-pre-wrap">{result.style_block}</pre>
            </details>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function AppliedList({ applied }: { applied: Record<string, unknown>[] }) {
  if (!applied.length) return null;
  return (
    <div className="grid gap-1">
      <p className="text-xs font-medium">{t("styles.appliedDirectives")}</p>
      <div className="flex flex-wrap gap-1">
        {applied.map((a) => (
          <Badge
            key={String(a.code)}
            variant="outline"
            title={(a.notes as string[] | undefined)?.join(" ")}
            className={cn("font-normal", a.effect === "conflicto" && "border-status-block/60 text-status-block", a.effect === "parcial" && "border-status-warn/60")}
          >
            <span className="font-mono">{String(a.code)}</span> · {tEnum("level", String(a.level))} · {String(a.title)}
          </Badge>
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ editor

type Draft = {
  slug: string;
  name: string;
  description: string;
  tags: Record<string, string[]>;
  free_tags: string;
  intensity_min: number;
  intensity_max: number;
  persona: string;
  trato: string;
  haz: string;
  evita: string;
  preferred_vocab: string;
  prohibited_vocab: string;
  length_min: number;
  length_max: number;
  emoji_usage: string;
  caps_usage: string;
  good_examples: string;
  bad_examples: string;
  visual_guide: string;
  palette: string;
  allowed_formats: string[];
  risk: string;
  requires_legal: boolean;
  change_note: string;
};

function toDraft(s?: Style): Draft {
  const len = (s?.length?.copy_principal ?? {}) as { min?: number; max?: number };
  return {
    slug: s?.slug ?? "",
    name: s?.name ?? "",
    description: s?.description ?? "",
    tags: s?.tags ?? {},
    free_tags: (s?.free_tags ?? []).join(", "),
    intensity_min: s?.intensity_min ?? 1,
    intensity_max: s?.intensity_max ?? 2,
    persona: String(s?.voice?.persona ?? "nosotros_institucional"),
    trato: String(s?.voice?.trato ?? "usted"),
    haz: (s?.guidelines?.haz ?? []).join("\n"),
    evita: (s?.guidelines?.evita ?? []).join("\n"),
    preferred_vocab: (s?.preferred_vocab ?? []).join(", "),
    prohibited_vocab: (s?.prohibited_vocab ?? []).join(", "),
    length_min: len.min ?? 120,
    length_max: len.max ?? 280,
    emoji_usage: s?.emoji_usage ?? "ninguno",
    caps_usage: s?.caps_usage ?? "normal",
    good_examples: (s?.good_examples ?? []).join("\n"),
    bad_examples: (s?.bad_examples ?? []).join("\n"),
    visual_guide: s?.visual_guide ?? "",
    palette: (s?.palette ?? []).join(", "),
    allowed_formats: s?.allowed_formats ?? [],
    risk: s?.risk ?? "bajo",
    requires_legal: s?.requires_legal ?? false,
    change_note: "",
  };
}

function fromDraft(d: Draft) {
  return {
    name: d.name,
    description: d.description,
    tags: d.tags,
    free_tags: commas(d.free_tags),
    intensity_min: Number(d.intensity_min),
    intensity_max: Number(d.intensity_max),
    voice: { persona: d.persona, trato: d.trato, idioma: "es-MX" },
    guidelines: { haz: lines(d.haz), evita: lines(d.evita) },
    preferred_vocab: commas(d.preferred_vocab),
    prohibited_vocab: commas(d.prohibited_vocab),
    length: { copy_principal: { min: Number(d.length_min), max: Number(d.length_max), unidad: "caracteres" } },
    emoji_usage: d.emoji_usage,
    caps_usage: d.caps_usage,
    good_examples: lines(d.good_examples),
    bad_examples: lines(d.bad_examples),
    visual_guide: d.visual_guide,
    palette: commas(d.palette),
    allowed_formats: d.allowed_formats,
    risk: d.risk,
    requires_legal: d.requires_legal,
  };
}

function StyleEditor({ open, onOpenChange, style, onSaved }: { open: boolean; onOpenChange: (o: boolean) => void; style?: Style; onSaved: (s: Style) => void }) {
  const { can } = useSession();
  const { data: dims } = useApi<Dim[]>("/tags");
  const { data: formats } = useApi<Schemas["FormatOut"][]>("/catalog/formats");
  const [d, setD] = useState<Draft>(toDraft(style));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const visualOnly = !can("style.edit") && can("style.visual_guide");
  useEffect(() => {
    if (open) {
      setD(toDraft(style));
      setError(null);
    }
  }, [open, style]);
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD((p) => ({ ...p, [k]: v }));
  const categorical = useMemo(() => (dims ?? []).filter((x) => x.kind === "categorical" && x.slug !== "riesgo"), [dims]);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const payload = visualOnly ? { visual_guide: d.visual_guide, palette: commas(d.palette) } : fromDraft(d);
      const saved = style
        ? await api.patch<Style>(`/styles/${style.id}`, { ...payload, change_note: d.change_note || null })
        : await api.post<Style>("/styles", { ...payload, slug: d.slug });
      await refresh("/styles");
      toast.success(t("common.saved"));
      onSaved(saved);
      onOpenChange(false);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  const field = (label: string, node: React.ReactNode, span = 2) => (
    <div className={cn("grid gap-1.5", span === 2 ? "col-span-2" : "col-span-1")}>
      <Label>{label}</Label>
      {node}
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{style ? `${t("styles.edit")} · ${style.name}` : t("styles.new")}</DialogTitle>
          {style?.status === "activo" ? <DialogDescription>{t("styles.editActiveHint")}</DialogDescription> : null}
        </DialogHeader>
        <div className="grid max-h-[65vh] grid-cols-2 gap-3 overflow-y-auto pr-1">
          {!visualOnly ? (
            <>
              {!style ? field(t("styles.fields.slug"), <Input value={d.slug} onChange={(e) => set("slug", e.target.value)} />, 1) : null}
              {field(t("styles.fields.name"), <Input value={d.name} onChange={(e) => set("name", e.target.value)} />, style ? 2 : 1)}
              {field(t("styles.fields.description"), <Input value={d.description} onChange={(e) => set("description", e.target.value)} />)}
              <div className="col-span-2 grid gap-2">
                <Label>{t("styles.fields.tags")}</Label>
                {categorical.map((dim) => (
                  <div key={dim.slug} className="flex flex-wrap items-center gap-1">
                    <span className="w-24 text-xs text-muted-foreground">{dim.name}</span>
                    {dim.tags.map((tag) => {
                      const on = (d.tags[dim.slug] ?? []).includes(tag.slug);
                      return (
                        <button
                          key={tag.slug}
                          type="button"
                          onClick={() => {
                            const cur = d.tags[dim.slug] ?? [];
                            set("tags", { ...d.tags, [dim.slug]: on ? cur.filter((x) => x !== tag.slug) : [...cur, tag.slug] });
                          }}
                          className={cn("rounded-full border px-2 py-0.5 text-xs", on ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted")}
                        >
                          {tag.name}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
              {field(t("styles.fields.freeTags"), <Input value={d.free_tags} onChange={(e) => set("free_tags", e.target.value)} />)}
              {field(t("styles.fields.intensityMin"), <Input type="number" min={1} max={5} value={d.intensity_min} onChange={(e) => set("intensity_min", Number(e.target.value))} />, 1)}
              {field(t("styles.fields.intensityMax"), <Input type="number" min={1} max={5} value={d.intensity_max} onChange={(e) => set("intensity_max", Number(e.target.value))} />, 1)}
              {field(
                t("styles.fields.persona"),
                <Select value={d.persona} onValueChange={(v) => set("persona", v)}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["nosotros_institucional", "primera_singular", "impersonal"].map((o) => <SelectItem key={o} value={o}>{t(`styles.options.${o}`)}</SelectItem>)}
                  </SelectContent>
                </Select>,
                1,
              )}
              {field(
                t("styles.fields.trato"),
                <Select value={d.trato} onValueChange={(v) => set("trato", v)}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["usted", "tu"].map((o) => <SelectItem key={o} value={o}>{t(`styles.options.${o}`)}</SelectItem>)}
                  </SelectContent>
                </Select>,
                1,
              )}
              {field(t("styles.fields.haz"), <Textarea rows={3} value={d.haz} onChange={(e) => set("haz", e.target.value)} />, 1)}
              {field(t("styles.fields.evita"), <Textarea rows={3} value={d.evita} onChange={(e) => set("evita", e.target.value)} />, 1)}
              {field(t("styles.fields.prohibited"), <Input value={d.prohibited_vocab} onChange={(e) => set("prohibited_vocab", e.target.value)} />, 1)}
              {field(t("styles.fields.preferred"), <Input value={d.preferred_vocab} onChange={(e) => set("preferred_vocab", e.target.value)} />, 1)}
              {field(t("styles.fields.lengthMin"), <Input type="number" value={d.length_min} onChange={(e) => set("length_min", Number(e.target.value))} />, 1)}
              {field(t("styles.fields.lengthMax"), <Input type="number" value={d.length_max} onChange={(e) => set("length_max", Number(e.target.value))} />, 1)}
              {field(
                t("styles.fields.emoji"),
                <Select value={d.emoji_usage} onValueChange={(v) => set("emoji_usage", v)}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>{["ninguno", "moderado"].map((o) => <SelectItem key={o} value={o}>{t(`styles.options.${o}`)}</SelectItem>)}</SelectContent>
                </Select>,
                1,
              )}
              {field(
                t("styles.fields.caps"),
                <Select value={d.caps_usage} onValueChange={(v) => set("caps_usage", v)}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>{["normal", "solo_rotulos"].map((o) => <SelectItem key={o} value={o}>{t(`styles.options.${o}`)}</SelectItem>)}</SelectContent>
                </Select>,
                1,
              )}
              {field(t("styles.fields.good"), <Textarea rows={2} value={d.good_examples} onChange={(e) => set("good_examples", e.target.value)} />, 1)}
              {field(t("styles.fields.bad"), <Textarea rows={2} value={d.bad_examples} onChange={(e) => set("bad_examples", e.target.value)} />, 1)}
            </>
          ) : null}
          {field(t("styles.fields.visualGuide"), <Textarea rows={3} value={d.visual_guide} onChange={(e) => set("visual_guide", e.target.value)} />)}
          <p className="col-span-2 -mt-2 text-xs text-muted-foreground">{t("styles.visualGuideHint")}</p>
          {field(t("styles.fields.palette"), <Input value={d.palette} onChange={(e) => set("palette", e.target.value)} />)}
          {!visualOnly ? (
            <>
              <div className="col-span-2 grid gap-1.5">
                <Label>{t("styles.fields.formats")}</Label>
                <div className="flex flex-wrap gap-3">
                  {(formats ?? []).map((f) => (
                    <label key={f.slug} className="flex items-center gap-1.5 text-sm">
                      <Checkbox
                        checked={d.allowed_formats.includes(f.slug)}
                        onCheckedChange={(c) => set("allowed_formats", c ? [...d.allowed_formats, f.slug] : d.allowed_formats.filter((x) => x !== f.slug))}
                      />
                      {f.code} · {f.name}
                    </label>
                  ))}
                </div>
              </div>
              {field(
                t("styles.fields.risk"),
                <Select value={d.risk} onValueChange={(v) => set("risk", v)}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>{["bajo", "medio", "alto"].map((o) => <SelectItem key={o} value={o}>{tEnum("risk", o)}</SelectItem>)}</SelectContent>
                </Select>,
                1,
              )}
              <label className="col-span-1 mt-6 flex items-center gap-2 text-sm">
                <Checkbox checked={d.requires_legal} onCheckedChange={(c) => set("requires_legal", Boolean(c))} />
                {t("styles.fields.requiresLegal")}
              </label>
            </>
          ) : null}
          {style ? field(t("styles.fields.changeNote"), <Input value={d.change_note} onChange={(e) => set("change_note", e.target.value)} />) : null}
        </div>
        {error ? <p className="text-sm text-status-block">{error}</p> : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t("common.cancel")}</Button>
          <Button onClick={save} disabled={busy || (!style && !d.slug) || !d.name}>{busy ? t("common.saving") : t("common.save")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CloneDialog({ open, onOpenChange, style, onSaved }: { open: boolean; onOpenChange: (o: boolean) => void; style: Style; onSaved: (s: Style) => void }) {
  const [slug, setSlug] = useState("");
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{style.is_base ? t("styles.clone") : t("styles.cloneAs")}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-1.5">
          <Label>{t("styles.newSlug")}</Label>
          <Input value={slug} placeholder={style.slug} onChange={(e) => setSlug(e.target.value)} />
        </div>
        <DialogFooter>
          <Button
            onClick={async () => {
              try {
                const q = slug ? `?new_slug=${encodeURIComponent(slug)}` : "";
                const s = await api.post<Style>(`/styles/${style.id}/clone${q}`);
                await refresh("/styles");
                onSaved(s);
                onOpenChange(false);
              } catch (err) {
                toast.error(errMsg(err));
              }
            }}
          >
            {t("styles.clone")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ImportDialog({ open, onOpenChange, onSaved }: { open: boolean; onOpenChange: (o: boolean) => void; onSaved: (s: Style) => void }) {
  const [text, setText] = useState("");
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("styles.importTitle")}</DialogTitle>
          <DialogDescription>{t("styles.importHelp")}</DialogDescription>
        </DialogHeader>
        <Textarea rows={12} className="font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} />
        <DialogFooter>
          <Button
            disabled={!text.trim()}
            onClick={async () => {
              try {
                const s = await api.post<Style>("/styles/import", JSON.parse(text));
                await refresh("/styles");
                onSaved(s);
                onOpenChange(false);
                setText("");
              } catch (err) {
                toast.error(errMsg(err));
              }
            }}
          >
            {t("common.import")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
