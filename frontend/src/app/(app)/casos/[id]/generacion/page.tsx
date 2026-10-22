"use client";

import { ArrowLeft, Ban, Loader2, PenLine, Sparkles, Wand2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState, Loading, PageHeader } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { RiskMeter } from "@/components/cases/parts";
import { CopilotPanel, CopyText, CreativeThumb, errMsg, FiguresPanel, PieceStatusBadge, ValidationBadge, ValidationFindings, VersionsPanel, type PieceD, type PieceS } from "@/components/pieces/parts";
import { AppliedList } from "@/components/styles/styles-tab";
import { LintBadge, TagChips } from "@/components/styles/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { fmtDate, t, tEnum } from "@/i18n";
import { api, refresh, useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Proposal = Schemas["ProposalOut"];

function PieceMeta({ p }: { p: PieceS }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <PieceStatusBadge status={p.status} />
      <ValidationBadge status={p.validation_status} />
      {p.compliance?.status ? <LintBadge status={String(p.compliance.status)} /> : null}
      {p.legal_required ? <Badge variant="outline" className="border-veda/50 text-veda">{t("cases.legal")}: {tEnum("legal_status", p.legal_status)}</Badge> : null}
      <Badge variant="outline">{t("generation.figures", { verified: p.figures_verified ?? 0, total: p.figures_total ?? 0 })}</Badge>
      <span className="ml-auto flex items-center gap-1 text-muted-foreground">{t("generation.risk")} <RiskMeter score={p.risk_score} /></span>
    </div>
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
                <Wand2 className="size-4" /> {t("generation.copilot")} · {data.kind === "copy" ? data.style_slug : tEnum("creative", data.creative_slug)}
                <span className="font-mono text-xs text-muted-foreground">v{data.current_version}</span>
              </SheetTitle>
            </SheetHeader>
            <div className="grid gap-5 px-4 pb-8">
              <PieceMeta p={data} />
              {data.kind === "copy" ? <div className="rounded-md border bg-card p-3"><CopyText piece={data} facts={data.facts ?? []} /></div> : <CreativeThumb piece={data} className="aspect-[4/5] w-full" />}
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

export default function GenerationPage() {
  const params = useParams<{ id: string }>();
  const { can } = useSession();
  const { data: c, error, mutate: mutateCase } = useApi<Schemas["CaseDetail"]>(`/cases/${params.id}`);
  const { data: proposals, mutate } = useApi<Proposal[]>(`/cases/${params.id}/proposals`, {
    refreshInterval: (latest) => (latest?.[0]?.status === "generando" || latest?.[0]?.pieces?.some((p) => p.render_status === "pendiente") ? 2000 : 0),
  });
  const [variants, setVariants] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [copilotId, setCopilotId] = useState<number | null>(null);

  if (error) return <ErrorState error={error} />;
  if (!c) return <Loading />;
  const account = c.account_options?.find((a) => a.id === c.account_id);
  const proposal = proposals?.[0];
  const copies = proposal?.pieces.filter((p) => p.kind === "copy") ?? [];
  const creatives = proposal?.pieces.filter((p) => p.kind === "creative") ?? [];
  const canGenerate = can("generation.run") && ["listo_para_generar", "generado", "en_revision"].includes(c.status);

  async function generate() {
    setBusy(true);
    try {
      await api.post(`/cases/${c!.id}/generate`, { variant_styles: variants.length ? variants : null });
      await Promise.all([mutate(), mutateCase(), refresh("/inbox", "/dashboard")]);
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-5">
      <div>
        <Link href={`/casos/${c.id}`} className="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"><ArrowLeft className="size-3" />{c.code}</Link>
        <PageHeader title={`${t("generation.title")} · ${c.code}`} subtitle={t("generation.subtitle")} />
      </div>
      <Card className="gap-3 py-4">
        <CardContent className="grid gap-4 px-4 md:grid-cols-[minmax(0,1fr)_auto]">
          <div className="grid gap-3">
            <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
              <span><span className="text-muted-foreground">{t("generation.target")}: </span>{account?.display_name ?? "—"}</span>
              <span><span className="text-muted-foreground">{t("generation.format")}: </span>{account?.format_name ?? "—"}</span>
              <span><span className="text-muted-foreground">{t("generation.strategy")}: </span>{tEnum("strategy", c.strategy ?? "")}</span>
              <span><span className="text-muted-foreground">{t("generation.chosenStyle")}: </span>{c.style_slug} <span className="text-xs text-muted-foreground">({String(c.style_choice?.reason ?? "")})</span></span>
            </div>
            {c.recommended_style?.value ? <p className="text-xs text-muted-foreground">{t("generation.recommendedStyle", { style: String(c.recommended_style.value), reason: String(c.recommended_style.reason) })}</p> : null}
            {account ? (
              <div className="grid gap-1.5">
                <p className="text-xs font-medium">{t("generation.variants")}</p>
                <div className="flex flex-wrap gap-1.5">
                  {account.allowed_styles.map((s) => {
                    const on = variants.includes(s);
                    return (
                      <button key={s} type="button" onClick={() => setVariants(on ? variants.filter((x) => x !== s) : [...variants, s].slice(0, 4))}
                        className={cn("rounded-full border px-2.5 py-1 text-xs", on ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted")}>
                        {s}{s === c.recommended_style?.value ? ` · ${t("cases.recommendedTag")}` : ""}
                      </button>
                    );
                  })}
                </div>
                <p className="text-[11px] text-muted-foreground">{t("generation.variantsHelp")}</p>
              </div>
            ) : null}
          </div>
          <div className="flex items-start">
            {canGenerate ? (
              <Button onClick={generate} disabled={busy || proposal?.status === "generando"}>
                {busy || proposal?.status === "generando" ? <Loader2 className="animate-spin" /> : <Sparkles />}
                {proposal ? t("generation.regenerate") : t("generation.generate")}
              </Button>
            ) : !proposal ? <p className="max-w-xs text-xs text-muted-foreground">{t("generation.notReady")}</p> : null}
          </div>
        </CardContent>
      </Card>

      {!proposal ? <p className="text-sm text-muted-foreground">{t("generation.noProposal")}</p> : proposal.status === "generando" ? (
        <div className="flex items-center gap-2 text-sm"><Loader2 className="size-4 animate-spin" />{t("generation.generating")}</div>
      ) : proposal.status === "error" ? (
        <p className="text-sm text-status-block">{t("generation.error", { error: proposal.error })}</p>
      ) : (
        <Tabs defaultValue="copy">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <TabsList>
              <TabsTrigger value="copy">{t("generation.copyVariants")} ({copies.length})</TabsTrigger>
              <TabsTrigger value="creatives">{t("generation.creatives")} ({creatives.length})</TabsTrigger>
            </TabsList>
            <span className="text-xs text-muted-foreground">{t("generation.proposalOf", { id: proposal.id, date: fmtDate(proposal.created_at) })}</span>
          </div>
          <TabsContent value="copy" className="mt-3">
            <div className="grid gap-4 xl:grid-cols-3 [&>*]:min-w-0">
              {copies.map((p) => (
                <Card key={p.id} className="gap-3 py-4">
                  <CardHeader className="grid-cols-1 gap-2 px-4">
                    <CardTitle className="flex items-center gap-2 text-sm">{p.style_slug} <span className="font-mono text-xs font-normal text-muted-foreground">v{p.style_version} · {tEnum("strategy", p.strategy)}</span></CardTitle>
                    <PieceMeta p={p} />
                  </CardHeader>
                  <CardContent className="grid grid-cols-1 gap-3 px-4">
                    <CopyText piece={p} facts={proposal.facts ?? []} />
                    <p className="text-xs text-muted-foreground"><span className="font-medium text-foreground">{t("generation.why")}: </span>{p.why}</p>
                    <TagChips tags={{}} free={p.effective_tags.filter((x) => x.includes(":") && !x.startsWith("tono") && !x.startsWith("registro") && !x.startsWith("audiencia"))} />
                    <AppliedList applied={p.applied_directives} />
                    {p.validation.length ? <ValidationFindings piece={p} /> : null}
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => setCopilotId(p.id)}><Wand2 />{t("generation.copilot")}</Button>
                      <Button size="sm" variant="ghost" asChild><Link href={`/piezas/${p.id}`}><PenLine />{t("generation.openEditor")}</Link></Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
          <TabsContent value="creatives" className="mt-3 grid gap-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
              {creatives.map((p) => (
                <Card key={p.id} className="gap-2 overflow-hidden py-0">
                  <button className="text-left" onClick={() => setCopilotId(p.id)}>
                    <CreativeThumb piece={p} className="aspect-[4/5] w-full rounded-none border-0 border-b" />
                  </button>
                  <CardContent className="grid grid-cols-1 gap-2 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium">{tEnum("creative", p.creative_slug)}</p>
                      {p.adaptation ? (
                        <Tooltip>
                          <TooltipTrigger asChild><Badge variant="outline" className="border-status-warn/60 text-status-warn">◐ {t("generation.adaptation")}</Badge></TooltipTrigger>
                          <TooltipContent className="max-w-xs text-xs">{p.adaptation}</TooltipContent>
                        </Tooltip>
                      ) : <Badge variant="outline" className="border-status-ok/50 text-status-ok">✓</Badge>}
                    </div>
                    <PieceMeta p={p} />
                    <p className="text-xs text-muted-foreground">{p.why}</p>
                    {p.missing_inputs.length ? <p className="text-xs text-status-warn">{t("generation.missingInputs")}: {p.missing_inputs.join(" ")}</p> : null}
                    {p.validation.some((f) => f.severity === "block") ? <ValidationFindings piece={p} /> : null}
                    <div className="flex gap-2">
                      <Button size="xs" variant="outline" onClick={() => setCopilotId(p.id)}><Wand2 />{t("generation.copilot")}</Button>
                      <Button size="xs" variant="ghost" asChild><Link href={`/piezas/${p.id}`}><PenLine />{t("generation.openEditor")}</Link></Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
            {proposal.excluded_creatives.length ? (
              <Card className="gap-2 py-4">
                <CardHeader className="px-4"><CardTitle className="text-sm">{t("generation.excluded")}</CardTitle></CardHeader>
                <CardContent className="grid gap-1.5 px-4">
                  {proposal.excluded_creatives.map((e) => (
                    <div key={String(e.slug)} className="flex items-start gap-2 text-xs text-muted-foreground opacity-80">
                      <Ban className="mt-0.5 size-3.5 shrink-0" />
                      <span className="w-48 shrink-0 font-medium text-foreground">{tEnum("creative", String(e.slug))}</span>
                      <Badge variant="outline">{t(`generation.excludedKind.${String(e.kind)}`)}</Badge>
                      <span>{String(e.reason)}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}
          </TabsContent>
        </Tabs>
      )}
      <CopilotSheet pieceId={copilotId} onClose={() => { setCopilotId(null); void mutate(); }} />
    </div>
  );
}
