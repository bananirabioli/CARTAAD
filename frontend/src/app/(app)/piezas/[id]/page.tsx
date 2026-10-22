"use client";

import { ArrowLeft, ChevronLeft, ChevronRight, RefreshCw, Save } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState, Loading } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { RiskBreakdown, RiskMeter } from "@/components/cases/parts";
import { PieceActions } from "@/components/pieces/actions";
import {
  ConsentPanel,
  CopilotPanel,
  CopyText,
  errMsg,
  FiguresPanel,
  PieceLegalPanel,
  PieceStatusBadge,
  RedTeamPanel,
  ValidationBadge,
  ValidationFindings,
  VersionsPanel,
  type PieceD,
} from "@/components/pieces/parts";
import { AppliedList } from "@/components/styles/styles-tab";
import { FindingList, LintBadge } from "@/components/styles/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { enumOptions, t, tEnum } from "@/i18n";
import { API_BASE, api, fileUrl, refresh, useApi, type Schemas } from "@/lib/api/client";
import { useStateResetOn } from "@/lib/hooks";

type Seg = { text: string; type: string; fact_ids: number[] };
type Slot = { text: string; fact_ids: number[] };
type Slide = { title: string; text: string; fact_ids: number[] };
const NONE = "__none__";

function Preview({ piece }: { piece: PieceD }) {
  const [i, setI] = useState(0);
  const [live, setLive] = useState(false);
  const n = piece.renders.length;
  if (piece.kind === "copy") return <div className="rounded-md border bg-card p-4"><CopyText piece={piece} facts={piece.facts ?? []} /></div>;
  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between text-xs">
        <Badge variant="outline">{tEnum("render_status", piece.render_status)}</Badge>
        <Button size="xs" variant="ghost" onClick={() => setLive(!live)}>{live ? t("editor.renders") : t("editor.livePreview")}</Button>
      </div>
      {live ? (
        <iframe title="preview" src={`${API_BASE}/pieces/${piece.id}/preview?slide=${i}&v=${piece.current_version}`} className="aspect-[4/5] w-full rounded-md border bg-white" style={{ zoom: 1 }} />
      ) : n ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={fileUrl(piece.renders[Math.min(i, n - 1)])} alt="" className="w-full rounded-md border" />
      ) : piece.render_status === "no_aplica" ? (
        <div className="grid gap-2 rounded-md border bg-muted/30 p-3 text-sm">{((piece.content.slides as Slide[]) ?? []).map((s, k) => <p key={k}><b>{s.title}:</b> {s.text}</p>)}</div>
      ) : <Loading />}
      {n > 1 ? (
        <div className="flex items-center justify-center gap-3 text-xs">
          <Button size="icon-xs" variant="outline" disabled={i === 0} onClick={() => setI(i - 1)}><ChevronLeft /></Button>
          {i + 1} / {n}
          <Button size="icon-xs" variant="outline" disabled={i >= n - 1} onClick={() => setI(i + 1)}><ChevronRight /></Button>
        </div>
      ) : null}
    </div>
  );
}

function ContentEditor({ piece, onChange }: { piece: PieceD; onChange: (p: PieceD) => void }) {
  const { can } = useSession();
  const [segments, setSegments] = useStateResetOn<Seg[]>(piece.content, () => ((piece.content.segments as Seg[]) ?? []).map((s) => ({ ...s })));
  const [slots, setSlots] = useStateResetOn<Record<string, Slot>>(piece.content, () => ({ ...((piece.content.slots as Record<string, Slot>) ?? {}) }));
  const [slides, setSlides] = useStateResetOn<Slide[]>(piece.content, () => ((piece.content.slides as Slide[]) ?? []).map((s) => ({ ...s })));
  const [images, setImages] = useStateResetOn<Record<string, unknown>[]>(piece.content, () => ((piece.content.images as Record<string, unknown>[]) ?? []).map((x) => ({ ...x })));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const { data: bank } = useApi<Schemas["ImageOut"][]>(piece.kind === "creative" ? "/kb/images?image_type=foto_real" : null);
  const editable = can("piece.edit") && !["programado", "publicado", "descartado"].includes(piece.status);
  const realIdx = images.findIndex((x) => x.approved_image_id);

  async function save() {
    setBusy(true);
    try {
      const body = piece.kind === "copy" ? { segments, note } : { slots, slides, images, note };
      onChange(await api.put<PieceD>(`/pieces/${piece.id}/content`, body));
      setNote("");
      await refresh("/proposals", "/cases", "/inbox");
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  const ids = (v: string) => v.split(",").map((x) => Number(x.trim())).filter((x) => Number.isFinite(x) && x > 0);
  return (
    <div className="grid grid-cols-1 gap-3">
      {piece.kind === "copy" ? (
        segments.map((s, i) => (
          <div key={i} className="grid grid-cols-1 gap-1.5 rounded-md border p-2">
            <Textarea rows={2} value={s.text} disabled={!editable} onChange={(e) => setSegments(segments.map((x, k) => (k === i ? { ...x, text: e.target.value } : x)))} />
            <div className="grid grid-cols-2 gap-2">
              <Select value={s.type} disabled={!editable} onValueChange={(v) => setSegments(segments.map((x, k) => (k === i ? { ...x, type: v } : x)))}>
                <SelectTrigger size="sm" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>{enumOptions("segment_type").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
              </Select>
              <Input className="h-7 text-xs" placeholder={t("editor.segmentFacts")} disabled={!editable} value={s.fact_ids.join(", ")} onChange={(e) => setSegments(segments.map((x, k) => (k === i ? { ...x, fact_ids: ids(e.target.value) } : x)))} />
            </div>
          </div>
        ))
      ) : (
        <>
          {Object.entries(slots).map(([name, slot]) => (
            <div key={name} className="grid grid-cols-1 gap-1">
              <Label className="text-xs">{name}{slot.fact_ids.length ? ` · hechos ${slot.fact_ids.join(", ")}` : ""}</Label>
              <Textarea rows={2} value={slot.text} disabled={!editable} onChange={(e) => setSlots({ ...slots, [name]: { ...slot, text: e.target.value } })} />
            </div>
          ))}
          {slides.length ? <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("editor.slides")}</p> : null}
          {slides.map((s, i) => (
            <div key={i} className="grid grid-cols-1 gap-1 rounded-md border p-2">
              <Input className="h-7 text-xs font-medium" value={s.title} disabled={!editable} onChange={(e) => setSlides(slides.map((x, k) => (k === i ? { ...x, title: e.target.value } : x)))} />
              <Textarea rows={2} value={s.text} disabled={!editable} onChange={(e) => setSlides(slides.map((x, k) => (k === i ? { ...x, text: e.target.value } : x)))} />
            </div>
          ))}
          {realIdx >= 0 && bank ? (
            <div className="grid gap-1">
              <Label className="text-xs">{t("editor.changeImage")}</Label>
              <Select value={String(images[realIdx].approved_image_id ?? NONE)} disabled={!editable} onValueChange={(v) => setImages(images.map((x, k) => (k === realIdx ? { approved_image_id: Number(v) } : x)))}>
                <SelectTrigger size="sm" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>{bank.map((b) => <SelectItem key={b.id} value={String(b.id)}>{b.title}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          ) : null}
        </>
      )}
      {editable ? (
        <div className="grid gap-2">
          <Input placeholder={t("editor.editNote")} value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex gap-2">
            <Button size="sm" onClick={save} disabled={busy}><Save />{t("editor.saveVersion")}</Button>
            {piece.kind === "creative" ? (
              <Button size="sm" variant="outline" onClick={async () => onChange(await api.post<PieceD>(`/pieces/${piece.id}/rerender`))}><RefreshCw />{t("editor.rerender")}</Button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function PieceEditorPage() {
  const params = useParams<{ id: string }>();
  const { data: piece, error, mutate } = useApi<PieceD>(`/pieces/${params.id}`, {
    refreshInterval: (p) => (p?.render_status === "pendiente" ? 2000 : 0),
  });
  if (error) return <ErrorState error={error} />;
  if (!piece) return <Loading />;
  const set = (p: PieceD) => mutate(p, { revalidate: false });
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <Link href={`/casos/${piece.case_id}/generacion`} className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"><ArrowLeft className="size-3" />{piece.case_code}</Link>
          <h1 className="flex flex-wrap items-center gap-2 text-xl font-semibold">
            {piece.kind === "copy" ? `${t("generation.copyVariants")} · ${piece.style_slug}` : tEnum("creative", piece.creative_slug)}
            <span className="font-mono text-sm text-muted-foreground">v{piece.current_version}</span>
          </h1>
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <PieceStatusBadge status={piece.status} />
            <ValidationBadge status={piece.validation_status} />
            {piece.compliance?.status ? <LintBadge status={String(piece.compliance.status)} /> : null}
            <Badge variant="outline">{tEnum("format", piece.format_slug)}</Badge>
            <Badge variant="outline">{piece.style_slug} v{piece.style_version}</Badge>
            <Badge variant="outline">{tEnum("strategy", piece.strategy)}</Badge>
            {piece.account_handle ? <Badge variant="outline">{piece.account_handle}</Badge> : null}
          </div>
        </div>
        <PieceActions piece={piece} onChange={set} />
      </div>
      {piece.approval_blockers?.length && ["generado", "bloqueado"].includes(piece.status) ? (
        <div className="rounded-md border border-status-warn/50 bg-status-warn/5 p-3 text-xs">
          <p className="mb-1 font-medium">{t("editor.approvalBlockers")}</p>
          <ul className="list-disc pl-4">{piece.approval_blockers.map((b) => <li key={b}>{b}</li>)}</ul>
        </div>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)_minmax(0,400px)] [&>*]:min-w-0">
        <Card className="gap-3 py-4"><CardHeader className="px-4"><CardTitle className="text-sm">{t("editor.preview")}</CardTitle></CardHeader><CardContent className="px-4"><Preview piece={piece} /></CardContent></Card>
        <div className="grid grid-cols-1 content-start gap-4">
          <Card className="gap-3 py-4">
            <CardHeader className="px-4"><CardTitle className="text-sm">{piece.kind === "copy" ? t("editor.segments") : t("editor.slots")}</CardTitle></CardHeader>
            <CardContent className="px-4"><ContentEditor piece={piece} onChange={set} /></CardContent>
          </Card>
          <Card className="gap-3 py-4">
            <CardContent className="grid grid-cols-1 gap-3 px-4 text-xs">
              <p><span className="font-medium">{t("generation.why")}: </span>{piece.why}</p>
              {piece.adaptation ? <p><span className="font-medium">{t("generation.adaptation")}: </span>{piece.adaptation}</p> : null}
              {piece.missing_inputs.length ? <p className="text-status-warn">{t("generation.missingInputs")}: {piece.missing_inputs.join(" ")}</p> : null}
              <AppliedList applied={piece.applied_directives} />
              <div className="flex flex-wrap gap-1">{piece.effective_tags.map((tag) => <Badge key={tag} variant="outline" className="font-normal">{tag}</Badge>)}</div>
              {((piece.content.sources as string[]) ?? []).length ? (
                <div className="grid gap-0.5"><p className="font-medium">{t("generation.sources")}</p>{(piece.content.sources as string[]).map((s) => <p key={s} className="text-muted-foreground">{s}</p>)}</div>
              ) : null}
            </CardContent>
          </Card>
        </div>
        <Card className="gap-3 py-4">
          <CardContent className="px-4">
            <Tabs defaultValue="copilot">
              <TabsList className="h-auto flex-wrap">
                <TabsTrigger value="copilot">{t("editor.copilotTitle")}</TabsTrigger>
                <TabsTrigger value="checks">{t("editor.validation")}</TabsTrigger>
                <TabsTrigger value="figures">{t("editor.figures")}</TabsTrigger>
                <TabsTrigger value="versions">{t("editor.versions")}</TabsTrigger>
              </TabsList>
              <TabsContent value="copilot" className="mt-3"><CopilotPanel piece={piece} onChange={set} /></TabsContent>
              <TabsContent value="checks" className="mt-3 grid gap-4">
                <section className="grid gap-1"><p className="text-xs font-medium">{t("editor.validation")}</p><ValidationFindings piece={piece} /></section>
                <section className="grid gap-1"><p className="text-xs font-medium">{t("editor.compliance")}</p><FindingList findings={((piece.compliance?.findings as never[]) ?? [])} /></section>
                <section className="grid gap-1"><p className="text-xs font-medium">{t("editor.redTeam")}</p><RedTeamPanel notes={piece.red_team_notes ?? []} /></section>
                <section className="grid gap-2"><div className="flex items-center justify-between"><p className="text-xs font-medium">{t("cases.riskBreakdown")}</p><RiskMeter score={piece.risk_score} /></div><RiskBreakdown items={piece.risk_breakdown} /></section>
                {piece.legal_required ? <section className="grid gap-1"><p className="text-xs font-medium">{t("editor.legal")}</p><PieceLegalPanel piece={piece} onChange={set} /></section> : null}
                {piece.creative_slug === "voz_ciudadana" ? <section className="grid gap-1"><p className="text-xs font-medium">{t("editor.consent")}</p><ConsentPanel piece={piece} onChange={set} /></section> : null}
              </TabsContent>
              <TabsContent value="figures" className="mt-3"><FiguresPanel piece={piece} onChange={set} /></TabsContent>
              <TabsContent value="versions" className="mt-3"><VersionsPanel piece={piece} onChange={set} /></TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
