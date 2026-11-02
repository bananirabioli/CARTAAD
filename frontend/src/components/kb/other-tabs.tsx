"use client";

import { ExternalLink, Pencil, Plus, Upload } from "lucide-react";
import { useState } from "react";

import { EmptyState, Loading } from "@/components/app/common";
import { FormDialog, toFormData, type FieldSpec } from "@/components/app/form-dialog";
import { Markdown } from "@/components/app/markdown";
import { useSession } from "@/components/app/session";
import { ExtractFromDocButton } from "@/components/kb/review-tab";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { enumOptions, fmtDate, fmtDay, fmtNum, t, tEnum } from "@/i18n";
import { api, fileUrl, refresh, useApi, type Schemas } from "@/lib/api/client";
import { useLevels, useTopics } from "@/lib/hooks";

// ------------------------------------------------------------------ documents

export function DocumentsTab() {
  const { can } = useSession();
  const topics = useTopics();
  const levels = useLevels();
  const { data, isLoading } = useApi<Schemas["DocumentOut"][]>("/kb/documents");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);
  const { data: detail } = useApi<Schemas["DocumentDetail"]>(detailId ? `/kb/documents/${detailId}` : null);

  const fields: FieldSpec[] = [
    { name: "file", label: "PDF", type: "file", accept: "application/pdf", required: true },
    { name: "title", label: t("kb.documents.titleField"), required: true },
    { name: "issuer", label: t("kb.documents.issuer"), colSpan: 1 },
    { name: "doc_type", label: t("kb.documents.docType"), colSpan: 1 },
    { name: "issued_at", label: t("kb.documents.issuedAt"), type: "date", colSpan: 1 },
    { name: "url", label: t("kb.documents.url"), colSpan: 1 },
    { name: "gov_level_id", label: t("kb.facts.level"), type: "select", options: levels.options, colSpan: 1 },
    { name: "topic_id", label: t("kb.facts.topic"), type: "select", options: topics.options, colSpan: 1 },
  ];

  return (
    <div className="grid gap-3">
      {can("kb.curate") ? (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setUploadOpen(true)}><Upload />{t("kb.documents.upload")}</Button>
        </div>
      ) : null}
      {isLoading ? <Loading /> : !data?.length ? <EmptyState /> : (
        <div className="grid gap-2 md:grid-cols-2">
          {data.map((d) => (
            <Card key={d.id} className="gap-2 py-4">
              <CardHeader className="px-4">
                <CardTitle className="text-sm">{d.title}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center gap-2 px-4 text-xs text-muted-foreground">
                <span>{d.issuer}</span>
                <span>· {fmtDay(d.issued_at)}</span>
                <Badge variant="secondary">{d.doc_type}</Badge>
                <Badge variant={d.status === "procesado" ? "outline" : "destructive"}>{tEnum("doc_status", d.status)}</Badge>
                <span>{t("kb.documents.chunks", { count: d.chunk_count ?? 0 })}</span>
                <span>{t("kb.documents.facts", { count: d.fact_count ?? 0 })}</span>
                <div className="ml-auto flex gap-1">
                  <Button size="xs" variant="outline" onClick={() => setDetailId(d.id)}>{t("kb.documents.viewChunks")}</Button>
                  {can("kb.curate") ? <ExtractFromDocButton docId={d.id} disabled={d.status !== "procesado"} /> : null}
                  {d.file_key ? (
                    <Button size="xs" variant="ghost" asChild>
                      <a href={fileUrl(d.file_key)} target="_blank" rel="noreferrer"><ExternalLink />{t("kb.documents.openPdf")}</a>
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <FormDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        title={t("kb.documents.uploadTitle")}
        fields={fields}
        initial={{ doc_type: "informe" }}
        onSubmit={async (v) => {
          await api.upload("/kb/documents", toFormData(v));
          await refresh("/kb/");
        }}
      />
      <Sheet open={detailId !== null} onOpenChange={(o) => !o && setDetailId(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>{detail?.title}</SheetTitle>
            <SheetDescription>{detail ? t("kb.documents.pages", { count: detail.pages }) : null}</SheetDescription>
          </SheetHeader>
          <div className="grid gap-2 px-4 pb-6">
            {detail?.chunks?.map((c) => (
              <div key={c.id} className="rounded border bg-muted/40 p-2 text-xs">
                <div className="mb-1 font-mono text-[10px] text-muted-foreground">#{c.ord} · {t("kb.documents.page", { page: c.page })}</div>
                {c.text}
              </div>
            ))}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

// ------------------------------------------------------------------ briefs

export function BriefsTab() {
  const { can } = useSession();
  const topics = useTopics();
  const { data, isLoading } = useApi<Schemas["BriefOut"][]>("/kb/briefs");
  const [editing, setEditing] = useState<Schemas["BriefOut"] | "new" | null>(null);
  const fields: FieldSpec[] = [
    { name: "title", label: t("kb.briefs.titleField"), required: true },
    { name: "topic_id", label: t("kb.facts.topic"), type: "select", options: topics.options },
    { name: "body_md", label: t("kb.briefs.body"), type: "textarea", rows: 14 },
  ];
  return (
    <div className="grid gap-3">
      {can("kb.curate") ? (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setEditing("new")}><Plus />{t("kb.briefs.new")}</Button>
        </div>
      ) : null}
      {isLoading ? <Loading /> : !data?.length ? <EmptyState /> : (
        <div className="grid gap-3 md:grid-cols-2">
          {data.map((b) => (
            <Card key={b.id} className="gap-2">
              <CardHeader className="flex flex-row items-start justify-between gap-2">
                <div>
                  <CardTitle className="text-sm">{b.title}</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {b.topic_id ? topics.byId.get(b.topic_id)?.name : t("kb.messages.general")} · {t("kb.briefs.updated", { date: fmtDate(b.updated_at) })}
                  </p>
                </div>
                {can("kb.curate") ? <Button size="icon-xs" variant="ghost" onClick={() => setEditing(b)} aria-label={t("kb.briefs.edit")}><Pencil /></Button> : null}
              </CardHeader>
              <CardContent><Markdown source={b.body_md} /></CardContent>
            </Card>
          ))}
        </div>
      )}
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={editing === "new" ? t("kb.briefs.new") : t("kb.briefs.edit")}
        fields={fields}
        wide
        initial={editing && editing !== "new" ? { ...editing, topic_id: editing.topic_id ? String(editing.topic_id) : null } : {}}
        onSubmit={async (v) => {
          const body = { ...v, topic_id: v.topic_id ? Number(v.topic_id) : null };
          if (editing === "new") await api.post("/kb/briefs", body);
          else if (editing) await api.put(`/kb/briefs/${editing.id}`, body);
          await refresh("/kb/");
        }}
      />
    </div>
  );
}

// ------------------------------------------------------------------ key messages

export function MessagesTab() {
  const { can } = useSession();
  const topics = useTopics();
  const { data, isLoading } = useApi<Schemas["KeyMessageOut"][]>("/kb/key-messages");
  const [editing, setEditing] = useState<Schemas["KeyMessageOut"] | "new" | null>(null);
  const fields: FieldSpec[] = [
    { name: "text", label: t("kb.messages.text"), type: "textarea", required: true, rows: 3 },
    { name: "topic_id", label: t("kb.facts.topic"), type: "select", options: topics.options, colSpan: 1 },
    { name: "priority", label: t("kb.messages.priority"), type: "number", colSpan: 1 },
    { name: "tone_note", label: t("kb.messages.tone") },
    { name: "active", label: t("common.active"), type: "checkbox" },
  ];
  return (
    <div className="grid gap-3">
      {can("kb.curate") ? (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setEditing("new")}><Plus />{t("kb.messages.new")}</Button>
        </div>
      ) : null}
      {isLoading ? <Loading /> : !data?.length ? <EmptyState /> : (
        <div className="rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("kb.messages.text")}</TableHead>
                <TableHead className="w-40">{t("kb.facts.topic")}</TableHead>
                <TableHead className="w-24">{t("kb.messages.priority")}</TableHead>
                <TableHead className="w-24">{t("common.status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="whitespace-normal">
                    <button className="text-left hover:underline" disabled={!can("kb.curate")} onClick={() => setEditing(m)}>{m.text}</button>
                  </TableCell>
                  <TableCell className="text-xs">{m.topic_id ? topics.byId.get(m.topic_id)?.name : t("kb.messages.general")}</TableCell>
                  <TableCell className="text-xs">{m.priority}</TableCell>
                  <TableCell><Badge variant={m.active ? "outline" : "secondary"}>{m.active ? t("common.active") : t("common.inactive")}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={t("kb.messages.new")}
        fields={fields}
        initial={editing && editing !== "new" ? { ...editing, topic_id: editing.topic_id ? String(editing.topic_id) : null } : { priority: 50, active: true }}
        onSubmit={async (v) => {
          const body = { ...v, topic_id: v.topic_id ? Number(v.topic_id) : null, priority: Number(v.priority ?? 50) };
          if (editing === "new") await api.post("/kb/key-messages", body);
          else if (editing) await api.put(`/kb/key-messages/${editing.id}`, body);
          await refresh("/kb/");
        }}
      />
    </div>
  );
}

// ------------------------------------------------------------------ actors

export function ActorsTab() {
  const { can } = useSession();
  const levels = useLevels();
  const { data, isLoading } = useApi<Schemas["ActorOut"][]>("/kb/actors");
  const [editing, setEditing] = useState<Schemas["ActorOut"] | "new" | null>(null);
  const fields: FieldSpec[] = [
    { name: "name", label: t("kb.actors.name"), required: true },
    { name: "aliases", label: t("kb.actors.aliases"), type: "tags" },
    { name: "actor_type", label: t("kb.actors.type"), type: "select", options: enumOptions("actor_type"), required: true, colSpan: 1 },
    { name: "gov_level_id", label: t("kb.facts.level"), type: "select", options: levels.options, colSpan: 1 },
    { name: "is_own", label: t("kb.actors.own"), type: "checkbox" },
    { name: "notes", label: t("kb.actors.notes"), type: "textarea", rows: 2 },
  ];
  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">{t("kb.actors.help")}</p>
        {can("kb.curate") ? <Button size="sm" onClick={() => setEditing("new")}><Plus />{t("kb.actors.new")}</Button> : null}
      </div>
      {isLoading ? <Loading /> : !data?.length ? <EmptyState /> : (
        <div className="rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("kb.actors.name")}</TableHead>
                <TableHead>{t("kb.actors.aliases")}</TableHead>
                <TableHead className="w-44">{t("kb.actors.type")}</TableHead>
                <TableHead className="w-32">{t("kb.facts.level")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>
                    <button className="text-left font-medium hover:underline" disabled={!can("kb.curate")} onClick={() => setEditing(a)}>{a.name}</button>
                    {a.is_own ? <Badge variant="secondary" className="ml-2">{t("kb.actors.own")}</Badge> : null}
                  </TableCell>
                  <TableCell className="whitespace-normal">
                    <div className="flex flex-wrap gap-1">{a.aliases.map((al) => <Badge key={al} variant="outline">{al}</Badge>)}</div>
                  </TableCell>
                  <TableCell className="text-xs">{tEnum("actor_type", a.actor_type)}</TableCell>
                  <TableCell className="text-xs">{a.gov_level_id ? levels.byId.get(a.gov_level_id)?.name : t("common.none")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={editing === "new" ? t("kb.actors.new") : editing ? editing.name : ""}
        fields={fields}
        initial={editing && editing !== "new" ? { ...editing, gov_level_id: editing.gov_level_id ? String(editing.gov_level_id) : null } : { actor_type: "otro" }}
        onSubmit={async (v) => {
          const body = { ...v, gov_level_id: v.gov_level_id ? Number(v.gov_level_id) : null };
          if (editing === "new") await api.post("/kb/actors", body);
          else if (editing) await api.put(`/kb/actors/${editing.id}`, body);
          await refresh("/kb/");
        }}
      />
    </div>
  );
}

// ------------------------------------------------------------------ competences

export function CompetencesTab() {
  const { can } = useSession();
  const topics = useTopics();
  const levels = useLevels();
  const { data, isLoading } = useApi<Schemas["CompetenceOut"][]>("/kb/competences");
  const [editing, setEditing] = useState<Schemas["CompetenceOut"] | "new" | null>(null);
  const fields: FieldSpec[] = [
    { name: "gov_level_id", label: t("kb.competences.level"), type: "select", options: levels.options, required: true, colSpan: 1 },
    { name: "topic_id", label: t("kb.competences.topic"), type: "select", options: topics.options, colSpan: 1 },
    { name: "description", label: t("kb.competences.description"), type: "textarea", required: true, rows: 3 },
    { name: "legal_basis", label: t("kb.competences.legalBasis") },
  ];
  if (isLoading) return <Loading />;
  const rows = topics.list;
  return (
    <div className="grid gap-3">
      {can("kb.curate") ? (
        <div className="flex justify-end"><Button size="sm" onClick={() => setEditing("new")}><Plus />{t("kb.competences.new")}</Button></div>
      ) : null}
      <div className="overflow-x-auto rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-36">{t("kb.competences.topic")}</TableHead>
              {levels.list.map((l) => <TableHead key={l.id}>{l.name}</TableHead>)}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((topic) => (
              <TableRow key={topic.id} className="align-top">
                <TableCell className="font-medium">{topic.name}</TableCell>
                {levels.list.map((l) => (
                  <TableCell key={l.id} className="whitespace-normal text-xs">
                    {(data ?? []).filter((c) => c.topic_id === topic.id && c.gov_level_id === l.id).map((c) => (
                      <button key={c.id} className="mb-1 block text-left hover:underline" disabled={!can("kb.curate")} onClick={() => setEditing(c)}>
                        {c.description}
                        {c.legal_basis ? <span className="block text-[10px] text-muted-foreground">{c.legal_basis}</span> : null}
                      </button>
                    ))}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={t("kb.competences.new")}
        fields={fields}
        initial={editing && editing !== "new" ? { ...editing, gov_level_id: String(editing.gov_level_id), topic_id: editing.topic_id ? String(editing.topic_id) : null } : {}}
        onSubmit={async (v) => {
          const body = { ...v, gov_level_id: Number(v.gov_level_id), topic_id: v.topic_id ? Number(v.topic_id) : null };
          if (editing === "new") await api.post("/kb/competences", body);
          else if (editing) await api.put(`/kb/competences/${editing.id}`, body);
          await refresh("/kb/");
        }}
      />
    </div>
  );
}

// ------------------------------------------------------------------ images

export function ImagesTab() {
  const { can } = useSession();
  const topics = useTopics();
  const { data, isLoading } = useApi<Schemas["ImageOut"][]>("/kb/images");
  const [uploadOpen, setUploadOpen] = useState(false);
  const fields: FieldSpec[] = [
    { name: "file", label: t("common.upload"), type: "file", accept: "image/png,image/jpeg,image/webp", required: true },
    { name: "title", label: t("kb.documents.titleField"), required: true },
    { name: "image_type", label: t("kb.images.type"), type: "select", options: enumOptions("image_type"), required: true, colSpan: 1 },
    { name: "topic_id", label: t("kb.facts.topic"), type: "select", options: topics.options, colSpan: 1 },
    { name: "credit", label: t("kb.images.credit"), help: t("kb.images.creditRequired") },
    { name: "license", label: t("kb.images.license"), colSpan: 1 },
    { name: "taken_at", label: t("kb.images.takenAt"), type: "date", colSpan: 1 },
    { name: "tags", label: t("kb.images.tags"), type: "tags" },
  ];
  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">{t("kb.images.notEvidence")}</p>
        {can("assets.upload") ? <Button size="sm" onClick={() => setUploadOpen(true)}><Upload />{t("kb.images.upload")}</Button> : null}
      </div>
      {isLoading ? <Loading /> : !data?.length ? <EmptyState /> : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
          {data.map((img) => (
            <Card key={img.id} className="gap-0 overflow-hidden py-0">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={fileUrl(img.file_key)} alt={img.title} className="aspect-[3/2] w-full object-cover" />
              <CardContent className="grid gap-1 p-3 text-xs">
                <p className="text-sm font-medium leading-snug">{img.title}</p>
                <div className="flex flex-wrap gap-1">
                  <Badge variant={img.image_type === "foto_real" ? "default" : "secondary"}>{tEnum("image_type", img.image_type)}</Badge>
                  {img.tags.map((tag) => <Badge key={tag} variant="outline">{tag}</Badge>)}
                </div>
                <p className="text-muted-foreground">{img.credit || t("common.none")} · {img.license}</p>
                <p className="text-muted-foreground">{fmtDay(img.taken_at)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <FormDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        title={t("kb.images.uploadTitle")}
        fields={fields}
        initial={{ image_type: "foto_real" }}
        onSubmit={async (v) => {
          await api.upload("/kb/images", toFormData(v));
          await refresh("/kb/");
        }}
      />
    </div>
  );
}

// ------------------------------------------------------------------ history

export function HistoryTab() {
  const { data, isLoading } = useApi<Schemas["HistoryOut"][]>("/kb/history");
  if (isLoading) return <Loading />;
  if (!data?.length) return <EmptyState />;
  return (
    <div className="rounded-lg border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("kb.history.date")}</TableHead>
            <TableHead>{t("kb.history.topic")}</TableHead>
            <TableHead>{t("kb.history.format")}</TableHead>
            <TableHead>{t("kb.history.style")}</TableHead>
            <TableHead>{t("kb.history.strategy")}</TableHead>
            <TableHead>{t("kb.history.creative")}</TableHead>
            <TableHead>{t("kb.history.outcome")}</TableHead>
            <TableHead className="text-right">{t("kb.history.reach")}</TableHead>
            <TableHead className="text-right">{t("kb.history.sentiment")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((h) => (
            <TableRow key={h.id}>
              <TableCell className="text-xs">{fmtDay(h.created_at)}</TableCell>
              <TableCell className="text-xs">{h.topic_slug}</TableCell>
              <TableCell className="text-xs">{tEnum("format", h.format_slug)}</TableCell>
              <TableCell><Badge variant="outline">{h.style_slug}</Badge></TableCell>
              <TableCell className="text-xs">{tEnum("strategy", h.strategy)}</TableCell>
              <TableCell className="text-xs">{tEnum("creative", h.creative_slug)}</TableCell>
              <TableCell>
                <Badge className={h.outcome === "funciono" ? "bg-status-ok text-white" : "bg-status-block text-white"}>{tEnum("outcome", h.outcome)}</Badge>
              </TableCell>
              <TableCell className="text-right font-mono text-xs">{h.reach_ratio !== null && h.reach_ratio !== undefined ? `${fmtNum(h.reach_ratio, 1)}×` : t("common.none")}</TableCell>
              <TableCell className="text-right font-mono text-xs">{h.sentiment_delta !== null && h.sentiment_delta !== undefined ? fmtNum(h.sentiment_delta, 2) : t("common.none")}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
