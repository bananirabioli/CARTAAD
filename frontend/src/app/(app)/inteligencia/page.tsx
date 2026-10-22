"use client";

import { Download, Network } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AlertBadge } from "@/components/app/badges";
import { EmptyState, Loading, PageHeader } from "@/components/app/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fmtDate, fmtNum, t, tEnum } from "@/i18n";
import { API_BASE, qs, useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Narrative = Schemas["NarrativeOut"];
type Item = { post_id: number; source: string; network: string; text: string; published_at: string; interactions: number; alert_level: string | null; similarity: number; case_id: number | null; case_code: string | null };

function NarrativeCard({ n }: { n: Narrative }) {
  const items = n.items as Item[];
  const coordinated = n.level === "coordinado";
  return (
    <Card className="gap-3 py-4">
      <CardHeader className="grid gap-2 px-4">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge className={cn("border-transparent", coordinated ? "bg-status-block/15 text-status-block" : "bg-status-warn/15 text-status-warn")}>{t(`intelligence.level.${n.level}`)}</Badge>
          {n.topic_name ? <Badge variant="outline">{n.topic_name}</Badge> : null}
          <span className="text-muted-foreground">
            {t("intelligence.pages", { n: n.sources })} · {t("intelligence.posts", { n: n.posts })} · {t("intelligence.similarity", { value: fmtNum(n.mean_similarity, 2) })} · {t("intelligence.span", { hours: fmtNum(n.span_hours, 1) })} · {t("intelligence.interactions", { n: fmtNum(n.interactions) })}
          </span>
        </div>
        <CardTitle className="text-sm font-normal leading-relaxed">«{n.representative}»</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-0 px-4">
        <ol className="relative grid gap-3 border-l pl-4">
          {items.map((it) => (
            <li key={it.post_id} className="relative grid gap-0.5 text-xs">
              <span className="absolute -left-[21px] top-1 size-2.5 rounded-full border-2 border-background bg-primary" />
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-muted-foreground">{fmtDate(it.published_at)}</span>
                <span className="font-medium">{it.source}</span>
                <span className="text-muted-foreground">{tEnum("network", it.network)}</span>
                <span className="font-mono text-muted-foreground">{fmtNum(it.similarity, 2)}</span>
                <AlertBadge level={it.alert_level} />
                {it.case_id ? <Link className="font-mono text-primary hover:underline" href={`/casos/${it.case_id}`}>{it.case_code}</Link> : null}
              </div>
              <p className="line-clamp-2 text-muted-foreground">{it.text}</p>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function NarrativesTab() {
  const [days, setDays] = useState("7");
  const { data, isLoading } = useApi<Narrative[]>(`/intelligence/narratives${qs({ days })}`);
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <Select value={days} onValueChange={setDays}>
          <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>{["7", "14", "30"].map((d) => <SelectItem key={d} value={d}>{t("intelligence.window", { days: d })}</SelectItem>)}</SelectContent>
        </Select>
        <p className="max-w-3xl text-xs text-muted-foreground">{t("intelligence.disclaimer")}</p>
      </div>
      {isLoading ? <Loading /> : !data?.length ? <EmptyState label={t("intelligence.none")} /> : data.map((n) => <NarrativeCard key={n.id} n={n} />)}
    </div>
  );
}

function ReportTab() {
  const [start, setStart] = useState("");
  const [tag, setTag] = useState("");
  const query = qs({ start: start || null, tag: tag || null });
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1">
          <Label className="text-xs">{t("intelligence.start")}</Label>
          <Input type="date" className="w-44" value={start} onChange={(e) => setStart(e.target.value)} />
          <span className="text-[11px] text-muted-foreground">{t("intelligence.startHelp")}</span>
        </div>
        <div className="grid gap-1">
          <Label className="text-xs">{t("intelligence.tag")}</Label>
          <Input className="w-64" placeholder="estilo:cercano" value={tag} onChange={(e) => setTag(e.target.value.trim())} />
          <span className="text-[11px] text-transparent">.</span>
        </div>
        <div className="ml-auto flex gap-2 self-center">
          <Button size="sm" variant="outline" asChild><a href={`${API_BASE}/intelligence/weekly-report.md${query}`}><Download />{t("intelligence.downloadMd")}</a></Button>
          <Button size="sm" variant="outline" asChild><a href={`${API_BASE}/intelligence/weekly-report.html${qs({ start: start || null, tag: tag || null, download: true })}`}><Download />{t("intelligence.downloadHtml")}</a></Button>
        </div>
      </div>
      <iframe title={t("intelligence.tabs.report")} src={`${API_BASE}/intelligence/weekly-report.html${query}`} className="h-[75vh] w-full rounded-lg border bg-white" />
    </div>
  );
}

export default function IntelligencePage() {
  return (
    <div>
      <PageHeader title={t("intelligence.title")} subtitle={t("intelligence.subtitle")} />
      <Tabs defaultValue="narratives">
        <TabsList>
          <TabsTrigger value="narratives"><Network />{t("intelligence.tabs.narratives")}</TabsTrigger>
          <TabsTrigger value="report">{t("intelligence.tabs.report")}</TabsTrigger>
        </TabsList>
        <TabsContent value="narratives" className="mt-3"><NarrativesTab /></TabsContent>
        <TabsContent value="report" className="mt-3"><ReportTab /></TabsContent>
      </Tabs>
    </div>
  );
}
