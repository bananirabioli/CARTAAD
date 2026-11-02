"use client";

import { ImageUp, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

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
import { api, ApiError, fileUrl, refresh, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

/** Re-encode any picked/pasted image (HEIC from iPhone, huge screenshots, nameless clipboard blobs) as a JPEG ≤ 2000 px. */
async function toUploadable(file: File): Promise<File> {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, 2000 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    return blob ? new File([blob], "captura.jpg", { type: "image/jpeg" }) : file;
  } catch {
    return file; // the browser cannot decode it: let the API answer with a clear error
  }
}

export default function CapturePage() {
  const { can } = useSession();
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [network, setNetwork] = useState("facebook");
  const [blur, setBlur] = useState(true);
  const [counts, setCounts] = useState({ likes: "", comments: "", shares: "" });
  const [commentsText, setCommentsText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Schemas["PostDetail"] | null>(null);

  function pick(f: File | null | undefined) {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  // Ctrl+V / Cmd+V pastes a screenshot straight from the clipboard.
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith("image/"));
      const f = item?.getAsFile();
      if (f) pick(f);
    }
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, []);

  function reset() {
    setFile(null);
    setPreview(null);
    setText("");
    setUrl("");
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
      for (const [k, v] of Object.entries(counts)) if (v !== "") fd.append(k, v);
      if (commentsText.trim()) fd.append("comments_text", commentsText);
      if (file) fd.append("image", await toUploadable(file), "captura.jpg");
      const post = await api.upload<Schemas["PostDetail"]>("/posts/manual", fd);
      await refresh("/posts", "/cases", "/dashboard");
      if (post.case_id) router.push(`/casos/${post.case_id}`);
      else setResult(post);
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
      <PageHeader title={t("mvp.captureTitle")} subtitle={t("mvp.captureSubtitle")} />
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
          <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
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
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label>{t("capture.network")}</Label>
              <Select value={network} onValueChange={setNetwork}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>{enumOptions("network").map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <label className="flex items-start gap-3 rounded-md border p-3">
            <Switch checked={blur} onCheckedChange={setBlur} />
            <span className="grid gap-0.5">
              <span className="text-sm font-medium">{t("capture.blur")}</span>
              <span className="text-xs text-muted-foreground">{t("capture.blurHint")}</span>
            </span>
          </label>
          <details className="rounded-md border p-3">
            <summary className="cursor-pointer text-sm">{t("mvp.optionalData")}</summary>
            <div className="mt-3 grid gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="url">{t("capture.url")}</Label>
                <Input id="url" value={url} onChange={(e) => setUrl(e.target.value)} />
              </div>
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
            </div>
          </details>
          {error ? <p className="text-sm text-status-block">{error}</p> : null}
          <div>
            <Button onClick={submit} disabled={busy || !can("case.capture") || (!text.trim() && !file)}>
              {busy ? <Loader2 className="animate-spin" /> : null}
              {busy ? t("mvp.analyzing") : t("mvp.analyze")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
