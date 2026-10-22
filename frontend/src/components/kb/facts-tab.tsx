"use client";

import { CheckCircle2, FileUp, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState, ErrorState, Loading, Pagination } from "@/components/app/common";
import { FormDialog, type FieldSpec } from "@/components/app/form-dialog";
import { useSession } from "@/components/app/session";
import { SourceBadge } from "@/components/app/source-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { enumOptions, fmtDay, fmtNum, t } from "@/i18n";
import { api, ApiError, qs, refresh, useApi, type Schemas } from "@/lib/api/client";
import { useDocuments, useLevels, useTopics } from "@/lib/hooks";

type Fact = Schemas["FactOut"];
const ALL = "__all__";

export function FactsTab() {
  const { can } = useSession();
  const topics = useTopics();
  const levels = useLevels();
  const docs = useDocuments();
  const [q, setQ] = useState("");
  const [topic, setTopic] = useState(ALL);
  const [level, setLevel] = useState(ALL);
  const [status, setStatus] = useState(ALL);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Fact | null | "new">(null);
  const [importOpen, setImportOpen] = useState(false);

  const path = `/kb/facts${qs({ q, page, page_size: 25, topic_id: topic === ALL ? null : topic, gov_level_id: level === ALL ? null : level, status: status === ALL ? null : status })}`;
  const { data, error, isLoading, mutate } = useApi<Schemas["Page_FactOut_"]>(path);

  const fields: FieldSpec[] = [
    { name: "statement", label: t("kb.facts.statement"), type: "textarea", required: true, rows: 2 },
    { name: "value", label: t("kb.facts.value"), type: "number", colSpan: 1 },
    { name: "unit", label: t("kb.facts.unit"), colSpan: 1 },
    { name: "base", label: t("kb.facts.base"), colSpan: 1 },
    { name: "period_label", label: t("kb.facts.periodLabel"), colSpan: 1 },
    { name: "period_start", label: t("kb.facts.periodStart"), type: "date", colSpan: 1 },
    { name: "period_end", label: t("kb.facts.periodEnd"), type: "date", colSpan: 1 },
    { name: "fact_date", label: t("kb.facts.factDate"), type: "date", colSpan: 1 },
    { name: "valid_until", label: t("kb.facts.validity"), type: "date", colSpan: 1 },
    { name: "document_id", label: t("kb.facts.document"), type: "select", options: docs.options },
    { name: "gov_level_id", label: t("kb.facts.level"), type: "select", options: levels.options, colSpan: 1 },
    { name: "topic_id", label: t("kb.facts.topic"), type: "select", options: topics.options, colSpan: 1 },
    { name: "notes", label: t("kb.facts.notes"), type: "textarea", rows: 2 },
  ];

  async function verify(f: Fact) {
    try {
      await api.post(`/kb/facts/${f.id}/verify`);
      await mutate();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : String(err));
    }
  }

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input className="w-64" placeholder={t("common.searchPlaceholder")} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <Select value={topic} onValueChange={(v) => { setTopic(v); setPage(1); }}>
          <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("kb.facts.allTopics")}</SelectItem>
            {topics.options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={level} onValueChange={(v) => { setLevel(v); setPage(1); }}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("kb.facts.allLevels")}</SelectItem>
            {levels.options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={(v) => { setStatus(v); setPage(1); }}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("kb.facts.allStatus")}</SelectItem>
            {enumOptions("fact_status").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <div className="ml-auto flex gap-2">
          {can("kb.curate") ? (
            <>
              <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}><FileUp />{t("kb.facts.import")}</Button>
              <Button size="sm" onClick={() => setEditing("new")}><Plus />{t("kb.facts.new")}</Button>
            </>
          ) : null}
        </div>
      </div>
      {isLoading ? <Loading /> : error ? <ErrorState error={error} onRetry={() => mutate()} /> : !data?.items.length ? <EmptyState /> : (
        <>
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-20">{t("kb.facts.code")}</TableHead>
                  <TableHead>{t("kb.facts.statement")}</TableHead>
                  <TableHead className="w-32 text-right">{t("kb.facts.value")}</TableHead>
                  <TableHead className="w-40">{t("kb.facts.period")}</TableHead>
                  <TableHead className="min-w-56">{t("kb.facts.source")}</TableHead>
                  <TableHead className="w-28">{t("kb.facts.level")}</TableHead>
                  <TableHead className="w-36">{t("kb.facts.verified")}</TableHead>
                  <TableHead className="w-28">{t("kb.facts.validity")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((f) => (
                  <TableRow key={f.id} className="align-top">
                    <TableCell><SourceBadge fact={f} /></TableCell>
                    <TableCell className="min-w-[22rem] whitespace-normal text-sm">
                      <button className="text-left hover:underline" disabled={!can("kb.curate")} onClick={() => setEditing(f)}>{f.statement}</button>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">{f.value !== null && f.value !== undefined ? `${fmtNum(f.value)} ${f.unit}` : t("common.none")}</TableCell>
                    <TableCell className="whitespace-normal text-xs">{f.period_label || t("common.none")}</TableCell>
                    <TableCell className="whitespace-normal text-xs">
                      {f.document ? <span>{f.document.title} · {fmtDay(f.document.issued_at ?? f.fact_date)}</span> : <Badge variant="outline" className="border-status-warn/60 text-status-warn">{t("kb.facts.noDocument")}</Badge>}
                    </TableCell>
                    <TableCell className="text-xs">{f.gov_level_name ?? t("common.none")}</TableCell>
                    <TableCell className="text-xs">
                      {f.verified_at ? (
                        <span className="inline-flex items-start gap-1 text-status-ok"><CheckCircle2 className="mt-0.5 size-3.5 shrink-0" /><span className="whitespace-normal">{t("kb.facts.verifiedBy", { name: (f.verified_by_name ?? "").split(" (")[0] })}</span></span>
                      ) : can("fact.verify") ? (
                        <Button size="xs" variant="outline" onClick={() => verify(f)}>{t("kb.facts.verify")}</Button>
                      ) : (
                        <span className="text-muted-foreground">{t("kb.facts.notVerified")}</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs">
                      {f.expired ? <Badge variant="destructive">{t("kb.facts.expired")}</Badge> : f.valid_until ? t("kb.facts.validUntil", { date: fmtDay(f.valid_until) }) : t("kb.facts.noExpiry")}
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
        title={editing === "new" ? t("kb.facts.new") : editing ? editing.code : ""}
        fields={fields}
        wide
        initial={editing && editing !== "new" ? { ...editing, document_id: editing.document_id ? String(editing.document_id) : null, gov_level_id: editing.gov_level_id ? String(editing.gov_level_id) : null, topic_id: editing.topic_id ? String(editing.topic_id) : null } : { base: "total" }}
        onSubmit={async (v) => {
          const body = { ...v, document_id: v.document_id ? Number(v.document_id) : null, gov_level_id: v.gov_level_id ? Number(v.gov_level_id) : null, topic_id: v.topic_id ? Number(v.topic_id) : null };
          if (editing === "new") await api.post("/kb/facts", body);
          else if (editing) await api.patch(`/kb/facts/${editing.id}`, body);
          await refresh("/kb/");
        }}
      />
      <ImportDialog open={importOpen} onOpenChange={setImportOpen} onDone={() => refresh("/kb/")} />
    </div>
  );
}

function ImportDialog({ open, onOpenChange, onDone }: { open: boolean; onOpenChange: (o: boolean) => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<Schemas["ImportReport"] | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setResult(null); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("kb.facts.importTitle")}</DialogTitle>
          <DialogDescription>{t("kb.facts.importHelp")}</DialogDescription>
        </DialogHeader>
        <Input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        {result ? (
          <div className="grid gap-1 text-sm">
            <p>{t("kb.facts.importResult", { created: result.created, updated: result.updated ?? 0, errors: result.errors?.length ?? 0 })}</p>
            {(result.errors ?? []).map((e, i) => <p key={i} className="text-xs text-status-block">{`L${String(e.line)}: ${String(e.error)}`}</p>)}
          </div>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t("common.close")}</Button>
          <Button
            disabled={!file || busy}
            onClick={async () => {
              if (!file) return;
              setBusy(true);
              try {
                const fd = new FormData();
                fd.append("file", file);
                setResult(await api.upload<Schemas["ImportReport"]>("/kb/facts/import", fd));
                onDone();
              } catch (err) {
                toast.error(err instanceof ApiError ? err.message : String(err));
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("common.import")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
