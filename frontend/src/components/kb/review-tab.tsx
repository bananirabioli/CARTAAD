"use client";

import { Check, Download, Loader2, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState, Loading } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { ModelPicker } from "@/components/lab/parts";
import { errMsg } from "@/components/pieces/parts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fmtNum, t } from "@/i18n";
import { API_BASE, api, refresh, useApi, type Schemas } from "@/lib/api/client";

type Fact = Schemas["FactOut"];
type ExtractReport = Schemas["ExtractReport"];

/** Facts proposed by the AI: approve (→ activo, used in prompts) or discard. */
export function ReviewTab() {
  const { can } = useSession();
  const { data, isLoading, mutate } = useApi<Schemas["Page_FactOut_"]>("/kb/facts?state=propuesto&page_size=100");
  const [extractOpen, setExtractOpen] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function review(f: Fact, action: "aprobar" | "descartar") {
    setBusyId(f.id);
    try {
      await api.post(`/kb/facts/${f.id}/review`, { action });
      toast.success(action === "aprobar" ? t("kb.lab.approved") : t("kb.lab.discarded"));
      await mutate();
      await refresh("/kb/");
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs text-muted-foreground">{t("kb.lab.reviewHelp")}</p>
        <div className="ml-auto flex gap-2">
          <Button size="sm" variant="outline" asChild><a href={`${API_BASE}/kb/facts-template.csv`} download><Download />{t("kb.lab.template")}</a></Button>
          {can("kb.curate") ? <Button size="sm" onClick={() => setExtractOpen(true)}><Sparkles />{t("kb.lab.extract")}</Button> : null}
        </div>
      </div>
      {isLoading ? <Loading /> : !data?.items.length ? <EmptyState /> : data.items.map((f) => (
        <Card key={f.id} className="gap-2 py-3">
          <CardContent className="grid gap-2 px-4 text-sm">
            <div className="flex flex-wrap items-start gap-2">
              <span className="font-mono text-xs text-muted-foreground">{f.code}</span>
              <p className="min-w-0 flex-1">{f.statement}</p>
              {f.value !== null && f.value !== undefined ? <Badge variant="outline" className="font-mono">{fmtNum(f.value)} {f.unit}</Badge> : null}
              {f.period_label ? <Badge variant="secondary">{f.period_label}</Badge> : null}
            </div>
            {f.source_quote ? (
              <blockquote className="border-l-2 pl-3 text-xs text-muted-foreground">
                «{f.source_quote}» <span className="whitespace-nowrap">— {f.document?.title}{f.source_page ? `, ${t("kb.lab.page")} ${f.source_page}` : ""}</span>
              </blockquote>
            ) : null}
            {can("kb.curate") ? (
              <div className="flex gap-2">
                <Button size="xs" disabled={busyId === f.id} onClick={() => review(f, "aprobar")}><Check />{t("kb.lab.approve")}</Button>
                <Button size="xs" variant="ghost" disabled={busyId === f.id} onClick={() => review(f, "descartar")}><X />{t("kb.lab.discard")}</Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ))}
      <ExtractTextDialog open={extractOpen} onOpenChange={setExtractOpen} onDone={() => { void mutate(); void refresh("/kb/"); }} />
    </div>
  );
}

function ExtractTextDialog({ open, onOpenChange, onDone }: { open: boolean; onOpenChange: (o: boolean) => void; onDone: () => void }) {
  const [title, setTitle] = useState("");
  const [issuer, setIssuer] = useState("");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true);
    try {
      const r = await api.post<ExtractReport>("/kb/extract-text", { title, issuer, url: url || null, text, model: model || null });
      toast.success(t("kb.lab.extractDone", { n: r.proposed }));
      onDone();
      onOpenChange(false);
      setText("");
      setTitle("");
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("kb.lab.extractTitle")}</DialogTitle>
          <DialogDescription>{t("kb.lab.extractHelp")}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="grid gap-1.5"><Label htmlFor="xt">{t("kb.documents.titleField")}</Label><Input id="xt" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            <div className="grid gap-1.5"><Label htmlFor="xi">{t("kb.lab.sourceIssuer")}</Label><Input id="xi" value={issuer} onChange={(e) => setIssuer(e.target.value)} /></div>
          </div>
          <div className="grid gap-1.5"><Label htmlFor="xu">{t("kb.lab.sourceUrl")}</Label><Input id="xu" value={url} onChange={(e) => setUrl(e.target.value)} /></div>
          <div className="grid gap-1.5"><Label htmlFor="xx">{t("kb.lab.extractText")}</Label><Textarea id="xx" rows={10} value={text} onChange={(e) => setText(e.target.value)} /></div>
          <div className="grid gap-1.5"><Label>{t("lab.layers.text")}</Label><ModelPicker kind="text" value={model} onChange={setModel} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t("common.close")}</Button>
          <Button disabled={busy || title.trim().length < 3 || text.trim().length < 40} onClick={run}>{busy ? <Loader2 className="animate-spin" /> : <Sparkles />}{t("kb.lab.extract")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Button for a processed document: ask the AI to propose its facts. */
export function ExtractFromDocButton({ docId, disabled }: { docId: number; disabled?: boolean }) {
  const [busy, setBusy] = useState(false);
  return (
    <Button size="xs" variant="outline" disabled={busy || disabled} onClick={async () => {
      setBusy(true);
      try {
        const r = await api.post<ExtractReport>(`/kb/documents/${docId}/extract-facts`, {});
        toast.success(t("kb.lab.extractDone", { n: r.proposed }));
        await refresh("/kb/");
      } catch (err) {
        toast.error(errMsg(err));
      } finally {
        setBusy(false);
      }
    }}>
      {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}{t("kb.lab.extractFromDoc")}
    </Button>
  );
}
