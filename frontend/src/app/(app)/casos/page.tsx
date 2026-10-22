"use client";

import Link from "next/link";
import { useState } from "react";

import { AlertBadge } from "@/components/app/badges";
import { EmptyState, ErrorState, Loading, PageHeader, Pagination } from "@/components/app/common";
import { CaseStatusBadge, RiskMeter } from "@/components/cases/parts";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { enumOptions, fmtDate, t, tEnum } from "@/i18n";
import { qs, useApi, type Schemas } from "@/lib/api/client";
import { useTopics } from "@/lib/hooks";

const ALL = "__all__";

export default function CasesPage() {
  const topics = useTopics();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState(ALL);
  const [flow, setFlow] = useState(ALL);
  const [topic, setTopic] = useState(ALL);
  const [order, setOrder] = useState("alert");
  const [openOnly, setOpenOnly] = useState(true);
  const [page, setPage] = useState(1);
  const v = (x: string) => (x === ALL ? null : x);
  const { data, error, isLoading, mutate } = useApi<Schemas["Page_CaseListItem_"]>(
    `/cases${qs({ q, status: v(status), flow: v(flow), topic: v(topic), order, open_only: openOnly, page, page_size: 25 })}`,
  );
  const reset = () => setPage(1);
  return (
    <div>
      <PageHeader title={t("cases.title")} subtitle={t("cases.subtitle")} />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input className="w-56" placeholder={t("common.searchPlaceholder")} value={q} onChange={(e) => { setQ(e.target.value); reset(); }} />
        <Select value={status} onValueChange={(x) => { setStatus(x); reset(); }}>
          <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("cases.allStatus")}</SelectItem>
            {enumOptions("case_status").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={flow} onValueChange={(x) => { setFlow(x); reset(); }}>
          <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("cases.allFlows")}</SelectItem>
            {enumOptions("flow").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={topic} onValueChange={(x) => { setTopic(x); reset(); }}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("cases.allTopics")}</SelectItem>
            {topics.list.map((tp) => <SelectItem key={tp.slug} value={tp.slug}>{tp.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={order} onValueChange={setOrder}>
          <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="alert">{t("cases.orderAlert")}</SelectItem>
            <SelectItem value="risk">{t("cases.orderRisk")}</SelectItem>
            <SelectItem value="recent">{t("cases.orderRecent")}</SelectItem>
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={openOnly} onCheckedChange={(c) => { setOpenOnly(c); reset(); }} />
          {t("cases.openOnly")}
        </label>
      </div>
      {isLoading ? <Loading /> : error ? <ErrorState error={error} onRetry={() => mutate()} /> : !data?.items.length ? <EmptyState /> : (
        <>
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-24">{t("cases.code")}</TableHead>
                  <TableHead>{t("cases.post")}</TableHead>
                  <TableHead className="w-36">{t("monitoring.alert")}</TableHead>
                  <TableHead className="w-44">{t("cases.classification")}</TableHead>
                  <TableHead className="w-36">{t("cases.status")}</TableHead>
                  <TableHead className="w-28">{t("cases.risk")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((c) => (
                  <TableRow key={c.id} className="align-top">
                    <TableCell>
                      <Link href={`/casos/${c.id}`} className="font-mono text-sm text-primary hover:underline">{c.code}</Link>
                      <div className="text-[11px] text-muted-foreground">{fmtDate(c.created_at)}</div>
                    </TableCell>
                    <TableCell className="whitespace-normal">
                      <Link href={`/casos/${c.id}`} className="line-clamp-2 text-sm hover:underline">{c.post_text}</Link>
                      <div className="mt-0.5 text-xs text-muted-foreground">{c.source_name ?? tEnum("origin", "manual")} · {tEnum("network", c.network ?? "otra")}</div>
                    </TableCell>
                    <TableCell><AlertBadge level={c.alert_level} ratio={c.alert_ratio} /></TableCell>
                    <TableCell className="text-xs">
                      <div>{tEnum("stance", c.stance)} · {topics.bySlug.get(c.topic_slug ?? "")?.name ?? c.topic_slug}</div>
                      <div className="text-muted-foreground">{tEnum("message_type", c.message_type)}</div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {c.flow ? <Badge variant="outline">{c.flow}</Badge> : null}
                        {c.canalizar_a_atencion ? <Badge variant="secondary">{t("cases.canalizar")}</Badge> : null}
                        {c.legal_required ? <Badge variant="outline" className="border-veda/50 text-veda">{t("cases.legal")}: {tEnum("legal_status", c.legal_status)}</Badge> : null}
                      </div>
                    </TableCell>
                    <TableCell>
                      <CaseStatusBadge status={c.status} />
                      {c.recommendation && c.status === "interpretado" ? <div className="mt-1 text-[11px] text-muted-foreground">{t("cases.recommendation")}: {tEnum("recommendation", c.recommendation)}</div> : null}
                    </TableCell>
                    <TableCell><RiskMeter score={c.risk_score} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
