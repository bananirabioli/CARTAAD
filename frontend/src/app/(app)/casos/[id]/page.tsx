"use client";

import { ArrowRight, Pencil, RefreshCw, Scale } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AlertBadge } from "@/components/app/badges";
import { ErrorState, KeyValue, Loading, ReasonDialog } from "@/components/app/common";
import { FormDialog } from "@/components/app/form-dialog";
import { useSession } from "@/components/app/session";
import { CaseStatusBadge, ClaimList, LearningTable, RiskBreakdown, RiskMeter } from "@/components/cases/parts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { enumOptions, fmtDate, fmtNum, t, tEnum } from "@/i18n";
import { api, ApiError, fileUrl, refresh, useApi, type Schemas } from "@/lib/api/client";
import { useTopics } from "@/lib/hooks";
import { cn } from "@/lib/utils";

type CaseD = Schemas["CaseDetail"];

function errMsg(err: unknown) {
  return err instanceof ApiError ? (err.ruleId ? `[${err.ruleId}] ${err.message}` : err.message) : String(err);
}

function Section({ title, children, action, className }: { title: string; children: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-3 py-4", className)}>
      <CardHeader className="flex flex-row items-center justify-between gap-2 px-4">
        <CardTitle className="text-sm">{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent className="min-w-0 px-4">{children}</CardContent>
    </Card>
  );
}

function DecisionPanel({ c, onDone }: { c: CaseD; onDone: (d: CaseD) => void }) {
  const { can } = useSession();
  const accounts = c.account_options ?? [];
  const [accountId, setAccountId] = useState<string>(accounts[0] ? String(accounts[0].id) : "");
  const account = accounts.find((a) => String(a.id) === accountId);
  const recommended = (c.recommended_style?.value as string | null) ?? null;
  const [style, setStyle] = useState<string>("");
  const [strategy, setStrategy] = useState<string>(c.strategy_suggested ?? "");
  const [reasonFor, setReasonFor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setStyle(""), [accountId]);

  if (c.status !== "interpretado" || !can("case.decide")) return null;

  async function decide(decision: string, reason = "") {
    setBusy(true);
    try {
      const body: Record<string, unknown> = { decision, reason };
      if (decision === "responder") Object.assign(body, { account_id: Number(accountId), strategy: strategy || null, style_slug: style || null });
      const d = await api.post<CaseD>(`/cases/${c.id}/decide`, body);
      onDone(d);
      await refresh("/cases", "/dashboard");
      toast.success(tEnum("case_status", d.status));
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title={t("cases.decision")}>
      <div className="grid gap-4">
        <p className="text-xs text-muted-foreground">{t("cases.decisionHelp")}</p>
        {c.flow ? (
          <div className="grid min-w-0 gap-3 rounded-md border bg-muted/30 p-3">
            <div className="grid gap-1.5">
              <Label>{t("cases.account")}</Label>
              <Select value={accountId} onValueChange={setAccountId}>
                <SelectTrigger className="w-full max-w-full min-w-0"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {accounts.map((a) => (
                    <SelectItem key={a.id} value={String(a.id)}>
                      {a.display_name} · {a.format_name} · {tEnum("account_type", a.account_type)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {account ? (
              <div className="grid gap-1.5">
                <Label>{t("cases.style")}</Label>
                <div className="flex flex-wrap gap-1.5">
                  {account.allowed_styles.map((s) => {
                    const selected = (style || account.default_style) === s;
                    return (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setStyle(s === account.default_style ? "" : s)}
                        className={cn("rounded-full border px-2.5 py-1 text-xs", selected ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted")}
                      >
                        {s}
                        {s === recommended ? ` · ${t("cases.recommendedTag")}` : ""}
                      </button>
                    );
                  })}
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {t("cases.styleDefault", { style: account.default_style ?? "", source: t(`cases.sourceStyleSource.${account.default_source}`) })}
                </p>
              </div>
            ) : null}
            <div className="grid gap-1.5">
              <Label>{t("cases.confirmStrategy")}</Label>
              <Select value={strategy} onValueChange={setStrategy}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(c.strategy_candidates ?? []).map((s) => <SelectItem key={s} value={s}>{tEnum("strategy", s)}{s === c.strategy_suggested ? ` · ${t("cases.recommendedTag")}` : ""}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Button disabled={busy || !accountId} onClick={() => decide("responder")}>{t("cases.confirmRespond")}</Button>
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {(["monitorear", "ignorar", "canalizar"] as const).map((d) => (
            <Button key={d} size="sm" variant={c.classification?.recommendation === d ? "default" : "outline"} onClick={() => setReasonFor(d)}>
              {tEnum("decision", d)}
            </Button>
          ))}
        </div>
      </div>
      <ReasonDialog
        open={reasonFor !== null}
        onOpenChange={(o) => !o && setReasonFor(null)}
        title={t("cases.reasonFor", { decision: tEnum("decision", reasonFor ?? "") })}
        onConfirm={async (reason) => {
          if (reasonFor) await decide(reasonFor, reason);
        }}
      />
    </Section>
  );
}

function LegalPanel({ c, onDone }: { c: CaseD; onDone: (d: CaseD) => void }) {
  const { can } = useSession();
  const [note, setNote] = useState("");
  if (!c.legal_required) return null;
  async function act(action: string) {
    try {
      onDone(await api.post<CaseD>(`/cases/${c.id}/legal`, { action, note }));
      await refresh("/cases", "/dashboard");
    } catch (err) {
      toast.error(errMsg(err));
    }
  }
  return (
    <Section title={t("cases.legalPanel")} action={<Badge variant="outline" className="border-veda/50 text-veda"><Scale className="size-3" />{tEnum("legal_status", c.legal_status)}</Badge>}>
      <div className="grid gap-2 text-sm">
        <p className="text-xs text-muted-foreground">{t("cases.legalHelp")}</p>
        {c.legal_note ? <p className="rounded bg-muted p-2 text-xs">{c.legal_note} · {fmtDate(c.legal_at)}</p> : null}
        {can("legal.review") && c.legal_status === "pendiente" ? (
          <>
            <Label htmlFor="ln">{t("cases.legalNote")}</Label>
            <Textarea id="ln" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
            <div className="flex gap-2">
              <Button size="sm" disabled={note.trim().length < 3} onClick={() => act("liberar")}>{t("cases.legalRelease")}</Button>
              <Button size="sm" variant="destructive" disabled={note.trim().length < 3} onClick={() => act("bloquear")}>{t("cases.legalBlock")}</Button>
            </div>
          </>
        ) : null}
      </div>
    </Section>
  );
}

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const { can } = useSession();
  const topics = useTopics();
  const { data: c, error, isLoading, mutate } = useApi<CaseD>(`/cases/${params.id}`);
  const [editCls, setEditCls] = useState(false);
  const [closeOpen, setCloseOpen] = useState(false);
  const [reopenOpen, setReopenOpen] = useState(false);

  if (isLoading) return <Loading />;
  if (error || !c) return <ErrorState error={error} onRetry={() => mutate()} />;
  const set = (d: CaseD) => mutate(d, { revalidate: false });
  const cls = c.classification;
  const interp = c.interpretation;
  const closable = !["monitoreando", "ignorado", "canalizado", "descartado", "calificado", "publicado", "medido"].includes(c.status);

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-mono text-xl font-semibold">{c.code}</h1>
            <CaseStatusBadge status={c.status} />
            <AlertBadge level={c.alert_level} ratio={c.alert_ratio} />
            {c.flow ? <Badge variant="outline">{tEnum("flow", c.flow)}</Badge> : null}
            {c.canalizar_a_atencion ? <Badge variant="secondary">{t("cases.canalizar")}</Badge> : null}
          </div>
          <p className="text-xs text-muted-foreground">
            {c.source_name ?? tEnum("origin", "manual")} · {fmtDate(c.created_at)}
            {c.decided_by_name ? ` · ${t("cases.decidedBy", { name: c.decided_by_name })}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="text-right">
            <p className="text-[11px] text-muted-foreground">{t("cases.risk")}</p>
            <RiskMeter score={c.risk_score} />
          </div>
          {["listo_para_generar", "generado", "en_revision", "aprobado", "programado"].includes(c.status) ? (
            <Button asChild>
              <Link href={`/casos/${c.id}/generacion`}>{t("cases.goGenerate")}<ArrowRight /></Link>
            </Button>
          ) : null}
          {closable && can("case.decide") ? <Button variant="ghost" size="sm" onClick={() => setCloseOpen(true)}>{t("cases.close")}</Button> : null}
          {["monitoreando", "ignorado", "canalizado", "descartado"].includes(c.status) && can("case.decide") ? <Button variant="outline" size="sm" onClick={() => setReopenOpen(true)}>{t("cases.reopen")}</Button> : null}
        </div>
      </div>
      {c.closed_reason ? <p className="rounded-md border bg-muted/40 p-2 text-sm"><span className="font-medium">{t("cases.closedReason")}:</span> {c.closed_reason}</p> : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="grid content-start gap-4">
          <Section title={t("cases.original")}>
            <div className="grid gap-3 text-sm">
              {c.post.image_key ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={fileUrl(c.post.image_key)} alt="" className="max-h-72 rounded border object-contain" />
              ) : null}
              <p className="whitespace-pre-line text-base">{c.post.text}</p>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <KeyValue label={t("monitoring.network")}>{tEnum("network", c.post.network)}</KeyValue>
                <KeyValue label={t("monitoring.velocity")}>{t("monitoring.velocityValue", { value: fmtNum(c.post.velocity ?? 0, 1) })}</KeyValue>
                <KeyValue label={t("monitoring.baseline")}>{c.post.baseline_per_hour ? t("monitoring.baselinePerHour", { value: fmtNum(c.post.baseline_per_hour, 1) }) : t("monitoring.baselineInsufficient")}</KeyValue>
                <KeyValue label={t("monitoring.interactions")}>{fmtNum(c.post.total_interactions)}</KeyValue>
              </div>
            </div>
          </Section>

          {cls ? (
            <Section
              title={t("cases.classification")}
              action={can("case.classify_edit") ? <Button size="xs" variant="ghost" onClick={() => setEditCls(true)}><Pencil />{t("cases.editClassification")}</Button> : null}
            >
              <div className="grid gap-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{tEnum("stance", cls.stance)}</Badge>
                  <Badge variant="outline">{topics.bySlug.get(cls.topic_slug)?.name ?? cls.topic_slug}</Badge>
                  <Badge variant="outline">{tEnum("message_type", cls.message_type)}</Badge>
                  <Badge>{t("cases.recommendation")}: {tEnum("recommendation", cls.recommendation)}</Badge>
                  <span className="text-xs text-muted-foreground">{t("cases.confidence", { value: fmtNum(cls.confidence * 100, 0) + "%" })}</span>
                </div>
                <p className="text-sm"><span className="font-medium">{t("cases.why")}: </span>{cls.explanation}</p>
              </div>
            </Section>
          ) : null}

          {interp ? (
            <Section title={t("cases.interpretation")} action={can("case.classify_edit") ? <Button size="xs" variant="ghost" onClick={async () => set(await api.post<CaseD>(`/cases/${c.id}/reinterpret`))}><RefreshCw />{t("cases.reinterpret")}</Button> : null}>
              <div className="grid gap-4 text-sm">
                <p>{interp.summary}</p>
                <p className="text-muted-foreground"><span className="font-medium text-foreground">{t("cases.narrative")}: </span>{interp.narrative}</p>
                <div className="grid gap-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("cases.claims")}</p>
                  <ClaimList claims={interp.claims} facts={c.facts ?? []} />
                </div>
                {interp.missing_context.length ? (
                  <div className="grid gap-1">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("cases.missingContext")}</p>
                    <ul className="grid gap-1 text-xs">
                      {interp.missing_context.map((m, i) => (
                        <li key={i} className={cn("rounded px-2 py-1", m.needs_kb_owner ? "bg-status-warn/10 text-foreground" : "bg-muted")}>{String(m.description)}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <div className="grid gap-1">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("cases.comments")}</p>
                  {interp.comments_summary.length ? interp.comments_summary.map((th, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <Badge variant="secondary" className="shrink-0">{String(th.theme)} · {fmtNum(Number(th.share) * 100, 0)}%</Badge>
                      <span className="text-muted-foreground">{String(th.summary)}</span>
                    </div>
                  )) : <p className="text-xs text-muted-foreground">{t("common.empty")}</p>}
                </div>
                <div className="grid gap-1">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("cases.repeated")}</p>
                  {interp.repeated_in.length ? interp.repeated_in.map((r, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <Badge variant="outline" className="shrink-0">{fmtNum(Number(r.similarity) * 100, 0)}%</Badge>
                      <span><span className="font-medium">{String(r.source)}</span>: {String(r.text)}</span>
                    </div>
                  )) : <p className="text-xs text-muted-foreground">{t("cases.notRepeated")}</p>}
                </div>
              </div>
            </Section>
          ) : null}

          <Section title={t("cases.timeline")}>
            <ul className="grid gap-1 text-xs">
              {(c.timeline ?? []).map((e, i) => (
                <li key={i} className="flex gap-2">
                  <span className="w-36 shrink-0 text-muted-foreground">{fmtDate(String(e.at))}</span>
                  <span className="font-mono">{String(e.action)}</span>
                  <span className="text-muted-foreground">{String(e.who)}</span>
                  <span className="truncate">{String(e.note ?? "")}</span>
                </li>
              ))}
            </ul>
          </Section>
        </div>

        <div className="grid content-start gap-4">
          <DecisionPanel c={c} onDone={set} />
          <LegalPanel c={c} onDone={set} />
          {c.flow ? (
            <Section title={t("cases.strategy")}>
              <div className="grid gap-2 text-sm">
                <div className="flex items-center gap-2">
                  <Badge>{tEnum("strategy", c.strategy ?? c.strategy_suggested ?? "")}</Badge>
                  {c.strategy && c.strategy !== c.strategy_suggested ? <span className="text-xs text-muted-foreground">({t("cases.recommendedTag")}: {tEnum("strategy", c.strategy_suggested)})</span> : null}
                </div>
                <p className="text-xs">{c.strategy_justification}</p>
                {c.strategy_alternatives.length ? (
                  <div className="grid gap-1">
                    <p className="text-xs font-medium">{t("cases.alternatives")}</p>
                    {c.strategy_alternatives.map((a, i) => <p key={i} className="text-xs text-muted-foreground"><span className="font-medium text-foreground">{tEnum("strategy", String(a.strategy))}</span>: {String(a.why)}</p>)}
                  </div>
                ) : null}
              </div>
            </Section>
          ) : null}
          {c.flow ? (
            <Section title={t("cases.recommendedStyle")}>
              <div className="grid gap-3">
                <div className="flex items-center gap-2 text-sm">
                  {c.recommended_style?.value ? <Badge>{String(c.recommended_style.value)}</Badge> : <Badge variant="outline">{t("cases.insufficient")}</Badge>}
                  <span className="text-xs text-muted-foreground">{String(c.recommended_style?.reason ?? "")}</span>
                </div>
                {c.style_slug ? <p className="text-xs"><span className="font-medium">{t("cases.style")}:</span> {c.style_slug} — {String(c.style_choice?.reason ?? "")}</p> : null}
                <LearningTable learning={c.learning_context} />
              </div>
            </Section>
          ) : null}
          <Section title={t("cases.riskBreakdown")} action={<RiskMeter score={c.risk_score} />}>
            <p className="mb-2 text-[11px] text-muted-foreground">{t("cases.riskHelp")}</p>
            <RiskBreakdown items={c.risk_breakdown} />
          </Section>
        </div>
      </div>

      {cls ? (
        <FormDialog
          open={editCls}
          onOpenChange={setEditCls}
          title={t("cases.editClassification")}
          fields={[
            { name: "stance", label: t("cases.classification"), type: "select", options: enumOptions("stance"), required: true, colSpan: 1 },
            { name: "topic_slug", label: t("kb.facts.topic"), type: "select", options: topics.list.map((tp) => ({ value: tp.slug, label: tp.name })), required: true, colSpan: 1 },
            { name: "message_type", label: t("common.type"), type: "select", options: enumOptions("message_type"), required: true },
            { name: "recommendation", label: t("cases.recommendation"), type: "select", options: enumOptions("recommendation"), required: true },
          ]}
          initial={{ stance: cls.stance, topic_slug: cls.topic_slug, message_type: cls.message_type, recommendation: cls.recommendation }}
          onSubmit={async (v) => {
            set(await api.patch<CaseD>(`/cases/${c.id}/classification`, v));
            await refresh("/cases", "/dashboard");
          }}
        />
      ) : null}
      <ReasonDialog open={closeOpen} onOpenChange={setCloseOpen} title={t("cases.close")} onConfirm={async (reason) => { set(await api.post<CaseD>(`/cases/${c.id}/close`, { reason })); await refresh("/cases"); }} />
      <ReasonDialog open={reopenOpen} onOpenChange={setReopenOpen} title={t("cases.reopen")} onConfirm={async (reason) => { set(await api.post<CaseD>(`/cases/${c.id}/reopen`, { reason })); await refresh("/cases"); }} />
    </div>
  );
}
