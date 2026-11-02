"use client";

import { ArrowRight, Camera } from "lucide-react";
import Link from "next/link";

import { EmptyState, Loading, PageHeader } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { CaseStatusBadge } from "@/components/cases/parts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fmtDate, t, tEnum } from "@/i18n";
import { useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const STANCES = [
  { key: "en_contra", tone: "border-t-status-block" },
  { key: "a_favor", tone: "border-t-status-ok" },
  { key: "neutral", tone: "border-t-muted-foreground/40" },
] as const;

// MVP home: the capture button and the latest cases grouped by stance.
export default function HomePage() {
  const { me } = useSession();
  const { data, isLoading } = useApi<Schemas["Page_CaseListItem_"]>("/cases?page_size=60&order=recent", { refreshInterval: 30_000 });
  const { data: ai } = useApi<{ key_present: boolean; llm_provider: string }>("/meta/ai-status");
  if (isLoading || !data) return <Loading />;
  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title={t("mvp.homeTitle")} subtitle={t("dashboard.welcome", { name: me?.user.name })} />
        <Button asChild size="lg"><Link href="/captura"><Camera />{t("mvp.newCapture")}</Link></Button>
      </div>
      {ai && ai.llm_provider !== "mock" && !ai.key_present ? (
        <p className="rounded-md border border-status-warn/50 bg-status-warn/10 p-3 text-sm">{t("mvp.keyMissing")}</p>
      ) : null}
      {!data.items.length ? (
        <Card className="py-10"><CardContent className="grid justify-items-center gap-3 text-center">
          <p className="text-sm text-muted-foreground">{t("mvp.emptyHome")}</p>
          <Button asChild><Link href="/captura"><Camera />{t("mvp.newCapture")}</Link></Button>
        </CardContent></Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          {STANCES.map(({ key, tone }) => {
            const items = data.items.filter((c) => (c.stance ?? "neutral") === key);
            return (
              <Card key={key} className={cn("gap-2 border-t-4 py-4", tone)}>
                <CardHeader className="flex flex-row items-center justify-between px-4">
                  <CardTitle className="text-sm">{tEnum("stance", key)} · {items.length}</CardTitle>
                  <Link href={`/casos?stance=${key}`} className="flex items-center gap-1 text-xs text-primary hover:underline">{t("nav.cases")}<ArrowRight className="size-3" /></Link>
                </CardHeader>
                <CardContent className="grid gap-2 px-4">
                  {items.length ? items.slice(0, 12).map((c) => (
                    <Link key={c.id} href={`/casos/${c.id}`} className="grid gap-1 rounded-md border px-3 py-2 hover:bg-muted">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-xs text-primary">{c.code}</span>
                        <CaseStatusBadge status={c.status} />
                      </div>
                      <p className="line-clamp-2 text-sm">{c.post_text}</p>
                      <p className="text-[11px] text-muted-foreground">{c.network ? `${tEnum("network", c.network)} · ` : ""}{fmtDate(c.created_at)}</p>
                    </Link>
                  )) : <EmptyState label={t("common.empty")} />}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
