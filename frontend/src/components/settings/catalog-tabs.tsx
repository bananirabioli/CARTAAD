"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { FormDialog, type FieldSpec } from "@/components/app/form-dialog";
import { useSession } from "@/components/app/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { t } from "@/i18n";
import { api, refresh, useApi, type Schemas } from "@/lib/api/client";
import { useTopics } from "@/lib/hooks";

// Moved from Configuración: in the MVP topics, formats and creatives live under Catálogos.

export function TopicsTab() {
  const { can } = useSession();
  const topics = useTopics();
  const [editing, setEditing] = useState<Schemas["TopicOut"] | "new" | null>(null);
  return (
    <div className="grid gap-3">
      {can("catalog.manage") ? <div className="flex justify-end"><Button size="sm" onClick={() => setEditing("new")}><Plus />{t("settings.topics.new")}</Button></div> : null}
      <div className="grid gap-2 md:grid-cols-2">
        {topics.list.map((tp) => (
          <Card key={tp.id} className="gap-1 py-3"><CardContent className="grid gap-1 px-4">
            <button className="text-left text-sm font-medium hover:underline" disabled={!can("catalog.manage")} onClick={() => setEditing(tp)}>{tp.name} <span className="font-mono text-xs text-muted-foreground">{tp.slug}</span></button>
            <div className="flex flex-wrap gap-1">{tp.keywords.map((k) => <Badge key={k} variant="outline">{k}</Badge>)}</div>
          </CardContent></Card>
        ))}
      </div>
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={editing === "new" ? t("settings.topics.new") : editing ? editing.name : ""}
        fields={[...(editing === "new" ? [{ name: "slug", label: t("settings.topics.slug"), required: true } as FieldSpec] : []), { name: "name", label: t("settings.topics.name"), required: true }, { name: "keywords", label: t("settings.topics.keywords"), type: "tags" }, { name: "active", label: t("common.active"), type: "checkbox" }]}
        initial={editing && editing !== "new" ? { ...editing } : { active: true }}
        onSubmit={async (v) => {
          if (editing === "new") await api.post("/topics", v);
          else if (editing) await api.patch(`/topics/${editing.id}`, v);
          await refresh("/topics");
        }}
      />
    </div>
  );
}

export function CatalogTab() {
  const { can } = useSession();
  const { data: formats, mutate: mf } = useApi<Schemas["FormatOut"][]>("/catalog/formats");
  const { data: creatives, mutate: mc } = useApi<Schemas["CreativeTypeOut"][]>("/catalog/creatives");
  const [fmt, setFmt] = useState<Schemas["FormatOut"] | null>(null);
  const [ct, setCt] = useState<Schemas["CreativeTypeOut"] | null>(null);
  const [newFmt, setNewFmt] = useState(false);
  const [newCt, setNewCt] = useState(false);
  const templates = [...new Set((formats ?? []).map((f) => f.template))].map((v) => ({ value: v, label: v }));
  const creativeTemplates = [...new Set((creatives ?? []).map((c) => c.template))].map((v) => ({ value: v, label: v }));
  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium">{t("settings.catalog.formats")}</p>
        {can("catalog.manage") ? <Button size="sm" onClick={() => setNewFmt(true)}><Plus />{t("mvp.newFormat")}</Button> : null}
      </div>
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {(formats ?? []).map((f) => (
          <Card key={f.id} className="gap-1 py-3"><CardContent className="grid gap-1 px-4 text-xs">
            <button className="text-left text-sm font-medium hover:underline" disabled={!can("catalog.manage")} onClick={() => setFmt(f)}>{f.code} · {f.name}</button>
            <p className="text-muted-foreground">{f.description}</p>
            <p><span className="font-medium">{t("settings.catalog.defaultStyle")}:</span> {f.default_style_slug} · <span className="font-medium">{t("settings.catalog.allowedStyles")}:</span> {f.allowed_style_slugs.join(", ")}</p>
          </CardContent></Card>
        ))}
      </div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium">{t("settings.catalog.creatives")}</p>
        {can("catalog.manage") ? <Button size="sm" onClick={() => setNewCt(true)}><Plus />{t("mvp.newCreative")}</Button> : null}
      </div>
      <div className="rounded-lg border bg-card">
        <Table>
          <TableBody>
            {(creatives ?? []).map((c) => (
              <TableRow key={c.id}>
                <TableCell className="w-16 font-mono text-xs">{c.code}</TableCell>
                <TableCell><button className="text-left hover:underline" disabled={!can("catalog.manage")} onClick={() => setCt(c)}><span className="font-medium">{c.name}</span></button><div className="text-xs text-muted-foreground">{c.description}</div></TableCell>
                <TableCell className="text-xs">{c.required_slots.join(", ")}</TableCell>
                <TableCell className="text-xs">{[c.requires_fact && t("settings.catalog.requiresFact"), c.requires_consent && t("settings.catalog.requiresConsent"), c.requires_real_photo && t("settings.catalog.requiresPhoto")].filter(Boolean).join(" · ")}</TableCell>
                <TableCell>{c.active ? <Badge variant="outline">{t("common.active")}</Badge> : <Badge variant="secondary">{t("common.inactive")}</Badge>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <FormDialog
        open={fmt !== null}
        onOpenChange={(o) => !o && setFmt(null)}
        title={fmt ? `${fmt.code} · ${fmt.name}` : ""}
        wide
        fields={[
          { name: "name", label: t("common.name"), required: true },
          { name: "description", label: t("common.description"), type: "textarea", rows: 3 },
          { name: "default_style_slug", label: t("settings.catalog.defaultStyle"), required: true, colSpan: 1 },
          { name: "allowed_style_slugs", label: t("settings.catalog.allowedStyles"), type: "tags", colSpan: 1 },
          { name: "options", label: t("settings.catalog.options"), type: "textarea", rows: 4 },
          { name: "active", label: t("common.active"), type: "checkbox" },
        ]}
        initial={fmt ? { ...fmt, options: JSON.stringify(fmt.options, null, 1) } : {}}
        onSubmit={async (v) => {
          if (!fmt) return;
          await api.patch(`/catalog/formats/${fmt.id}`, { ...v, options: JSON.parse(String(v.options || "{}")) });
          await mf();
        }}
      />
      <FormDialog
        open={ct !== null}
        onOpenChange={(o) => !o && setCt(null)}
        title={ct ? `${ct.code} · ${ct.name}` : ""}
        fields={[
          { name: "name", label: t("common.name"), required: true },
          { name: "description", label: t("common.description"), type: "textarea", rows: 3 },
          { name: "required_slots", label: t("settings.catalog.requiredSlots"), type: "tags" },
          { name: "requires_fact", label: t("settings.catalog.requiresFact"), type: "checkbox" },
          { name: "requires_consent", label: t("settings.catalog.requiresConsent"), type: "checkbox" },
          { name: "requires_real_photo", label: t("settings.catalog.requiresPhoto"), type: "checkbox" },
          { name: "active", label: t("common.active"), type: "checkbox" },
        ]}
        initial={ct ? { ...ct } : {}}
        onSubmit={async (v) => {
          if (!ct) return;
          await api.patch(`/catalog/creatives/${ct.id}`, v);
          await mc();
        }}
      />
      <FormDialog
        open={newFmt}
        onOpenChange={setNewFmt}
        title={t("mvp.newFormat")}
        fields={[
          { name: "slug", label: t("settings.topics.slug"), required: true, colSpan: 1 },
          { name: "name", label: t("common.name"), required: true, colSpan: 1 },
          { name: "description", label: t("common.description"), type: "textarea", rows: 2 },
          { name: "template", label: t("mvp.template"), type: "select", options: templates, required: true, colSpan: 1 },
          { name: "default_style_slug", label: t("settings.catalog.defaultStyle"), required: true, colSpan: 1 },
          { name: "allowed_style_slugs", label: t("settings.catalog.allowedStyles"), type: "tags" },
        ]}
        initial={{ template: "clasico", default_style_slug: "cercano", allowed_style_slugs: ["cercano", "institucional", "directo"] }}
        onSubmit={async (v) => {
          await api.post("/catalog/formats", v);
          await mf();
          await refresh("/catalog/matrix");
        }}
      />
      <FormDialog
        open={newCt}
        onOpenChange={setNewCt}
        title={t("mvp.newCreative")}
        fields={[
          { name: "slug", label: t("settings.topics.slug"), required: true, colSpan: 1 },
          { name: "name", label: t("common.name"), required: true, colSpan: 1 },
          { name: "description", label: t("common.description"), type: "textarea", rows: 2 },
          { name: "flow", label: t("mvp.flow"), type: "select", options: [{ value: "A", label: t("mvp.flowA") }, { value: "B", label: t("mvp.flowB") }], required: true, colSpan: 1 },
          { name: "template", label: t("mvp.template"), type: "select", options: creativeTemplates, required: true, colSpan: 1 },
          { name: "required_slots", label: t("settings.catalog.requiredSlots"), type: "tags" },
          { name: "requires_fact", label: t("settings.catalog.requiresFact"), type: "checkbox" },
          { name: "text_only", label: t("mvp.textOnly"), type: "checkbox" },
        ]}
        initial={{ flow: "A", template: creativeTemplates[0]?.value ?? "", required_slots: ["titulo", "texto"] }}
        onSubmit={async (v) => {
          await api.post("/catalog/creatives", v);
          await mc();
          await refresh("/catalog/matrix");
        }}
      />
    </div>
  );
}
