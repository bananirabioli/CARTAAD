"use client";

import { ArrowLeft, Check, Copy, Download, Film, ImageIcon, Loader2, PenLine, Sparkles, Wand2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState, Loading, PageHeader } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { RiskMeter } from "@/components/cases/parts";
import { CopilotPanel, CopyText, CreativeThumb, errMsg, FiguresPanel, PieceStatusBadge, ValidationBadge, ValidationFindings, VersionsPanel, type PieceD, type PieceS } from "@/components/pieces/parts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { enumOptions, fmtDate, t, tEnum } from "@/i18n";
import { api, fileUrl, refresh, useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Proposal = Schemas["ProposalOut"];
type CaseD = Schemas["CaseDetail"];

const NETWORKS = ["facebook", "instagram", "x", "tiktok", "youtube", "whatsapp"] as const;
const BUSY_RENDER = ["pendiente", "generando"];

function PieceMeta({ p }: { p: PieceS }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <PieceStatusBadge status={p.status} />
      {p.kind === "copy" ? <ValidationBadge status={p.validation_status} /> : null}
      {p.legal_required ? <Badge variant="outline" className="border-veda/50 text-veda">{t("cases.legal")}: {tEnum("legal_status", p.legal_status)}</Badge> : null}
      {p.figures_total ? <Badge variant="outline">{t("generation.figures", { verified: p.figures_verified ?? 0, total: p.figures_total ?? 0 })}</Badge> : null}
      {p.kind === "copy" ? <span className="ml-auto flex items-center gap-1 text-muted-foreground">{t("generation.risk")} <RiskMeter score={p.risk_score} /></span> : null}
    </div>
  );
}

function copyPlainText(p: PieceS): string {
  const c = p.content as { segments?: { text: string }[]; legends?: string[]; sources?: string[]; hashtags?: string[]; cta?: string };
  const body = (c.segments ?? []).map((s) => s.text.trim()).join(" ");
  const parts = [body, c.cta ?? "", (c.hashtags ?? []).join(" "), ...(c.legends ?? [])];
  if (c.sources?.length) parts.push(`Fuentes: ${c.sources.join("; ")}`);
  return parts.filter(Boolean).join("\n\n");
}

function ApproveButton({ p, onDone }: { p: PieceS; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  if (p.status === "aprobado") return <Badge className="border-transparent bg-status-ok/15 text-status-ok"><Check className="size-3" />{tEnum("piece_status", "aprobado")}</Badge>;
  if (!["generado", "bloqueado"].includes(p.status)) return null;
  return (
    <Button
      size="sm"
      disabled={busy || BUSY_RENDER.includes(p.render_status)}
      title={p.approval_blockers?.join("\n")}
      onClick={async () => {
        setBusy(true);
        try {
          await api.post(`/pieces/${p.id}/approve`, { note: "" });
          toast.success(t("mvp.approved"));
          onDone();
        } catch (err) {
          toast.error(errMsg(err));
        } finally {
          setBusy(false);
        }
      }}
    >
      <Check />{t("mvp.approve")}
    </Button>
  );
}

function CopilotSheet({ pieceId, onClose }: { pieceId: number | null; onClose: () => void }) {
  const { data, mutate } = useApi<PieceD>(pieceId ? `/pieces/${pieceId}` : null);
  const set = (p: PieceD) => mutate(p, { revalidate: false });
  return (
    <Sheet open={pieceId !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        {!data ? <Loading className="p-6" /> : (
          <>
            <SheetHeader>
              <SheetTitle className="flex flex-wrap items-center gap-2">
                <Wand2 className="size-4" /> {t("generation.copilot")} · {data.style_slug}
                <span className="font-mono text-xs text-muted-foreground">v{data.current_version}</span>
              </SheetTitle>
            </SheetHeader>
            <div className="grid gap-5 px-4 pb-8">
              <PieceMeta p={data} />
              <div className="rounded-md border bg-card p-3"><CopyText piece={data} facts={data.facts ?? []} /></div>
              <section className="grid gap-2"><h3 className="text-sm font-medium">{t("editor.copilotTitle")}</h3><CopilotPanel piece={data} onChange={set} /></section>
              <section className="grid gap-2"><h3 className="text-sm font-medium">{t("editor.validation")}</h3><ValidationFindings piece={data} /></section>
              <section className="grid gap-2"><h3 className="text-sm font-medium">{t("editor.figures")}</h3><FiguresPanel piece={data} onChange={set} /></section>
              <section className="grid gap-2"><h3 className="text-sm font-medium">{t("editor.versions")}</h3><VersionsPanel piece={data} onChange={set} /></section>
              <Button asChild variant="outline" className="w-fit"><Link href={`/piezas/${data.id}`}><PenLine />{t("generation.openEditor")}</Link></Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function GenerateForm({ c, proposal, onStarted }: { c: CaseD; proposal: Proposal | undefined; onStarted: () => Promise<unknown> }) {
  const styles = c.account_options?.[0]?.allowed_styles ?? [];
  const strategies = c.strategy_candidates?.length ? c.strategy_candidates : enumOptions("strategy").map((o) => o.value);
  const opts = (proposal?.options ?? {}) as { network?: string; image_count?: number; video?: boolean; instructions?: string };
  const [strategy, setStrategy] = useState(c.strategy ?? c.strategy_suggested ?? strategies[0] ?? "contextualizar");
  const [variants, setVariants] = useState<string[]>(proposal?.variant_styles ?? []);
  const [network, setNetwork] = useState<string>(opts.network ?? "facebook");
  const [images, setImages] = useState<string>(String(opts.image_count ?? 1));
  const [video, setVideo] = useState<boolean>(opts.video ?? false);
  const [instructions, setInstructions] = useState(opts.instructions ?? "");
  const [legalNote, setLegalNote] = useState("");
  const [busy, setBusy] = useState(false);
  const legalPending = c.legal_required && c.legal_status !== "liberada";

  async function generate() {
    setBusy(true);
    try {
      if (legalPending) await api.post(`/cases/${c.id}/legal`, { action: "liberar", note: legalNote });
      await api.post(`/cases/${c.id}/generate-content`, {
        strategy, variant_styles: variants.length ? variants : null, network, image_count: Number(images), video, instructions,
      });
      await onStarted();
      await refresh("/cases", "/dashboard");
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="gap-3 py-4">
      <CardContent className="grid gap-4 px-4">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="grid gap-1.5">
            <Label>{t("generation.strategy")}</Label>
            <Select value={strategy} onValueChange={setStrategy}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {strategies.map((s) => <SelectItem key={s} value={s}>{tEnum("strategy", s)}{s === c.strategy_suggested ? ` · ${t("cases.recommendedTag")}` : ""}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label>{t("mvp.network")}</Label>
            <Select value={network} onValueChange={setNetwork}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{NETWORKS.map((n) => <SelectItem key={n} value={n}>{tEnum("network", n)}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label>{t("mvp.images")}</Label>
            <Select value={images} onValueChange={setImages}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{["0", "1", "2"].map((n) => <SelectItem key={n} value={n}>{n}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        {styles.length ? (
          <div className="grid gap-1.5">
            <Label>{t("generation.variants")}</Label>
            <div className="flex flex-wrap gap-1.5">
              {styles.map((s) => {
                const on = variants.includes(s);
                return (
                  <button key={s} type="button" onClick={() => setVariants(on ? variants.filter((x) => x !== s) : [...variants, s].slice(0, 3))}
                    className={cn("rounded-full border px-2.5 py-1 text-xs", on ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted")}>
                    {s}
                  </button>
                );
              })}
            </div>
            <p className="text-[11px] text-muted-foreground">{t("mvp.variantsHelp")}</p>
          </div>
        ) : null}
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={video} onCheckedChange={(v) => setVideo(v === true)} />
          {t("mvp.video")}
          <span className="text-xs text-muted-foreground">{t("mvp.videoHelp")}</span>
        </label>
        <div className="grid gap-1.5">
          <Label htmlFor="instr">{t("mvp.instructions")}</Label>
          <Textarea id="instr" rows={2} value={instructions} onChange={(e) => setInstructions(e.target.value)} placeholder={t("mvp.instructionsPlaceholder")} />
        </div>
        {legalPending ? (
          <div className="grid gap-1.5 rounded-md border border-veda/40 bg-veda/5 p-3">
            <Label htmlFor="legal">{t("mvp.legalCheck")}</Label>
            <Textarea id="legal" rows={2} value={legalNote} onChange={(e) => setLegalNote(e.target.value)} placeholder={t("mvp.legalPlaceholder")} />
          </div>
        ) : null}
        <div>
          <Button onClick={generate} disabled={busy || proposal?.status === "generando" || (legalPending && legalNote.trim().length < 3)}>
            {busy || proposal?.status === "generando" ? <Loader2 className="animate-spin" /> : <Sparkles />}
            {proposal ? t("generation.regenerate") : t("generation.generate")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ImageCard({ p, onDone }: { p: PieceS; onDone: () => void }) {
  const c = p.content as { concept?: string; prompt?: string; headline?: string; aspect_ratio?: string };
  return (
    <Card className="gap-2 overflow-hidden py-0">
      <CreativeThumb piece={p} className="aspect-[4/5] w-full rounded-none border-0 border-b object-contain" />
      <CardContent className="grid grid-cols-1 gap-2 p-3 text-xs">
        <PieceMeta p={p} />
        <p className="text-sm font-medium">{c.concept}</p>
        {c.headline ? <p><span className="text-muted-foreground">{t("mvp.headline")}: </span>{c.headline}</p> : null}
        {p.render_error ? <p className="text-status-block">{p.render_error}</p> : null}
        <details>
          <summary className="cursor-pointer text-muted-foreground">{t("mvp.prompt")}</summary>
          <p className="mt-1 rounded bg-muted p-2 font-mono text-[11px]">{c.prompt}</p>
        </details>
        <div className="flex flex-wrap gap-2">
          {p.renders[0] ? <Button size="sm" variant="outline" asChild><a href={fileUrl(p.renders[0])} download><Download />{t("mvp.download")}</a></Button> : null}
          <ApproveButton p={p} onDone={onDone} />
        </div>
      </CardContent>
    </Card>
  );
}

function VideoCard({ p, onDone }: { p: PieceS; onDone: () => void }) {
  const c = p.content as { concept?: string; prompt?: string; voiceover?: string; on_screen_text?: string[]; scenes?: { seconds: number; visual: string; voiceover: string }[]; seconds?: number };
  return (
    <Card className="gap-3 py-4">
      <CardHeader className="px-4"><CardTitle className="flex items-center gap-2 text-sm"><Film className="size-4" />{c.concept}</CardTitle></CardHeader>
      <CardContent className="grid gap-4 px-4 md:grid-cols-[280px_minmax(0,1fr)]">
        <div className="grid content-start gap-2">
          {p.render_status === "listo" && p.renders[0] ? (
            <video src={fileUrl(p.renders[0])} controls className="aspect-[9/16] w-full rounded-md border bg-black" />
          ) : BUSY_RENDER.includes(p.render_status) ? (
            <div className="flex aspect-[9/16] flex-col items-center justify-center gap-2 rounded-md border bg-muted text-xs text-muted-foreground"><Loader2 className="size-5 animate-spin" />{t("mvp.videoRendering")}</div>
          ) : (
            <div className="flex aspect-[9/16] items-center justify-center rounded-md border bg-muted p-3 text-center text-xs text-muted-foreground">{p.render_error || t("mvp.videoNone")}</div>
          )}
          <div className="flex flex-wrap gap-2">
            {p.renders[0] ? <Button size="sm" variant="outline" asChild><a href={fileUrl(p.renders[0])} download><Download />{t("mvp.download")}</a></Button> : null}
            <ApproveButton p={p} onDone={onDone} />
          </div>
        </div>
        <div className="grid content-start gap-3 text-sm">
          {c.scenes?.length ? (
            <div className="grid gap-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("mvp.scenes")}</p>
              {c.scenes.map((s, i) => <p key={i} className="text-xs"><Badge variant="outline" className="mr-1">{s.seconds}s</Badge>{s.visual}{s.voiceover ? <span className="text-muted-foreground"> — «{s.voiceover}»</span> : null}</p>)}
            </div>
          ) : null}
          {c.voiceover ? <div className="grid gap-1"><p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("mvp.voiceover")}</p><p>{c.voiceover}</p></div> : null}
          {c.on_screen_text?.length ? <div className="grid gap-1"><p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("mvp.onScreen")}</p><ul className="list-disc pl-4 text-xs">{c.on_screen_text.map((x) => <li key={x}>{x}</li>)}</ul></div> : null}
          <div className="grid gap-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("mvp.prompt")}</p>
            <p className="rounded bg-muted p-2 font-mono text-[11px]">{c.prompt}</p>
            <Button size="xs" variant="ghost" className="w-fit" onClick={() => { void navigator.clipboard.writeText(c.prompt ?? ""); toast.success(t("mvp.copied")); }}><Copy />{t("mvp.copyPrompt")}</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function GenerationPage() {
  const params = useParams<{ id: string }>();
  const { can } = useSession();
  const { data: c, error, mutate: mutateCase } = useApi<CaseD>(`/cases/${params.id}`);
  const { data: proposals, mutate } = useApi<Proposal[]>(`/cases/${params.id}/proposals`, {
    refreshInterval: (latest) => (latest?.[0]?.status === "generando" || latest?.[0]?.pieces?.some((p) => BUSY_RENDER.includes(p.render_status)) ? 3000 : 0),
  });
  const [copilotId, setCopilotId] = useState<number | null>(null);

  if (error) return <ErrorState error={error} />;
  if (!c) return <Loading />;
  const proposal = proposals?.[0];
  const pieces = proposal?.pieces ?? [];
  const copies = pieces.filter((p) => p.kind === "copy");
  const images = pieces.filter((p) => p.kind === "image" || p.kind === "creative");
  const videos = pieces.filter((p) => p.kind === "video");
  const reload = () => { void mutate(); void mutateCase(); };

  return (
    <div className="grid gap-5">
      <div>
        <Link href={`/casos/${c.id}`} className="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"><ArrowLeft className="size-3" />{c.code}</Link>
        <PageHeader title={`${t("generation.title")} · ${c.code}`} subtitle={t("mvp.generateSubtitle")} />
      </div>
      {can("generation.run") ? <GenerateForm key={proposal?.id ?? 0} c={c} proposal={proposal} onStarted={() => Promise.all([mutate(), mutateCase()])} /> : null}

      {!proposal ? <p className="text-sm text-muted-foreground">{t("generation.noProposal")}</p> : proposal.status === "generando" ? (
        <div className="flex items-center gap-2 text-sm"><Loader2 className="size-4 animate-spin" />{t("mvp.generating")}</div>
      ) : proposal.status === "error" ? (
        <p className="text-sm text-status-block">{t("generation.error", { error: proposal.error })}</p>
      ) : (
        <Tabs defaultValue="copy">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <TabsList>
              <TabsTrigger value="copy">{t("generation.copyVariants")} ({copies.length})</TabsTrigger>
              <TabsTrigger value="images"><ImageIcon className="size-3.5" />{t("mvp.imagesTab")} ({images.length})</TabsTrigger>
              <TabsTrigger value="video"><Film className="size-3.5" />{t("mvp.videoTab")} ({videos.length})</TabsTrigger>
            </TabsList>
            <span className="text-xs text-muted-foreground">{t("generation.proposalOf", { id: proposal.id, date: fmtDate(proposal.created_at) })}</span>
          </div>
          <TabsContent value="copy" className="mt-3">
            <div className="grid gap-4 xl:grid-cols-3 [&>*]:min-w-0">
              {copies.map((p) => {
                const content = p.content as { hashtags?: string[]; cta?: string; missing_data?: string[] };
                return (
                  <Card key={p.id} className="gap-3 py-4">
                    <CardHeader className="grid-cols-1 gap-2 px-4">
                      <CardTitle className="text-sm">{p.style_slug} <span className="font-mono text-xs font-normal text-muted-foreground">· {tEnum("strategy", p.strategy)}</span></CardTitle>
                      <PieceMeta p={p} />
                    </CardHeader>
                    <CardContent className="grid grid-cols-1 gap-3 px-4">
                      <CopyText piece={p} facts={proposal.facts ?? []} />
                      {content.cta ? <p className="text-sm font-medium">{content.cta}</p> : null}
                      {content.hashtags?.length ? <p className="text-xs text-primary">{content.hashtags.join(" ")}</p> : null}
                      <p className="text-xs text-muted-foreground"><span className="font-medium text-foreground">{t("generation.why")}: </span>{p.why}</p>
                      {content.missing_data?.length ? <p className="text-xs text-status-warn">{t("mvp.missingData")}: {content.missing_data.join("; ")}</p> : null}
                      {p.validation.length ? <ValidationFindings piece={p} /> : null}
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" onClick={() => { void navigator.clipboard.writeText(copyPlainText(p)); toast.success(t("mvp.copied")); }}><Copy />{t("mvp.copy")}</Button>
                        <Button size="sm" variant="outline" onClick={() => setCopilotId(p.id)}><Wand2 />{t("generation.copilot")}</Button>
                        <ApproveButton p={p} onDone={reload} />
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </TabsContent>
          <TabsContent value="images" className="mt-3">
            {images.length ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 [&>*]:min-w-0">{images.map((p) => <ImageCard key={p.id} p={p} onDone={reload} />)}</div>
            ) : <p className="text-sm text-muted-foreground">{t("mvp.noImages")}</p>}
          </TabsContent>
          <TabsContent value="video" className="mt-3 grid gap-4">
            {videos.length ? videos.map((p) => <VideoCard key={p.id} p={p} onDone={reload} />) : <p className="text-sm text-muted-foreground">{t("mvp.noVideo")}</p>}
          </TabsContent>
        </Tabs>
      )}
      <CopilotSheet pieceId={copilotId} onClose={() => { setCopilotId(null); void mutate(); }} />
    </div>
  );
}
