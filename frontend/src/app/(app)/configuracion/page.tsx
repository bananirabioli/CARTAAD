"use client";

import { CheckCircle2, Plus, Save } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState, Loading, PageHeader } from "@/components/app/common";
import { FormDialog, type FieldSpec } from "@/components/app/form-dialog";
import { useSession } from "@/components/app/session";
import { errMsg } from "@/components/pieces/parts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { enumOptions, fmtDate, t, tEnum } from "@/i18n";
import { api, refresh, useApi, type Schemas } from "@/lib/api/client";
import { useStateResetOn } from "@/lib/hooks";

const commas = (v: unknown) => (Array.isArray(v) ? v : String(v ?? "").split(",")).map((s) => String(s).trim()).filter(Boolean);

// ------------------------------------------------------------------ veda

// Hidden in the MVP (no campaign restrictions); kept for later.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function VedaTab() {
  const { can, reload } = useSession();
  const { data, mutate } = useApi<Schemas["RestrictionOut"][]>("/veda");
  const [editing, setEditing] = useState<Schemas["RestrictionOut"] | "new" | null>(null);
  const fields: FieldSpec[] = [
    { name: "name", label: t("settings.veda.name"), required: true },
    { name: "starts_at", label: t("settings.veda.startsAt"), type: "date", colSpan: 1 },
    { name: "ends_at", label: t("settings.veda.endsAt"), type: "date", colSpan: 1 },
    { name: "blocked_formats", label: t("settings.veda.formats"), type: "tags", help: enumOptions("format").map((o) => o.value).join(", ") },
    { name: "blocked_creatives", label: t("settings.veda.creatives"), type: "tags", help: enumOptions("creative").map((o) => o.value).join(", ") },
    { name: "mandatory_legends", label: t("settings.veda.legends"), type: "textarea", rows: 2 },
    { name: "reason", label: t("settings.veda.reason"), type: "textarea", rows: 2 },
    { name: "active", label: t("settings.veda.active"), type: "checkbox" },
  ];
  async function save(body: Record<string, unknown>, id?: number) {
    const payload = { ...body, mandatory_legends: String(body.mandatory_legends ?? "").split("\n").map((s) => s.trim()).filter(Boolean), active: Boolean(body.active) };
    if (id) await api.put(`/veda/${id}`, payload);
    else await api.post("/veda", payload);
    await mutate();
    await reload();
  }
  return (
    <div className="grid gap-3">
      <div className="flex items-start justify-between gap-3">
        <p className="max-w-3xl text-xs text-muted-foreground">{t("settings.veda.help")}</p>
        {can("veda.manage") ? <Button size="sm" onClick={() => setEditing("new")}><Plus />{t("settings.veda.new")}</Button> : null}
      </div>
      {!data?.length ? <EmptyState /> : data.map((r) => (
        <Card key={r.id} className="gap-2 py-4">
          <CardHeader className="flex flex-row items-start justify-between gap-2 px-4">
            <div>
              <CardTitle className="text-sm">{r.name}</CardTitle>
              <p className="text-xs text-muted-foreground">{fmtDate(r.starts_at)} → {fmtDate(r.ends_at)}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge className={r.in_effect ? "border-transparent bg-veda text-veda-foreground" : ""} variant={r.in_effect ? "default" : "outline"}>
                {r.in_effect ? t("settings.veda.inEffect") : r.active ? t("settings.veda.scheduled") : t("settings.veda.disabled")}
              </Badge>
              {can("veda.manage") ? (
                <>
                  {!r.in_effect ? (
                    <Button size="xs" variant="outline" onClick={() => save({ ...r, mandatory_legends: r.mandatory_legends.join("\n"), starts_at: new Date(Date.now() - 3600_000).toISOString(), active: true }, r.id)}>{t("settings.veda.activateNow")}</Button>
                  ) : null}
                  <Button size="xs" variant="ghost" onClick={() => setEditing(r)}>{t("common.edit")}</Button>
                </>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="grid gap-1 px-4 text-xs">
            <p><span className="font-medium">{t("settings.veda.formats")}:</span> {r.blocked_formats.map((f) => tEnum("format", f)).join(", ") || t("common.none")}</p>
            <p><span className="font-medium">{t("settings.veda.creatives")}:</span> {r.blocked_creatives.map((c) => tEnum("creative", c)).join(", ") || t("common.none")}</p>
            <p><span className="font-medium">{t("settings.veda.legends")}:</span> {r.mandatory_legends.join(" · ") || t("common.none")}</p>
            {r.reason ? <p className="text-muted-foreground">{r.reason}</p> : null}
          </CardContent>
        </Card>
      ))}
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={editing === "new" ? t("settings.veda.new") : editing ? editing.name : ""}
        fields={fields}
        wide
        initial={editing && editing !== "new" ? { ...editing, mandatory_legends: editing.mandatory_legends.join("\n") } : { active: true }}
        onSubmit={(v) => save(v, editing && editing !== "new" ? editing.id : undefined)}
      />
    </div>
  );
}

// ------------------------------------------------------------------ accounts

function AccountsTab() {
  const { can } = useSession();
  const { data, mutate } = useApi<Schemas["AccountOut"][]>("/accounts");
  const { data: styles } = useApi<Schemas["StyleOut"][]>("/styles");
  const [editing, setEditing] = useState<Schemas["AccountOut"] | "new" | null>(null);
  const fields: FieldSpec[] = [
    { name: "handle", label: t("settings.accounts.handle"), required: true, colSpan: 1 },
    { name: "display_name", label: t("settings.accounts.name"), required: true, colSpan: 1 },
    { name: "network", label: t("monitoring.network"), type: "select", options: enumOptions("network"), required: true, colSpan: 1 },
    { name: "account_type", label: t("settings.accounts.type"), type: "select", options: enumOptions("account_type"), required: true, colSpan: 1 },
    { name: "format_slug", label: t("settings.accounts.format"), type: "select", options: enumOptions("format"), required: true },
    { name: "default_style_slug", label: t("settings.accounts.style"), type: "select", options: (styles ?? []).map((s) => ({ value: s.slug, label: s.name })) },
    { name: "registered", label: t("settings.accounts.registered"), type: "checkbox" },
    { name: "notes", label: t("monitoring.notes"), type: "textarea", rows: 2 },
  ];
  return (
    <div className="grid gap-3">
      <div className="flex items-start justify-between gap-3">
        <p className="max-w-3xl text-xs text-muted-foreground">{t("settings.accounts.help")}</p>
        {can("config.manage") ? <Button size="sm" onClick={() => setEditing("new")}><Plus />{t("settings.accounts.new")}</Button> : null}
      </div>
      <div className="rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("settings.accounts.handle")}</TableHead>
              <TableHead>{t("settings.accounts.type")}</TableHead>
              <TableHead>{t("settings.accounts.format")}</TableHead>
              <TableHead>{t("settings.accounts.style")}</TableHead>
              <TableHead>{t("settings.accounts.registered")}</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data ?? []).map((a) => (
              <TableRow key={a.id}>
                <TableCell><button className="text-left hover:underline" disabled={!can("config.manage")} onClick={() => setEditing(a)}><span className="font-medium">{a.display_name}</span><div className="text-xs text-muted-foreground">{a.handle} · {tEnum("network", a.network)}</div></button></TableCell>
                <TableCell className="text-xs">{tEnum("account_type", a.account_type)}</TableCell>
                <TableCell className="text-xs">{tEnum("format", a.format_slug)}</TableCell>
                <TableCell className="text-xs">{a.default_style_slug ?? t("common.none")}</TableCell>
                <TableCell className="text-xs">
                  {a.registered ? (a.verified ? <span className="inline-flex items-center gap-1 text-status-ok"><CheckCircle2 className="size-3.5" />{t("settings.accounts.verified")}</span> : t("settings.accounts.registered")) : <Badge variant="outline" className="border-status-block/50 text-status-block">{t("common.no")}</Badge>}
                </TableCell>
                <TableCell>{a.registered && !a.verified && can("config.manage") ? <Button size="xs" variant="outline" onClick={async () => { await api.post(`/accounts/${a.id}/verify`); await mutate(); }}>{t("settings.accounts.verify")}</Button> : null}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={editing === "new" ? t("settings.accounts.new") : editing ? editing.display_name : ""}
        fields={editing === "new" ? fields : fields.filter((f) => !["handle", "network"].includes(f.name))}
        initial={editing && editing !== "new" ? { ...editing } : { network: "facebook", account_type: "propia", format_slug: "formato_clasico", registered: true }}
        onSubmit={async (v) => {
          if (editing === "new") await api.post("/accounts", v);
          else if (editing) await api.patch(`/accounts/${editing.id}`, v);
          await mutate();
        }}
      />
    </div>
  );
}

// ------------------------------------------------------------------ thresholds & weights

type SettingsData = Record<string, unknown>;

// eslint-disable-next-line @typescript-eslint/no-unused-vars -- hidden in the MVP
function ThresholdsTab() {
  const { can } = useSession();
  const { data, mutate } = useApi<Schemas["SettingsOut"]>("/settings");
  const [s, setS] = useStateResetOn<SettingsData | null>(data, () => (data ? structuredClone(data.settings) : null));
  if (!s) return <Loading />;
  const get = (path: string) => path.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], s);
  const set = (path: string, value: unknown) => {
    const next = structuredClone(s);
    const keys = path.split(".");
    let node = next as Record<string, unknown>;
    for (const k of keys.slice(0, -1)) node = node[k] as Record<string, unknown>;
    node[keys[keys.length - 1]] = value;
    setS(next);
  };
  const num = (path: string, label: string) => (
    <div className="grid gap-1"><Label className="text-xs">{label}</Label><Input type="number" step="any" value={String(get(path) ?? "")} onChange={(e) => set(path, Number(e.target.value))} /></div>
  );
  const weights = get("risk_weights") as Record<string, number>;
  const modes = get("validator_modes") as Record<string, string>;
  const mapping = get("strategy_mapping") as Record<string, string[]>;
  async function save() {
    try {
      await api.patch("/settings", { patch: s });
      await mutate();
      await refresh("/cases", "/dashboard");
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(errMsg(err));
    }
  }
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="gap-3 py-4"><CardHeader className="px-4"><CardTitle className="text-sm">{t("settings.thresholds.alert")}</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-3 gap-3 px-4">
            {num("alert_thresholds.medio", tEnum("alert_level", "medio"))}
            {num("alert_thresholds.alto", tEnum("alert_level", "alto"))}
            {num("alert_thresholds.critico", tEnum("alert_level", "critico"))}
            {num("alert_window_hours", t("settings.thresholds.window"))}
            {num("baseline_min_days", t("settings.thresholds.baselineDays"))}
            {num("learning_min_sample", t("settings.thresholds.minSample"))}
            {num("creatives_min", `${t("settings.thresholds.creatives")} · min`)}
            {num("creatives_max", `${t("settings.thresholds.creatives")} · max`)}
            {num("source_review_interval_days", t("settings.thresholds.review"))}
          </CardContent>
        </Card>
        <Card className="gap-3 py-4"><CardHeader className="px-4"><CardTitle className="text-sm">{t("settings.thresholds.weights")}</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 px-4">
            {Object.keys(weights).map((k) => num(`risk_weights.${k}`, t(`risk.${k}.label`)))}
          </CardContent>
        </Card>
        <Card className="gap-3 py-4"><CardHeader className="px-4"><CardTitle className="text-sm">{t("settings.thresholds.validators")}</CardTitle></CardHeader>
          <CardContent className="grid gap-3 px-4">
            {Object.keys(modes).map((k) => (
              <div key={k} className="flex items-center justify-between gap-3 text-sm">
                <span className="font-mono text-xs">{k}</span>
                <Select value={modes[k]} onValueChange={(v) => set(`validator_modes.${k}`, v)}>
                  <SelectTrigger size="sm" className="w-32"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="block">{t("settings.thresholds.block")}</SelectItem><SelectItem value="warn">{t("settings.thresholds.warn")}</SelectItem></SelectContent>
                </Select>
              </div>
            ))}
            <div className="grid gap-1"><Label className="text-xs">{t("settings.thresholds.variantStyles")}</Label><Input value={(get("default_variant_styles") as string[]).join(", ")} onChange={(e) => set("default_variant_styles", commas(e.target.value))} /></div>
          </CardContent>
        </Card>
        <Card className="gap-3 py-4"><CardHeader className="px-4"><CardTitle className="text-sm">{t("settings.thresholds.strategyMapping")}</CardTitle></CardHeader>
          <CardContent className="grid gap-2 px-4">
            {Object.keys(mapping).map((k) => (
              <div key={k} className="grid grid-cols-[180px_minmax(0,1fr)] items-center gap-2">
                <span className="text-xs">{k === "a_favor" ? tEnum("stance", k) : tEnum("message_type", k)}</span>
                <Input value={mapping[k].join(", ")} onChange={(e) => set(`strategy_mapping.${k}`, commas(e.target.value))} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
      {can("config.manage") ? <Button className="w-fit" onClick={save}><Save />{t("settings.thresholds.save")}</Button> : null}
    </div>
  );
}

// ------------------------------------------------------------------ topics, catalogs, users, clients, AI runs

// Per-user permissions come after the MVP; the master user does everything for now.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function UsersTab() {
  const { can, me } = useSession();
  const { data, mutate } = useApi<Schemas["UserAdminOut"][]>(can("users.manage") ? "/users" : null);
  const [editing, setEditing] = useState<Schemas["UserAdminOut"] | "new" | null>(null);
  if (!can("users.manage")) return <EmptyState />;
  const clientOpts = (me?.clients ?? []).map((c) => ({ value: String(c.id), label: c.name }));
  return (
    <div className="grid gap-3">
      <div className="flex justify-end"><Button size="sm" onClick={() => setEditing("new")}><Plus />{t("settings.users.new")}</Button></div>
      <div className="rounded-lg border bg-card">
        <Table>
          <TableHeader><TableRow><TableHead>{t("settings.users.name")}</TableHead><TableHead>{t("settings.users.role")}</TableHead><TableHead>{t("settings.users.clients")}</TableHead><TableHead>{t("common.status")}</TableHead></TableRow></TableHeader>
          <TableBody>
            {(data ?? []).map((u) => (
              <TableRow key={u.id}>
                <TableCell><button className="text-left hover:underline" onClick={() => setEditing(u)}><span className="font-medium">{u.name}</span><div className="text-xs text-muted-foreground">{u.email}</div></button></TableCell>
                <TableCell className="text-xs">{t(`roles.${u.role}`)}{u.kb_owner ? ` · ${t("roles.kb_owner")}` : ""}</TableCell>
                <TableCell className="text-xs">{u.client_ids.map((id) => me?.clients.find((c) => c.id === id)?.name).filter(Boolean).join(", ")}</TableCell>
                <TableCell>{u.active ? <Badge variant="outline">{t("common.active")}</Badge> : <Badge variant="secondary">{t("common.inactive")}</Badge>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={editing === "new" ? t("settings.users.new") : editing ? editing.name : ""}
        fields={[
          ...(editing === "new" ? [{ name: "email", label: t("settings.users.email"), required: true } as FieldSpec] : []),
          { name: "name", label: t("settings.users.name"), required: true },
          { name: "role", label: t("settings.users.role"), type: "select", required: true, options: ["analista", "aprobador", "legal", "diseno", "admin"].map((r) => ({ value: r, label: t(`roles.${r}`) })), colSpan: 1 },
          { name: "kb_owner", label: t("settings.users.kbOwner"), type: "checkbox", colSpan: 1 },
          { name: "password", label: t("settings.users.password"), required: editing === "new" },
          { name: "client_ids", label: `${t("settings.users.clients")} (${clientOpts.map((c) => `${c.value}=${c.label}`).join(", ")})`, type: "tags" },
          ...(editing !== "new" ? [{ name: "active", label: t("settings.users.active"), type: "checkbox" } as FieldSpec] : []),
        ]}
        initial={editing && editing !== "new" ? { ...editing, client_ids: editing.client_ids.map(String) } : { role: "analista", client_ids: [String(me?.client.id ?? "")] }}
        onSubmit={async (v) => {
          const body = { ...v, client_ids: (v.client_ids as string[]).map(Number), password: v.password || undefined };
          if (editing === "new") await api.post("/users", body);
          else if (editing) await api.patch(`/users/${editing.id}`, body);
          await mutate();
        }}
      />
    </div>
  );
}

function ClientContext() {
  const { can, me } = useSession();
  const { data, mutate } = useApi<{ settings: Record<string, unknown> }>("/settings");
  const [value, setValue] = useStateResetOn<string>(data, () => String(data?.settings.context ?? ""));
  if (!data) return <Loading />;
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4"><CardTitle className="text-sm">{t("mvp.contextTitle", { client: me?.client.name ?? "" })}</CardTitle></CardHeader>
      <CardContent className="grid gap-2 px-4">
        <p className="text-xs text-muted-foreground">{t("mvp.contextHelp")}</p>
        <Input value={value} onChange={(e) => setValue(e.target.value)} disabled={!can("config.manage")} placeholder="Juárez, Chihuahua" />
        {can("config.manage") ? (
          <Button size="sm" className="w-fit" onClick={async () => {
            try { await api.patch("/settings", { patch: { context: value } }); await mutate(); toast.success(t("common.saved")); } catch (err) { toast.error(errMsg(err)); }
          }}><Save />{t("common.save")}</Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ClientsTab() {
  const { can, me, reload } = useSession();
  const [editing, setEditing] = useState<Schemas["ClientOut"] | "new" | null>(null);
  return (
    <div className="grid gap-3">
      <ClientContext />
      {can("config.manage") ? <div className="flex justify-end"><Button size="sm" onClick={() => setEditing("new")}><Plus />{t("settings.clients.new")}</Button></div> : null}
      <div className="grid gap-2 md:grid-cols-2">
        {(me?.clients ?? []).map((c) => (
          <Card key={c.id} className="gap-1 py-3"><CardContent className="grid gap-1 px-4 text-xs">
            <button className="text-left text-sm font-medium hover:underline" disabled={!can("config.manage")} onClick={() => setEditing(c)}>{c.name} <Badge variant="outline">{tEnum("client_type", c.client_type)}</Badge></button>
            <p className="text-muted-foreground">{c.default_tone}</p>
          </CardContent></Card>
        ))}
      </div>
      <FormDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={editing === "new" ? t("settings.clients.new") : editing ? editing.name : ""}
        fields={[
          ...(editing === "new" ? [{ name: "slug", label: t("settings.clients.slug"), required: true } as FieldSpec] : []),
          { name: "name", label: t("settings.clients.name"), required: true },
          { name: "client_type", label: t("settings.clients.type"), type: "select", options: enumOptions("client_type"), required: true, colSpan: 1 },
          { name: "default_style_slug", label: t("settings.clients.defaultStyle"), colSpan: 1 },
          { name: "default_tone", label: t("settings.clients.tone"), type: "textarea", rows: 2 },
        ]}
        initial={editing && editing !== "new" ? { ...editing } : { client_type: "candidatura", default_style_slug: "cercano" }}
        onSubmit={async (v) => {
          if (editing === "new") await api.post("/clients", v);
          else if (editing) await api.patch(`/clients/${editing.id}`, v);
          await reload();
        }}
      />
    </div>
  );
}

export default function SettingsPage() {
  return (
    <div>
      <PageHeader title={t("settings.title")} subtitle={t("mvp.settingsSubtitle")} />
      <Tabs defaultValue="clients">
        <TabsList className="h-auto flex-wrap">
          <TabsTrigger value="clients">{t("settings.tabs.clients")}</TabsTrigger>
          <TabsTrigger value="accounts">{t("settings.tabs.accounts")}</TabsTrigger>

        </TabsList>
        <TabsContent value="clients" className="mt-3"><ClientsTab /></TabsContent>
        <TabsContent value="accounts" className="mt-3"><AccountsTab /></TabsContent>

      </Tabs>
    </div>
  );
}
