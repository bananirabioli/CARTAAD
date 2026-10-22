"use client";

import { ArrowRight, Network, TrendingUp } from "lucide-react";
import Link from "next/link";

import { AlertBadge, ALERT_ORDER } from "@/components/app/badges";
import { EmptyState, Loading, PageHeader } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { CaseStatusBadge, RiskMeter } from "@/components/cases/parts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fmtNum, t, tEnum } from "@/i18n";
import { useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const ALERT_BG: Record<string, string> = {
  critico: "bg-alert-critico text-white",
  alto: "bg-alert-alto/15 text-alert-alto",
  medio: "bg-alert-medio/20",
  bajo: "bg-alert-bajo/15 text-alert-bajo",
  sin_linea_base: "bg-alert-sin-base/10 text-alert-sin-base",
};

export default function DashboardPage() {
  const { me } = useSession();
  const { data, isLoading } = useApi<Schemas["DashboardOut"]>("/dashboard", { refreshInterval: 60_000 });
  if (isLoading || !data) return <Loading />;
  const pending = [
    { key: "decide", label: t("dashboard.pendingDecide"), href: "/casos?status=interpretado" },
    { key: "legal", label: t("dashboard.pendingLegal"), href: "/casos" },
    { key: "generate", label: t("dashboard.pendingGenerate"), href: "/casos" },
    { key: "review", label: t("dashboard.pendingReview"), href: "/bandeja" },
  ];
  return (
    <div className="grid gap-5">
      <PageHeader title={t("dashboard.title")} subtitle={`${t("dashboard.welcome", { name: me?.user.name })} · ${t("dashboard.subtitle")}`} />
      <div className="grid gap-3 md:grid-cols-5">
        {ALERT_ORDER.map((level) => (
          <Link key={level} href={`/casos`} className={cn("rounded-lg border p-4 transition-shadow hover:shadow-sm", ALERT_BG[level])}>
            <p className="text-xs font-medium uppercase tracking-wide opacity-80">{tEnum("alert_level", level)}</p>
            <p className="mt-1 text-3xl font-semibold tabular-nums">{data.by_alert[level] ?? 0}</p>
            <p className="text-[11px] opacity-70">{t("dashboard.openByAlert")}</p>
          </Link>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="gap-2 py-4">
          <CardHeader className="px-4"><CardTitle className="text-sm">{t("dashboard.pending")}</CardTitle></CardHeader>
          <CardContent className="grid gap-2 px-4">
            {pending.map((p) => (
              <Link key={p.key} href={p.href} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm hover:bg-muted">
                <span>{p.label}</span>
                <span className="font-mono text-lg font-semibold">{data.pending[p.key] ?? 0}</span>
              </Link>
            ))}
          </CardContent>
        </Card>
        <Card className="gap-2 py-4 lg:col-span-2">
          <CardHeader className="flex flex-row items-center gap-2 px-4"><TrendingUp className="size-4" /><CardTitle className="text-sm">{t("dashboard.accelerating")}</CardTitle></CardHeader>
          <CardContent className="grid gap-2 px-4">
            {data.accelerating.length ? data.accelerating.map((a) => (
              <Link key={String(a.post_id)} href={a.case_id ? `/casos/${a.case_id}` : "/monitoreo"} className="flex items-start gap-3 rounded-md border px-3 py-2 hover:bg-muted">
                <AlertBadge level={String(a.alert_level)} ratio={Number(a.ratio)} />
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-sm">{String(a.text)}</p>
                  <p className="text-xs text-muted-foreground">{String(a.source ?? "")} · {t("monitoring.velocityValue", { value: fmtNum(Number(a.velocity), 1) })}</p>
                </div>
                {a.case_code ? <span className="font-mono text-xs text-primary">{String(a.case_code)}</span> : null}
              </Link>
            )) : <EmptyState label={t("dashboard.noData")} />}
          </CardContent>
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="gap-2 py-4">
          <CardHeader className="flex flex-row items-center gap-2 px-4"><Network className="size-4" /><CardTitle className="text-sm">{t("dashboard.repeated")}</CardTitle></CardHeader>
          <CardContent className="grid gap-2 px-4">
            {data.repeated.length ? data.repeated.map((r) => (
              <Link key={String(r.case_id)} href={`/casos/${r.case_id}`} className="grid gap-1 rounded-md border px-3 py-2 text-sm hover:bg-muted">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-primary">{String(r.code)}</span>
                  <Badge variant="secondary">{t("dashboard.repeatedItem", { count: Number(r.count) })}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">{(r.sources as string[]).join(" · ")}</p>
              </Link>
            )) : <EmptyState label={t("dashboard.noData")} />}
          </CardContent>
        </Card>
        <Card className="gap-2 py-4 lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between px-4">
            <CardTitle className="text-sm">{t("dashboard.recent")}</CardTitle>
            <Link href="/casos" className="flex items-center gap-1 text-xs text-primary hover:underline">{t("nav.cases")}<ArrowRight className="size-3" /></Link>
          </CardHeader>
          <CardContent className="grid gap-2 px-4">
            {data.recent_cases.map((c) => (
              <Link key={c.id} href={`/casos/${c.id}`} className="grid grid-cols-[80px_minmax(0,1fr)_auto_auto] items-center gap-3 rounded-md border px-3 py-2 hover:bg-muted">
                <span className="font-mono text-xs text-primary">{c.code}</span>
                <span className="truncate text-sm">{c.post_text}</span>
                <CaseStatusBadge status={c.status} />
                <RiskMeter score={c.risk_score} />
              </Link>
            ))}
          </CardContent>
        </Card>
      </div>
      <Card className="gap-2 py-4">
        <CardHeader className="px-4"><CardTitle className="text-sm">{t("dashboard.byStatus")}</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap gap-2 px-4">
          {Object.entries(data.by_status).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
            <span key={s} className="flex items-center gap-1.5"><CaseStatusBadge status={s} /><span className="font-mono text-sm">{n}</span></span>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
