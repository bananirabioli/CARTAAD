"use client";

import { Plus, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Loading } from "@/components/app/common";
import { FormDialog } from "@/components/app/form-dialog";
import { useSession } from "@/components/app/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { enumOptions, t, tEnum } from "@/i18n";
import { api, ApiError, refresh, useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const MARK: Record<string, string> = { full: "✓", partial: "◐", none: "✗" };
const MARK_CLASS: Record<string, string> = {
  full: "bg-status-ok/10 text-status-ok",
  partial: "bg-status-warn/10 text-status-warn",
  none: "bg-muted text-muted-foreground",
};

export function MatrixTab() {
  const { can, me } = useSession();
  const veda = me?.restriction as { blocked_formats?: string[]; blocked_creatives?: string[]; name?: string } | null;
  const { data, isLoading } = useApi<Schemas["MatrixOut"]>("/catalog/matrix");
  const [editing, setEditing] = useState<Schemas["MatrixCell"] | null>(null);
  if (isLoading || !data) return <Loading />;
  const cell = (c: string, f: string) => data.cells.find((x) => x.creative_slug === c && x.format_slug === f);
  return (
    <div className="grid gap-3">
      <p className="text-xs text-muted-foreground">{t("matrix.help")}</p>
      <div className="overflow-x-auto rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="min-w-56">{t("matrix.creative")}</TableHead>
              {data.formats.map((f) => (
                <TableHead key={f.slug} className={cn("text-center text-xs", veda?.blocked_formats?.includes(f.slug) && "bg-veda/10")}>
                  {f.code}
                  <div className="font-normal text-muted-foreground">{f.name}</div>
                  {veda?.blocked_formats?.includes(f.slug) ? <div className="font-normal text-veda">{t("cases.blockedByVeda")}</div> : null}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.creatives.map((c) => (
              <TableRow key={c.slug}>
                <TableCell className="text-sm">
                  <span className="font-mono text-xs text-muted-foreground">{c.code}</span> {c.name}
                  <Badge variant="outline" className="ml-2 text-[10px]">{c.flow}</Badge>
                </TableCell>
                {data.formats.map((f) => {
                  const x = cell(c.slug, f.slug);
                  const level = x?.level ?? "none";
                  return (
                    <TableCell key={f.slug} className="p-1 text-center">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            disabled={!can("catalog.manage")}
                            onClick={() => setEditing(x ?? { creative_slug: c.slug, format_slug: f.slug, level: "none", note: "" })}
                            className={cn("w-full rounded px-2 py-1.5 text-base", MARK_CLASS[level])}
                          >
                            {MARK[level]}
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs text-xs">
                          <p className="font-medium">{tEnum("compat", level)}</p>
                          {x?.note ? <p>{x.note}</p> : null}
                        </TooltipContent>
                      </Tooltip>
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={editing ? `${t("matrix.editCell")} · ${tEnum("creative", editing.creative_slug)} × ${tEnum("format", editing.format_slug)}` : ""}
        fields={[
          { name: "level", label: t("matrix.level"), type: "select", options: enumOptions("compat"), required: true },
          { name: "note", label: t("matrix.note"), type: "textarea", rows: 3 },
        ]}
        initial={editing ?? {}}
        onSubmit={async (v) => {
          if (!editing) return;
          await api.put("/catalog/matrix", { ...editing, level: v.level, note: v.note ?? "" });
          await refresh("/catalog/matrix");
        }}
      />
    </div>
  );
}

export function TagsTab() {
  const { can } = useSession();
  const { data, isLoading } = useApi<Schemas["TagDimensionOut"][]>("/tags");
  const [adding, setAdding] = useState<number | null>(null);
  const [newDim, setNewDim] = useState(false);
  if (isLoading) return <Loading />;
  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">{t("tags.help")}</p>
        {can("catalog.manage") ? <Button size="sm" variant="outline" onClick={() => setNewDim(true)}><Plus />{t("tags.newDimension")}</Button> : null}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {(data ?? []).map((dim) => (
          <Card key={dim.id} className="gap-2 py-4">
            <CardHeader className="flex flex-row items-center justify-between px-4">
              <CardTitle className="text-sm">
                {dim.name} <span className="font-mono text-xs font-normal text-muted-foreground">{dim.slug}</span>
              </CardTitle>
              {can("catalog.manage") && dim.kind === "categorical" ? (
                <Button size="xs" variant="ghost" onClick={() => setAdding(dim.id)}><Plus />{t("tags.add")}</Button>
              ) : null}
            </CardHeader>
            <CardContent className="flex flex-wrap gap-1 px-4">
              {dim.tags.map((tag) => <Badge key={tag.id} variant="outline">{tag.name}</Badge>)}
            </CardContent>
          </Card>
        ))}
      </div>
      <FormDialog
        open={adding !== null}
        onOpenChange={(o) => !o && setAdding(null)}
        title={t("tags.add")}
        fields={[{ name: "slug", label: t("tags.slug"), required: true }, { name: "name", label: t("tags.name"), required: true }]}
        onSubmit={async (v) => {
          await api.post(`/tags/${adding}/values`, v);
          await refresh("/tags");
        }}
      />
      <FormDialog
        open={newDim}
        onOpenChange={setNewDim}
        title={t("tags.newDimension")}
        fields={[{ name: "slug", label: t("tags.slug"), required: true }, { name: "name", label: t("tags.name"), required: true }]}
        onSubmit={async (v) => {
          try {
            await api.post("/tags", { ...v, kind: "categorical" });
            await refresh("/tags");
          } catch (err) {
            toast.error(err instanceof ApiError ? err.message : String(err));
            throw err;
          }
        }}
      />
    </div>
  );
}

export function HardRulesTab() {
  const { data } = useApi<Schemas["HardRuleOut"][]>("/meta/hard-rules");
  return (
    <div className="grid gap-3">
      <p className="text-xs text-muted-foreground">{t("hardRules.help")}</p>
      <div className="grid gap-2 md:grid-cols-2">
        {(data ?? []).map((r) => (
          <Card key={r.id} className="gap-1 py-3">
            <CardHeader className="flex flex-row items-center gap-2 px-4">
              <ShieldCheck className="size-4 text-primary" />
              <CardTitle className="text-sm">
                <span className="font-mono">{r.id}</span> · {r.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 text-xs text-muted-foreground">{r.description}</CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
