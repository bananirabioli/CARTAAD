"use client";

import Link from "next/link";
import { useState } from "react";

import { Loading, PageHeader } from "@/components/app/common";
import { LearningTable } from "@/components/cases/parts";
import { RankingTable, VariantsTable } from "@/components/metrics/parts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { t, tEnum } from "@/i18n";
import { qs, useApi } from "@/lib/api/client";
import { useTopics } from "@/lib/hooks";

const ALL = "__all__";
type Rankings = { sample_size: number; min_sample: number; sufficient: boolean; formats: never[]; styles: never[]; strategies: never[]; creatives: never[]; by_topic: Record<string, number> };

export default function MetricsPage() {
  const topics = useTopics();
  const [topic, setTopic] = useState(ALL);
  const tp = topic === ALL ? null : topic;
  const { data, isLoading } = useApi<Rankings>(`/metrics/rankings${qs({ topic: tp })}`);
  const { data: learning } = useApi<Record<string, unknown>>(tp ? `/metrics/learning${qs({ topic: tp })}` : null);
  const { data: experiments } = useApi<Record<string, unknown>[]>("/metrics/experiments");
  return (
    <div className="grid gap-4">
      <PageHeader title={t("metrics.title")} subtitle={t("metrics.subtitle")} />
      <div className="flex flex-wrap items-center gap-3">
        <Select value={topic} onValueChange={setTopic}>
          <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("metrics.allTopics")}</SelectItem>
            {topics.list.map((x) => <SelectItem key={x.slug} value={x.slug}>{x.name}</SelectItem>)}
          </SelectContent>
        </Select>
        {data ? <span className="text-xs text-muted-foreground">{t("metrics.sampleTotal", { n: data.sample_size, min: data.min_sample })}</span> : null}
        {data && !tp ? <div className="flex flex-wrap gap-1">{Object.entries(data.by_topic).map(([k, n]) => <Badge key={k} variant="outline">{topics.bySlug.get(k)?.name ?? k}: {n}</Badge>)}</div> : null}
      </div>
      {isLoading || !data ? <Loading /> : (
        <Tabs defaultValue="styles">
          <TabsList>
            {(["styles", "formats", "strategies", "creatives"] as const).map((k) => <TabsTrigger key={k} value={k}>{t(`metrics.${k}`)}</TabsTrigger>)}
          </TabsList>
          {(["styles", "formats", "strategies", "creatives"] as const).map((k) => (
            <TabsContent key={k} value={k} className="mt-3"><Card className="py-2"><CardContent className="px-2"><RankingTable rows={data[k]} kind={k} /></CardContent></Card></TabsContent>
          ))}
        </Tabs>
      )}
      {learning ? (
        <Card className="gap-2 py-4">
          <CardHeader className="px-4"><CardTitle className="text-sm">{t("metrics.learning")}</CardTitle></CardHeader>
          <CardContent className="px-4"><LearningTable learning={learning} /></CardContent>
        </Card>
      ) : null}
      <Card className="gap-2 py-4">
        <CardHeader className="px-4"><CardTitle className="text-sm">{t("metrics.experiments")}</CardTitle></CardHeader>
        <CardContent className="grid gap-4 px-4">
          {!experiments?.length ? <p className="text-xs text-muted-foreground">{t("metrics.noExperiments")}</p> : experiments.map((e) => (
            <div key={String(e.case_id)} className="grid gap-1">
              <div className="flex items-center gap-2 text-sm">
                <Link href={`/casos/${e.case_id}`} className="font-mono text-primary hover:underline">{String(e.code)}</Link>
                <span className="text-xs text-muted-foreground">{topics.bySlug.get(String(e.topic))?.name}</span>
                {e.rating ? <Badge variant="outline">{tEnum("outcome", String(e.rating))}</Badge> : null}
              </div>
              <VariantsTable variants={e.variants as Record<string, unknown>[]} />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
