"use client";

import { useState } from "react";

import { EmptyState, ErrorState, JsonBlock, Loading, PageHeader, Pagination } from "@/components/app/common";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtDate, t } from "@/i18n";
import { qs, useApi, type Schemas } from "@/lib/api/client";

export default function AuditPage() {
  const [page, setPage] = useState(1);
  const [entity, setEntity] = useState("");
  const [action, setAction] = useState("");
  const { data, error, isLoading, mutate } = useApi<Schemas["Page_AuditOut_"]>(
    `/audit${qs({ page, page_size: 40, entity_type: entity, action })}`,
  );

  return (
    <div>
      <PageHeader title={t("audit.title")} subtitle={t("audit.subtitle")} />
      <div className="mb-3 flex flex-wrap gap-2">
        <Input className="w-56" placeholder={t("audit.filterEntity")} value={entity} onChange={(e) => { setEntity(e.target.value); setPage(1); }} />
        <Input className="w-56" placeholder={t("audit.filterAction")} value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} />
      </div>
      {isLoading ? <Loading /> : error ? <ErrorState error={error} onRetry={() => mutate()} /> : !data?.items.length ? <EmptyState /> : (
        <>
          <div className="rounded-lg border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-40">{t("audit.when")}</TableHead>
                  <TableHead>{t("audit.who")}</TableHead>
                  <TableHead>{t("audit.action")}</TableHead>
                  <TableHead>{t("audit.entity")}</TableHead>
                  <TableHead>{t("audit.before")}</TableHead>
                  <TableHead>{t("audit.after")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((row) => (
                  <TableRow key={row.id} className="align-top">
                    <TableCell className="whitespace-nowrap text-xs">{fmtDate(row.created_at)}</TableCell>
                    <TableCell className="text-xs">{row.user_label}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="font-mono">{row.action}</Badge>
                      {row.note ? <p className="mt-1 max-w-56 text-xs text-muted-foreground">{row.note}</p> : null}
                    </TableCell>
                    <TableCell className="text-xs">
                      {row.entity_type}
                      {row.entity_id ? ` #${row.entity_id}` : ""}
                    </TableCell>
                    <TableCell className="max-w-72"><JsonBlock value={row.before} /></TableCell>
                    <TableCell className="max-w-72"><JsonBlock value={row.after} /></TableCell>
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
