"use client";

import { ImageUp, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

import { AlertBadge } from "@/components/app/badges";
import { PageHeader } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { enumOptions, t } from "@/i18n";
import { api, ApiError, fileUrl, refresh, useApi, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const NONE = "__none__";

export default function CapturePage() {
  const { can } = useSession();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [network, setNetwork] = useState("facebook");
  const [sourceId, setSourceId] = useState(NONE);
  const [sourceName, setSourceName] = useState("");
  const [sourceType, setSourceType] = useState("pagina_ciudadana");
  const [blur, setBlur] = useState(true);
  const [counts, setCounts] = useState({ likes: "", comments: "", shares: "" });
  const [commentsText, setCommentsText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Schemas["PostDetail"] | null>(null);
  const { data: sources } = useApi<Schemas["Page_SourceOut_"]>("/sources?page_size=200");

  function pick(f: File | null | undefined) {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setText("");
    setUrl("");
    setSourceId(NONE);
    setSourceName("");
    setCounts({ likes: "", comments: "", shares: "" });
    setCommentsText("");
    setResult(null);
    setError(null);
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("text", text);
      fd.append("network", network);
      fd.append("blur_names", String(blur));
      if (url) fd.append("url", url);
      if (sourceId !== NONE) fd.append("source_id", sourceId);
      else if (sourceName.trim()) {
        fd.append("source_name", sourceName.trim());
        fd.append("source_type", sourceType);
      }
      for (const [k, v] of Object.entries(counts)) if (v !== "") fd.append(k, v);
      if (commentsText.trim()) fd.append("comments_text", commentsText);
      if (file) fd.append("image", file);
      const post = await api.upload<Schemas["PostDetail"]>("/posts/manual", fd);
      setResult(post);
      await refresh("/posts", "/sources", "/cases", "/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div>
        <PageHeader title={t("capture.title")} />
        <Card className="max-w-3xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {t("capture.done")} <AlertBadge level={result.alert_level} ratio={result.alert_ratio} />
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            {result.image_key ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={fileUrl(result.image_key)} alt="" className="max-h-72 rounded border object-contain" />
            ) : null}
            <p className="whitespace-pre-line">{result.text}</p>
            <p className="text-xs text-muted-foreground">{result.visual_context}</p>
            <div className="flex flex-wrap gap-2">
              {result.case_id ? (
                <Button asChild>
                  <Link href={`/casos/${result.case_id}`}>{t("monitoring.openCase")} · {result.case_code}</Link>
                </Button>
              ) : null}
              <Button variant="outline" onClick={reset}>
                {t("capture.another")}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={t("capture.title")} subtitle={t("capture.subtitle")} />
      <div className="grid gap-6 lg:grid-cols-2">
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            pick(e.dataTransfer.files?.[0]);
          }}
          className={cn(
            "flex min-h-80 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed bg-card p-4 text-center text-sm text-muted-foreground transition-colors",
            dragging && "border-primary bg-primary/5",
          )}
        >
          <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
          {preview ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={preview} alt="" className={cn("max-h-96 rounded object-contain", blur && "[filter:none]")} />
              <span className="text-xs">{t("capture.replace")}</span>
            </>
          ) : (
            <>
              <ImageUp className="size-8" />
              <p>{t("capture.drop")}</p>
              <p className="text-xs">{t("capture.dropHint")}</p>
            </>
          )}
        </div>
        <div className="grid content-start gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="copy">{t("capture.copy")}</Label>
            <Textarea id="copy" rows={5} value={text} onChange={(e) => setText(e.target.value)} />
            <p className="text-xs text-muted-foreground">{t("capture.copyHint")}</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>{t("capture.network")}</Label>
              <Select value={network} onValueChange={setNetwork}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>{enumOptions("network").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="url">{t("capture.url")}</Label>
              <Input id="url" value={url} onChange={(e) => setUrl(e.target.value)} />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>{t("capture.source")}</Label>
            <Select value={sourceId} onValueChange={setSourceId}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>{t("capture.sourceNone")}</SelectItem>
                {(sources?.items ?? []).map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          {sourceId === NONE ? (
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="newsrc">{t("capture.newSource")}</Label>
                <Input id="newsrc" value={sourceName} onChange={(e) => setSourceName(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label>{t("capture.newSourceType")}</Label>
                <Select value={sourceType} onValueChange={setSourceType}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>{enumOptions("source_type").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
          ) : null}
          <label className="flex items-start gap-3 rounded-md border p-3">
            <Switch checked={blur} onCheckedChange={setBlur} />
            <span className="grid gap-0.5">
              <span className="text-sm font-medium">{t("capture.blur")}</span>
              <span className="text-xs text-muted-foreground">{t("capture.blurHint")}</span>
            </span>
          </label>
          <div className="grid gap-1.5">
            <Label>{t("capture.counts")}</Label>
            <div className="grid grid-cols-3 gap-2">
              {(["likes", "comments", "shares"] as const).map((k) => (
                <Input key={k} type="number" min={0} placeholder={t(`monitoring.${k}`)} value={counts[k]} onChange={(e) => setCounts({ ...counts, [k]: e.target.value })} />
              ))}
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="ct">{t("capture.commentsText")}</Label>
            <Textarea id="ct" rows={3} value={commentsText} onChange={(e) => setCommentsText(e.target.value)} />
          </div>
          {error ? <p className="text-sm text-status-block">{error}</p> : null}
          <div>
            <Button onClick={submit} disabled={busy || !can("case.capture") || (!text.trim() && !file)}>
              {busy ? <Loader2 className="animate-spin" /> : null}
              {busy ? t("capture.submitting") : t("capture.submit")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
