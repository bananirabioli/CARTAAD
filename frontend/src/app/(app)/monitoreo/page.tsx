"use client";

import { CheckCheck, FileUp, Plus, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AlertBadge } from "@/components/app/badges";
import { EmptyState, ErrorState, Loading, PageHeader, Pagination } from "@/components/app/common";
import { PostSheet } from "@/components/monitoring/post-sheet";
import { FormDialog, toFormData, type FieldSpec } from "@/components/app/form-dialog";
import { useSession } from "@/components/app/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { enumOptions, fmtDate, fmtNum, t, tEnum } from "@/i18n";
import { api, ApiError, qs, refresh, useApi, type Schemas } from "@/lib/api/client";

const ALL = "__all__";
type Source = Schemas["SourceOut"];

function FilterSelect({ value, onChange, allLabel, options }: { value: string; onChange: (v: string) => void; allLabel: string; options: { value: string; label: string }[] }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{allLabel}</SelectItem>
        {options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

const sourceFields: FieldSpec[] = [
  { name: "name", label: t("monitoring.name"), required: true },
  { name: "network", label: t("monitoring.network"), type: "select", options: enumOptions("network"), required: true, colSpan: 1 },
  { name: "handle", label: t("monitoring.handle"), colSpan: 1 },
  { name: "url", label: t("monitoring.url") },
  { name: "source_type", label: t("monitoring.type"), type: "select", options: enumOptions("source_type"), required: true, colSpan: 1 },
  { name: "priority", label: t("monitoring.priority"), type: "select", options: enumOptions("priority"), required: true, colSpan: 1 },
  { name: "check_frequency_minutes", label: t("monitoring.frequency"), type: "number", colSpan: 1 },
  { name: "adapter", label: t("monitoring.adapter"), type: "select", options: enumOptions("adapter"), required: true, colSpan: 1 },
  { name: "active", label: t("monitoring.active"), type: "checkbox" },
  { name: "notes", label: t("monitoring.notes"), type: "textarea", rows: 2 },
];

function SourcesTab() {
  const { can } = useSession();
  const [q, setQ] = useState("");
  const [network, setNetwork] = useState(ALL);
  const [type, setType] = useState(ALL);
  const [priority, setPriority] = useState(ALL);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Source | "new" | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const v = (x: string) => (x === ALL ? null : x);
  const { data, error, isLoading, mutate } = useApi<Schemas["Page_SourceOut_"]>(
    `/sources${qs({ q, network: v(network), source_type: v(type), priority: v(priority), page, page_size: 25 })}`,
  );

  async function check(s: Source) {
    setBusyId(s.id);
    try {
      const r = await api.post<Schemas["CheckResult"]>(`/sources/${s.id}/check`);
      toast.success(`${s.name}: ${t("monitoring.checked", { created: r.created, updated: r.updated })}`);
      await refresh("/sources", "/posts");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input className="w-56" placeholder={t("common.searchPlaceholder")} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <FilterSelect value={network} onChange={(x) => { setNetwork(x); setPage(1); }} allLabel={t("monitoring.allNetworks")} options={enumOptions("network")} />
        <FilterSelect value={type} onChange={(x) => { setType(x); setPage(1); }} allLabel={t("monitoring.allTypes")} options={enumOptions("source_type")} />
        <FilterSelect value={priority} onChange={(x) => { setPriority(x); setPage(1); }} allLabel={t("monitoring.allPriorities")} options={enumOptions("priority")} />
        {can("sources.manage") ? (
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="ghost" onClick={async () => { await api.post("/settings/sources-reviewed"); toast.success(t("common.saved")); }}><CheckCheck />{t("monitoring.reviewed")}</Button>
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}><FileUp />{t("monitoring.importCsv")}</Button>
            <Button size="sm" onClick={() => setEditing("new")}><Plus />{t("monitoring.newSource")}</Button>
          </div>
        ) : null}
      </div>
      {isLoading ? <Loading /> : error ? <ErrorState error={error} onRetry={() => mutate()} /> : !data?.items.length ? <EmptyState /> : (
        <>
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("monitoring.name")}</TableHead>
                  <TableHead>{t("monitoring.network")}</TableHead>
                  <TableHead>{t("monitoring.type")}</TableHead>
                  <TableHead>{t("monitoring.priority")}</TableHead>
                  <TableHead className="text-right">{t("monitoring.baseline")}</TableHead>
                  <TableHead className="text-right">{t("monitoring.posts")}</TableHead>
                  <TableHead>{t("monitoring.lastChecked")}</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((s) => (
                  <TableRow key={s.id} className={s.active ? "" : "opacity-60"}>
                    <TableCell>
                      <button className="text-left font-medium hover:underline" disabled={!can("sources.manage")} onClick={() => setEditing(s)}>{s.name}</button>
                      <div className="text-xs text-muted-foreground">{s.handle} {!s.active ? `· ${t("common.inactive")}` : ""}</div>
                    </TableCell>
                    <TableCell className="text-xs">{tEnum("network", s.network)}</TableCell>
                    <TableCell className="text-xs">{tEnum("source_type", s.source_type)}</TableCell>
                    <TableCell><Badge variant={s.priority === "alta" ? "default" : "outline"}>{tEnum("priority", s.priority)}</Badge></TableCell>
                    <TableCell className="text-right text-xs">
                      {s.baseline_ok ? t("monitoring.baselinePerHour", { value: fmtNum(s.baseline_per_hour ?? 0, 1) }) : <Badge variant="outline" className="border-alert-sin-base/40 text-alert-sin-base">{t("monitoring.baselineInsufficient")}</Badge>}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">{s.posts_count}</TableCell>
                    <TableCell className="text-xs">{fmtDate(s.last_checked_at)}</TableCell>
                    <TableCell className="text-right">
                      {can("case.capture") ? (
                        <Button size="xs" variant="outline" disabled={busyId === s.id} onClick={() => check(s)}><RefreshCw className={busyId === s.id ? "animate-spin" : ""} />{t("monitoring.checkNow")}</Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={editing === "new" ? t("monitoring.newSource") : editing ? editing.name : ""}
        fields={sourceFields}
        initial={editing && editing !== "new" ? { ...editing } : { network: "facebook", source_type: "pagina_ciudadana", priority: "media", check_frequency_minutes: 60, adapter: "mock", active: true }}
        onSubmit={async (val) => {
          const body = { ...val, check_frequency_minutes: Number(val.check_frequency_minutes ?? 60) };
          if (editing === "new") await api.post("/sources", body);
          else if (editing) await api.patch(`/sources/${editing.id}`, body);
          await refresh("/sources");
        }}
      />
      <FormDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        title={t("monitoring.importCsv")}
        description={t("monitoring.importHelp")}
        fields={[{ name: "file", label: "CSV", type: "file", accept: ".csv,text/csv", required: true }]}
        submitLabel={t("common.import")}
        onSubmit={async (val) => {
          const r = await api.upload<Schemas["ImportReport"]>("/sources/import", toFormData(val));
          toast.success(`${r.created} / ${r.updated} · ${r.errors?.length ?? 0} errores`);
          await refresh("/sources");
        }}
      />
    </div>
  );
}

function PostsTab() {
  const { can } = useSession();
  const [q, setQ] = useState("");
  const [level, setLevel] = useState(ALL);
  const [origin, setOrigin] = useState(ALL);
  const [order, setOrder] = useState("recent");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const v = (x: string) => (x === ALL ? null : x);
  const { data, isLoading } = useApi<Schemas["Page_PostOut_"]>(`/posts${qs({ q, alert_level: v(level), origin: v(origin), order, page, page_size: 25 })}`);
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input className="w-56" placeholder={t("common.searchPlaceholder")} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <FilterSelect value={level} onChange={(x) => { setLevel(x); setPage(1); }} allLabel={t("monitoring.allLevels")} options={enumOptions("alert_level")} />
        <FilterSelect value={origin} onChange={(x) => { setOrigin(x); setPage(1); }} allLabel={t("monitoring.allOrigins")} options={enumOptions("origin")} />
        <Select value={order} onValueChange={setOrder}>
          <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="recent">{t("monitoring.orderRecent")}</SelectItem>
            <SelectItem value="velocity">{t("monitoring.orderVelocity")}</SelectItem>
            <SelectItem value="ratio">{t("monitoring.orderRatio")}</SelectItem>
          </SelectContent>
        </Select>
        {can("case.capture") ? <Button size="sm" variant="outline" className="ml-auto" onClick={() => setImportOpen(true)}><FileUp />{t("monitoring.importPosts")}</Button> : null}
      </div>
      {isLoading ? <Loading /> : !data?.items.length ? <EmptyState /> : (
        <>
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-36">{t("monitoring.published")}</TableHead>
                  <TableHead className="w-44">{t("monitoring.source")}</TableHead>
                  <TableHead>{t("monitoring.text")}</TableHead>
                  <TableHead className="w-40">{t("monitoring.alert")}</TableHead>
                  <TableHead className="w-24 text-right">{t("monitoring.velocity")}</TableHead>
                  <TableHead className="w-24">{t("monitoring.case")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((p) => (
                  <TableRow key={p.id} className="cursor-pointer align-top" onClick={() => setOpenId(p.id)}>
                    <TableCell className="text-xs">{fmtDate(p.published_at)}<div className="text-muted-foreground">{tEnum("origin", p.origin)}</div></TableCell>
                    <TableCell className="text-xs">{p.source_name ?? t("common.none")}<div className="text-muted-foreground">{tEnum("network", p.network)}</div></TableCell>
                    <TableCell className="max-w-xl whitespace-normal text-sm">{p.text}</TableCell>
                    <TableCell><AlertBadge level={p.alert_level} ratio={p.alert_ratio} /></TableCell>
                    <TableCell className="text-right font-mono text-xs">{t("monitoring.velocityValue", { value: fmtNum(p.velocity ?? 0, 1) })}</TableCell>
                    <TableCell className="text-xs" onClick={(e) => e.stopPropagation()}>
                      {p.case_id ? <Link className="text-primary hover:underline" href={`/casos/${p.case_id}`}>{p.case_code}</Link> : <span className="text-muted-foreground">{t("monitoring.noCase")}</span>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
      <PostSheet id={openId} onClose={() => setOpenId(null)} />
      <FormDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        title={t("monitoring.importPosts")}
        description={t("monitoring.importPostsHelp")}
        fields={[{ name: "file", label: "CSV / JSON", type: "file", accept: ".csv,.json", required: true }]}
        submitLabel={t("common.import")}
        onSubmit={async (val) => {
          const r = await api.upload<Schemas["ImportReport"]>("/posts/import", toFormData(val));
          toast.success(`${r.created} / ${r.updated} · ${r.errors?.length ?? 0} errores`);
          await refresh("/posts");
        }}
      />
    </div>
  );
}

export default function MonitoringPage() {
  return (
    <div>
      <PageHeader title={t("monitoring.title")} subtitle={t("monitoring.subtitle")} />
      <Tabs defaultValue="sources">
        <TabsList>
          <TabsTrigger value="sources">{t("monitoring.tabs.sources")}</TabsTrigger>
          <TabsTrigger value="posts">{t("monitoring.tabs.posts")}</TabsTrigger>
        </TabsList>
        <TabsContent value="sources" className="mt-3"><SourcesTab /></TabsContent>
        <TabsContent value="posts" className="mt-3"><PostsTab /></TabsContent>
      </Tabs>
    </div>
  );
}
