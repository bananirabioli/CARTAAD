"use client";

import { PenLine } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AlertBadge } from "@/components/app/badges";
import { EmptyState, Loading, PageHeader, Pagination } from "@/components/app/common";
import { ClaimList, RiskBreakdown, RiskMeter } from "@/components/cases/parts";
import { PieceActions } from "@/components/pieces/actions";
import { CopyText, CreativeThumb, FiguresPanel, PieceLegalPanel, PieceStatusBadge, RedTeamPanel, ValidationBadge, ValidationFindings, type PieceD } from "@/components/pieces/parts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { enumOptions, t, tEnum } from "@/i18n";
import { qs, useApi, type Schemas } from "@/lib/api/client";

const ALL = "__all__";
type Item = Schemas["InboxItem"];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-2">
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

function ReviewSheet({ pieceId, onClose }: { pieceId: number | null; onClose: () => void }) {
  const { data: piece, mutate } = useApi<PieceD>(pieceId ? `/pieces/${pieceId}` : null);
  const { data: c } = useApi<Schemas["CaseDetail"]>(piece ? `/cases/${piece.case_id}` : null);
  const set = (p: PieceD) => mutate(p, { revalidate: false });
  return (
    <Sheet open={pieceId !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-3xl">
        {!piece ? <Loading className="p-6" /> : (
          <>
            <SheetHeader>
              <SheetTitle className="flex flex-wrap items-center gap-2">
                <span className="font-mono">{piece.case_code}</span>
                {piece.kind === "copy" ? `Copy · ${piece.style_slug}` : tEnum("creative", piece.creative_slug)}
                <span className="font-mono text-xs text-muted-foreground">v{piece.current_version}</span>
                <PieceStatusBadge status={piece.status} />
              </SheetTitle>
            </SheetHeader>
            <div className="grid gap-5 px-4 pb-8">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap gap-1.5"><ValidationBadge status={piece.validation_status} /><Badge variant="outline">{t("generation.figures", { verified: piece.figures_verified ?? 0, total: piece.figures_total ?? 0 })}</Badge></div>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" asChild><Link href={`/piezas/${piece.id}`}><PenLine />{t("inbox.openEditor")}</Link></Button>
                  <PieceActions piece={piece} onChange={set} />
                </div>
              </div>
              {piece.approval_blockers?.length && ["generado", "bloqueado"].includes(piece.status) ? (
                <div className="rounded-md border border-status-warn/50 bg-status-warn/5 p-3 text-xs">
                  <p className="mb-1 font-medium">{t("inbox.blockers")}</p>
                  <ul className="list-disc pl-4">{piece.approval_blockers.map((b) => <li key={b}>{b}</li>)}</ul>
                </div>
              ) : piece.status === "generado" ? <p className="text-xs text-status-ok">{t("inbox.ready")}</p> : null}
              <div className="grid gap-4 md:grid-cols-2 [&>*]:min-w-0">
                <Section title={t("editor.preview")}>
                  {piece.kind === "copy" ? <div className="rounded-md border p-3"><CopyText piece={piece} facts={piece.facts ?? []} /></div> : <CreativeThumb piece={piece} className="w-full" />}
                </Section>
                <Section title={t("inbox.original")}>
                  {c ? (
                    <div className="grid gap-2 rounded-md border p-3 text-sm">
                      <div className="flex items-center gap-2"><AlertBadge level={c.alert_level} ratio={c.alert_ratio} /><span className="text-xs text-muted-foreground">{c.source_name}</span></div>
                      <p>{c.post.text}</p>
                      {c.interpretation ? <ClaimList claims={c.interpretation.claims} facts={c.facts ?? []} /> : null}
                    </div>
                  ) : <Loading />}
                </Section>
              </div>
              <Section title={t("editor.figures")}><FiguresPanel piece={piece} onChange={set} /></Section>
              {piece.legal_required ? <Section title={t("editor.legal")}><PieceLegalPanel piece={piece} onChange={set} /></Section> : null}
              <div className="grid gap-4 md:grid-cols-2 [&>*]:min-w-0">
                <Section title={t("editor.redTeam")}><RedTeamPanel notes={piece.red_team_notes ?? []} /></Section>
                <Section title={t("cases.riskBreakdown")}><RiskBreakdown items={piece.risk_breakdown} /></Section>
              </div>
              <Section title={t("editor.validation")}><ValidationFindings piece={piece} /></Section>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

export default function InboxPage() {
  const [status, setStatus] = useState("generado,bloqueado");
  const [style, setStyle] = useState(ALL);
  const [kind, setKind] = useState(ALL);
  const [legal, setLegal] = useState(ALL);
  const [flow, setFlow] = useState(ALL);
  const [tag, setTag] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number | null>(null);
  const { data: styles } = useApi<Schemas["StyleOut"][]>("/styles");
  const v = (x: string) => (x === ALL ? null : x);
  const { data, isLoading, mutate } = useApi<Schemas["Page_InboxItem_"]>(`/inbox${qs({ status, style: v(style), kind: v(kind), legal: v(legal), flow: v(flow), tag, page, page_size: 24 })}`);
  const reset = () => setPage(1);
  return (
    <div>
      <PageHeader title={t("inbox.title")} subtitle={t("inbox.subtitle")} />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Select value={status} onValueChange={(x) => { setStatus(x); reset(); }}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="generado,bloqueado">{t("inbox.statusPending")}</SelectItem>
            <SelectItem value="aprobado,programado,publicado">{t("inbox.statusApproved")}</SelectItem>
            <SelectItem value="generado,bloqueado,aprobado,programado,publicado,descartado">{t("inbox.statusAll")}</SelectItem>
          </SelectContent>
        </Select>
        <Select value={flow} onValueChange={(x) => { setFlow(x); reset(); }}>
          <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value={ALL}>{t("cases.allFlows")}</SelectItem>{enumOptions("flow").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={style} onValueChange={(x) => { setStyle(x); reset(); }}>
          <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value={ALL}>{t("inbox.allStyles")}</SelectItem>{(styles ?? []).map((s) => <SelectItem key={s.slug} value={s.slug}>{s.name}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={kind} onValueChange={(x) => { setKind(x); reset(); }}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value={ALL}>{t("inbox.allKinds")}</SelectItem>{enumOptions("piece_kind").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={legal} onValueChange={(x) => { setLegal(x); reset(); }}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value={ALL}>{t("inbox.allLegal")}</SelectItem><SelectItem value="pendiente">{t("inbox.legalPending")}</SelectItem></SelectContent>
        </Select>
        <Input className="w-64" placeholder={t("inbox.tag")} value={tag} onChange={(e) => { setTag(e.target.value.trim()); reset(); }} />
      </div>
      {isLoading ? <Loading /> : !data?.items.length ? <EmptyState /> : (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 [&>*]:min-w-0">
            {data.items.map((p: Item) => (
              <Card key={p.id} className="cursor-pointer gap-0 overflow-hidden py-0 transition-shadow hover:shadow-md" onClick={() => setOpen(p.id)}>
                <div className="grid grid-cols-[110px_minmax(0,1fr)]">
                  <div className="h-40 overflow-hidden border-r">
                    {p.kind === "creative" ? <CreativeThumb piece={p} className="h-40 w-full rounded-none border-0 text-[10px]" /> : (
                      <div className="h-40 bg-muted/40 p-2 text-[11px] leading-snug text-muted-foreground">{((p.content.segments as { text: string }[]) ?? []).map((s) => s.text).join(" ")}</div>
                    )}
                  </div>
                  <CardContent className="grid min-w-0 gap-1.5 p-3 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-primary">{p.case_code}</span>
                      <AlertBadge level={p.alert_level} />
                    </div>
                    <p className="truncate text-sm font-medium">{p.kind === "copy" ? `Copy · ${p.style_slug}` : tEnum("creative", p.creative_slug)}</p>
                    <div className="flex flex-wrap gap-1"><PieceStatusBadge status={p.status} /><ValidationBadge status={p.validation_status} />{p.legal_required ? <Badge variant="outline" className="border-veda/50 text-veda">{tEnum("legal_status", p.legal_status)}</Badge> : null}</div>
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span>{t("generation.figures", { verified: p.figures_verified ?? 0, total: p.figures_total ?? 0 })} · {t("generation.redTeam")} {Object.values(p.red_team_summary ?? {}).reduce((a, b) => a + b, 0)}</span>
                      <RiskMeter score={p.risk_score} />
                    </div>
                    <p className="line-clamp-2 text-muted-foreground">{p.post_text}</p>
                  </CardContent>
                </div>
              </Card>
            ))}
          </div>
          <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
      <ReviewSheet pieceId={open} onClose={() => { setOpen(null); void mutate(); }} />
    </div>
  );
}
