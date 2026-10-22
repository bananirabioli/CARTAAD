"use client";

import { CalendarPlus, Copy, Download, Package, Send, X } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { EmptyState, Loading, PageHeader } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { errMsg } from "@/components/pieces/parts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { fmtDate, fmtDay, t, tEnum } from "@/i18n";
import { API_BASE, api, fileUrl, refresh, useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Sched = Schemas["ScheduledOut"];
type Item = Schemas["InboxItem"];
const NONE = "__none__";

function pieceLabel(p: Item) {
  return `${p.case_code} · ${p.kind === "copy" ? `Copy ${p.style_slug}` : tEnum("creative", p.creative_slug)} · v${p.current_version}`;
}

function ScheduleDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { data: approved } = useApi<Schemas["Page_InboxItem_"]>(open ? "/inbox?status=aprobado&page_size=200" : null);
  const { data: accounts } = useApi<Schemas["AccountOut"][]>(open ? "/accounts" : null);
  const [pieceId, setPieceId] = useState("");
  const [copyId, setCopyId] = useState(NONE);
  const [accountId, setAccountId] = useState("");
  const [when, setWhen] = useState(() => new Date(Date.now() + 3600_000).toISOString().slice(0, 16));
  const [error, setError] = useState<string | null>(null);
  const items = approved?.items ?? [];
  const piece = items.find((p) => String(p.id) === pieceId);
  const copies = items.filter((p) => p.kind === "copy" && piece && p.case_id === piece.case_id && p.id !== piece.id);
  const registered = (accounts ?? []).filter((a) => a.registered && a.verified && a.active);
  async function submit() {
    setError(null);
    try {
      await api.post("/schedule", { piece_id: Number(pieceId), account_id: Number(accountId), scheduled_at: new Date(when).toISOString(), copy_piece_id: copyId === NONE ? null : Number(copyId) });
      await refresh("/schedule", "/inbox", "/cases", "/dashboard");
      onOpenChange(false);
      toast.success(t("common.saved"));
    } catch (err) {
      setError(errMsg(err));
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader><DialogTitle>{t("publishing.schedule")}</DialogTitle></DialogHeader>
        {!items.length ? <p className="text-sm text-muted-foreground">{t("publishing.noApproved")}</p> : (
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label>{t("publishing.piece")}</Label>
              <Select value={pieceId} onValueChange={(v) => { setPieceId(v); setCopyId(NONE); const p = items.find((x) => String(x.id) === v); if (p?.account_id) setAccountId(String(p.account_id)); }}>
                <SelectTrigger className="w-full"><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{items.map((p) => <SelectItem key={p.id} value={String(p.id)}>{pieceLabel(p)}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            {piece?.kind === "creative" ? (
              <div className="grid gap-1.5">
                <Label>{t("publishing.copyPiece")}</Label>
                <Select value={copyId} onValueChange={setCopyId}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value={NONE}>{t("common.none")}</SelectItem>{copies.map((p) => <SelectItem key={p.id} value={String(p.id)}>{pieceLabel(p)}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            ) : null}
            <div className="grid gap-1.5">
              <Label>{t("publishing.account")}</Label>
              <Select value={accountId} onValueChange={setAccountId}>
                <SelectTrigger className="w-full"><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{registered.map((a) => <SelectItem key={a.id} value={String(a.id)}>{a.display_name} · {a.handle} · {tEnum("account_type", a.account_type)}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>{t("publishing.when")}</Label>
              <Input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
            </div>
            {error ? <p className="text-sm text-status-block">{error}</p> : null}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t("common.cancel")}</Button>
          <Button disabled={!pieceId || !accountId} onClick={submit}>{t("publishing.schedule")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CalendarTab() {
  const { can } = useSession();
  const { data, isLoading, mutate } = useApi<Sched[]>("/schedule");
  const [open, setOpen] = useState(false);
  const groups = useMemo(() => {
    const byDay = new Map<string, Sched[]>();
    for (const s of data ?? []) {
      const key = new Date(s.scheduled_at).toDateString();
      byDay.set(key, [...(byDay.get(key) ?? []), s]);
    }
    return [...byDay.entries()];
  }, [data]);
  async function act(path: string) {
    try {
      await api.post(path);
      await Promise.all([mutate(), refresh("/cases", "/inbox", "/dashboard")]);
    } catch (err) {
      toast.error(errMsg(err));
    }
  }
  return (
    <div className="grid gap-3">
      {can("schedule.manage") ? <div className="flex justify-end"><Button size="sm" onClick={() => setOpen(true)}><CalendarPlus />{t("publishing.schedule")}</Button></div> : null}
      {isLoading ? <Loading /> : !groups.length ? <EmptyState /> : groups.map(([day, items]) => (
        <div key={day} className="grid gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{fmtDay(items[0].scheduled_at)}</p>
          {items.map((s) => (
            <Card key={s.id} className="gap-0 py-0">
              <CardContent className="grid grid-cols-[80px_minmax(0,1fr)_auto] items-start gap-3 p-3">
                {s.render ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={fileUrl(s.render)} alt="" className="h-24 w-20 rounded border object-cover" />
                ) : <div className="h-24 w-20 rounded border bg-muted" />}
                <div className="grid min-w-0 gap-1 text-sm">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-mono">{new Date(s.scheduled_at).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" })}</span>
                    <Badge variant="outline">{s.account_handle}</Badge>
                    <Badge className={cn("border-transparent", s.status === "publicado" ? "bg-status-ok/15 text-status-ok" : s.status === "error" ? "bg-status-block/15 text-status-block" : s.status === "cancelado" ? "bg-muted text-muted-foreground" : "bg-status-info/15 text-status-info")}>{tEnum("schedule_status", s.status)}</Badge>
                    <span className="font-mono text-primary">{s.case_code}</span>
                    <span className="text-muted-foreground">{s.piece_label}</span>
                  </div>
                  <p className="line-clamp-3 whitespace-pre-line text-xs text-muted-foreground">{s.text}</p>
                  {s.error ? <p className="text-xs text-status-block">{s.error}</p> : null}
                  {s.published_at ? <p className="text-[11px] text-muted-foreground">{fmtDate(s.published_at)}</p> : null}
                </div>
                {s.status === "programado" && can("schedule.manage") ? (
                  <div className="flex flex-col gap-1">
                    <Button size="xs" onClick={() => act(`/schedule/${s.id}/publish-now`)}><Send />{t("publishing.publishNow")}</Button>
                    <Button size="xs" variant="ghost" onClick={() => act(`/schedule/${s.id}/cancel`)}><X />{t("publishing.cancel")}</Button>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      ))}
      <ScheduleDialog open={open} onOpenChange={setOpen} />
    </div>
  );
}

function AlliesTab() {
  const { can } = useSession();
  const { data, mutate } = useApi<Schemas["AllyPackageOut"][]>("/ally-packages");
  const { data: approved } = useApi<Schemas["Page_InboxItem_"]>("/inbox?status=aprobado,programado,publicado&page_size=200");
  const [open, setOpen] = useState(false);
  const [caseId, setCaseId] = useState("");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [days, setDays] = useState(7);
  const [selected, setSelected] = useState<number[]>([]);
  const items = approved?.items ?? [];
  const cases = [...new Map(items.map((p) => [p.case_id, p.case_code])).entries()];
  const casePieces = items.filter((p) => String(p.case_id) === caseId);
  const linkFor = (token: string) => `${typeof window !== "undefined" ? window.location.origin : ""}/aliados/${token}`;
  return (
    <div className="grid gap-3">
      {can("ally.manage") ? <div className="flex justify-end"><Button size="sm" onClick={() => setOpen(true)}><Package />{t("publishing.newPackage")}</Button></div> : null}
      {!data?.length ? <EmptyState /> : data.map((p) => (
        <Card key={p.id} className="gap-2 py-4">
          <CardHeader className="flex flex-row items-start justify-between gap-2 px-4">
            <div>
              <CardTitle className="text-sm">{p.title} <span className="font-mono text-xs text-primary">{p.case_code}</span></CardTitle>
              <p className="text-xs text-muted-foreground">{p.revoked ? t("publishing.revoked") : t("publishing.expires", { date: fmtDate(p.expires_at) })} · {p.piece_ids.length} piezas</p>
            </div>
            <div className="flex gap-2">
              <Button size="xs" variant="outline" onClick={async () => { await navigator.clipboard.writeText(linkFor(p.token)); toast.success(t("common.copied")); }}><Copy />{t("publishing.copyLink")}</Button>
              {!p.revoked && can("ally.manage") ? <Button size="xs" variant="ghost" onClick={async () => { await api.post(`/ally-packages/${p.id}/revoke`); await mutate(); }}>{t("publishing.revoke")}</Button> : null}
            </div>
          </CardHeader>
          <CardContent className="grid gap-1 px-4 text-xs">
            <p className="break-all text-muted-foreground">{linkFor(p.token)}</p>
            <p className="font-medium">{t("publishing.shares")}</p>
            {p.shares.length ? p.shares.map((s, i) => <p key={i}>{String(s.account)} · {String(s.by)} · {fmtDate(String(s.at))}</p>) : <p className="text-muted-foreground">{t("publishing.noShares")}</p>}
          </CardContent>
        </Card>
      ))}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader><DialogTitle>{t("publishing.newPackage")}</DialogTitle></DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-1.5"><Label>{t("publishing.packageCase")}</Label>
              <Select value={caseId} onValueChange={(v) => { setCaseId(v); setSelected([]); }}>
                <SelectTrigger className="w-full"><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{cases.map(([id, code]) => <SelectItem key={id} value={String(id)}>{code}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5"><Label>{t("publishing.packagePieces")}</Label>
              {casePieces.map((p) => (
                <label key={p.id} className="flex items-center gap-2 text-sm">
                  <Checkbox checked={selected.includes(p.id)} onCheckedChange={(c) => setSelected(c ? [...selected, p.id] : selected.filter((x) => x !== p.id))} />
                  {pieceLabel(p)}
                </label>
              ))}
            </div>
            <div className="grid gap-1.5"><Label>{t("publishing.packageTitle")}</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            <div className="grid gap-1.5"><Label>{t("publishing.packageMessage")}</Label><Textarea rows={2} value={message} onChange={(e) => setMessage(e.target.value)} /></div>
            <div className="grid gap-1.5"><Label>{t("publishing.expiresIn")}</Label><Input type="number" min={1} max={60} value={days} onChange={(e) => setDays(Number(e.target.value))} /></div>
          </div>
          <DialogFooter>
            <Button
              disabled={!caseId || !selected.length || title.length < 3}
              onClick={async () => {
                try {
                  await api.post("/ally-packages", { case_id: Number(caseId), title, message, piece_ids: selected, expires_in_days: days });
                  await mutate();
                  setOpen(false);
                } catch (err) {
                  toast.error(errMsg(err));
                }
              }}
            >
              {t("common.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ExportTab() {
  const { can } = useSession();
  const { data } = useApi<Schemas["Page_InboxItem_"]>("/inbox?status=aprobado,programado,publicado&page_size=200");
  const items = data?.items ?? [];
  const cases = [...new Map(items.map((p) => [p.case_id, p.case_code])).entries()];
  if (!can("export.pieces")) return <EmptyState />;
  return (
    <div className="grid gap-3">
      <p className="text-xs text-muted-foreground">{t("publishing.exportHelp")}</p>
      {!cases.length ? <EmptyState /> : cases.map(([id, code]) => (
        <Card key={id} className="gap-2 py-3">
          <CardContent className="flex flex-wrap items-center gap-2 px-4 text-sm">
            <span className="font-mono text-primary">{code}</span>
            <Button size="xs" variant="outline" asChild><a href={`${API_BASE}/cases/${id}/export.zip`}><Download />{t("publishing.exportCase")}</a></Button>
            {items.filter((p) => p.case_id === id).map((p) => (
              <Button key={p.id} size="xs" variant="ghost" asChild><a href={`${API_BASE}/pieces/${p.id}/export.zip`}><Download />{p.kind === "copy" ? `Copy ${p.style_slug}` : tEnum("creative", p.creative_slug)}</a></Button>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function PublishingPage() {
  return (
    <div>
      <PageHeader title={t("publishing.title")} subtitle={t("publishing.subtitle")} />
      <Tabs defaultValue="calendar">
        <TabsList>
          <TabsTrigger value="calendar">{t("publishing.tabs.calendar")}</TabsTrigger>
          <TabsTrigger value="allies">{t("publishing.tabs.allies")}</TabsTrigger>
          <TabsTrigger value="export">{t("publishing.tabs.export")}</TabsTrigger>
        </TabsList>
        <TabsContent value="calendar" className="mt-3"><CalendarTab /></TabsContent>
        <TabsContent value="allies" className="mt-3"><AlliesTab /></TabsContent>
        <TabsContent value="export" className="mt-3"><ExportTab /></TabsContent>
      </Tabs>
    </div>
  );
}
