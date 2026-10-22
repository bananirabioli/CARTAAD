"use client";

import { Check, ImageOff, Loader2, RotateCcw, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useSession } from "@/components/app/session";
import { SourceBadge } from "@/components/app/source-badge";
import { FindingList } from "@/components/styles/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { fmtDate, t, tEnum } from "@/i18n";
import { api, ApiError, fileUrl, refresh, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export type PieceD = Schemas["PieceDetail"];
export type PieceS = Schemas["PieceOut"];

export function errMsg(err: unknown) {
  return err instanceof ApiError ? (err.ruleId ? `[${err.ruleId}] ${err.message}` : err.message) : String(err);
}

const PIECE_STATUS: Record<string, string> = {
  generado: "bg-status-info/15 text-status-info",
  bloqueado: "bg-status-block/15 text-status-block",
  aprobado: "bg-status-ok/15 text-status-ok",
  descartado: "bg-muted text-muted-foreground line-through",
  programado: "bg-status-ok/25 text-status-ok",
  publicado: "bg-status-ok/30 text-status-ok",
};

export function PieceStatusBadge({ status }: { status: string }) {
  return <Badge className={cn("border-transparent", PIECE_STATUS[status])}>{tEnum("piece_status", status)}</Badge>;
}

const VAL: Record<string, string> = {
  ok: "border-status-ok/40 text-status-ok",
  warn: "border-status-warn/50 text-status-warn",
  block: "border-status-block/50 text-status-block",
};

export function ValidationBadge({ status }: { status: string }) {
  return <Badge variant="outline" className={VAL[status]}>{tEnum("validation", status)}</Badge>;
}

const SEG_CLASS: Record<string, string> = {
  asercion_factual: "bg-status-ok/10 decoration-status-ok/60",
  opinion_marcada: "",
  pregunta: "italic",
  llamado: "font-medium",
  saludo: "text-muted-foreground",
};

/** Copy with each factual segment followed by its source badges (HR-01). */
export function CopyText({ piece, facts }: { piece: { content: Record<string, unknown> }; facts: Schemas["FactOut"][] }) {
  const byId = new Map(facts.map((f) => [f.id, f]));
  const segs = (piece.content.segments as { text: string; type: string; fact_ids: number[] }[] | undefined) ?? [];
  const legends = (piece.content.legends as string[] | undefined) ?? [];
  return (
    <div className="grid min-w-0 grid-cols-1 gap-2 text-sm leading-relaxed break-words">
      <p>
        {segs.map((s, i) => (
          <span key={i} className={cn("rounded px-0.5", SEG_CLASS[s.type])} title={tEnum("segment_type", s.type)}>
            {s.text}
            {s.fact_ids.map((id) => {
              const f = byId.get(id);
              return f ? <SourceBadge key={id} fact={f} className="ml-1" /> : <Badge key={id} variant="outline" className="ml-1 font-mono text-[10px]">#{id}</Badge>;
            })}{" "}
          </span>
        ))}
      </p>
      {legends.map((l) => <p key={l} className="text-xs font-semibold">{l}</p>)}
    </div>
  );
}

export function CreativeThumb({ piece, className }: { piece: PieceS; className?: string }) {
  if (piece.render_status === "no_aplica") {
    const slides = (piece.content.slides as { title: string; text: string }[] | undefined) ?? [];
    return (
      <div className={cn("grid content-start gap-1 overflow-hidden rounded-md border bg-muted/40 p-3 text-xs", className)}>
        {slides.map((s, i) => <p key={i}><span className="font-semibold">{s.title}:</span> {s.text}</p>)}
      </div>
    );
  }
  if (piece.render_status === "pendiente") return <div className={cn("flex items-center justify-center rounded-md border bg-muted", className)}><Loader2 className="size-5 animate-spin" /></div>;
  if (!piece.renders.length) return <div className={cn("flex items-center justify-center rounded-md border bg-muted text-muted-foreground", className)}><ImageOff className="size-5" /></div>;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={fileUrl(piece.renders[0])} alt="" className={cn("rounded-md border object-cover", className)} />;
}

export function FiguresPanel({ piece, onChange }: { piece: PieceD; onChange: (p: PieceD) => void }) {
  const { can } = useSession();
  const facts = new Map((piece.facts ?? []).map((f) => [f.id, f]));
  async function verify(id: number, status: string) {
    try {
      onChange(await api.post<PieceD>(`/pieces/${piece.id}/figures/${id}/verify`, { status }));
      await refresh("/pieces", "/inbox");
    } catch (err) {
      toast.error(errMsg(err));
    }
  }
  if (!piece.figures?.length) return <p className="text-xs text-muted-foreground">{t("common.empty")}</p>;
  return (
    <div className="grid gap-1.5">
      <p className="text-[11px] text-muted-foreground">{t("editor.figuresHelp")}</p>
      {piece.figures.map((f) => {
        const fact = f.fact_id ? facts.get(f.fact_id) : undefined;
        return (
          <div key={f.id} className="flex items-center gap-2 rounded border px-2 py-1.5 text-xs">
            <span className="font-mono font-semibold">{f.raw}</span>
            <span className="truncate text-muted-foreground">{f.location}</span>
            {fact ? <SourceBadge fact={fact} /> : <span className="text-status-block">{t("editor.unmatched")}</span>}
            <span className="ml-auto" />
            <Badge variant="outline" className={cn(f.status === "verificada" && "border-status-ok/50 text-status-ok", f.status === "rechazada" && "border-status-block/50 text-status-block")}>{tEnum("figure_status", f.status)}</Badge>
            {can("figure.verify") && f.status === "pendiente" && ["generado", "bloqueado"].includes(piece.status) ? (
              <>
                <Button size="icon-xs" variant="outline" aria-label={t("editor.verify")} onClick={() => verify(f.id, "verificada")}><Check /></Button>
                <Button size="icon-xs" variant="ghost" aria-label={t("editor.reject")} onClick={() => verify(f.id, "rechazada")}><X /></Button>
              </>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export function RedTeamPanel({ notes }: { notes: Schemas["RedTeamNoteOut"][] }) {
  if (!notes.length) return <p className="text-xs text-muted-foreground">{t("common.empty")}</p>;
  return (
    <ul className="grid gap-1.5 text-xs">
      {notes.map((n) => (
        <li key={n.id} className="flex gap-2">
          <Badge variant="outline" className={cn("shrink-0", n.severity === "alta" && "border-status-block/50 text-status-block", n.severity === "media" && "border-status-warn/50 text-status-warn")}>
            {tEnum("severity", n.severity)}
          </Badge>
          <span><span className="font-medium">{tEnum("redteam_kind", n.kind)}:</span> {n.text}</span>
        </li>
      ))}
    </ul>
  );
}

function Diff({ ops }: { ops: Record<string, unknown>[] }) {
  return (
    <p className="text-xs leading-relaxed">
      {ops.map((o, i) =>
        o.op === "insert" ? <ins key={i} className="bg-status-ok/20 no-underline">{String(o.text)}</ins> : o.op === "delete" ? <del key={i} className="bg-status-block/15 text-muted-foreground">{String(o.text)}</del> : <span key={i}>{String(o.text)}</span>,
      )}
    </p>
  );
}

export function VersionsPanel({ piece, onChange }: { piece: PieceD; onChange: (p: PieceD) => void }) {
  const { can } = useSession();
  const [open, setOpen] = useState<number | null>(piece.versions?.[0]?.version ?? null);
  return (
    <div className="grid gap-1.5">
      {(piece.versions ?? []).map((v) => (
        <div key={v.id} className="rounded border">
          <button className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-xs" onClick={() => setOpen(open === v.version ? null : v.version)}>
            <span className="font-mono font-semibold">v{v.version}</span>
            {v.version === piece.current_version ? <Badge variant="secondary">{t("editor.current")}</Badge> : null}
            <Badge variant="outline">{tEnum("copilot_action", v.action)}</Badge>
            <Badge variant="outline" className={v.author_type === "ia" ? "border-status-info/40 text-status-info" : ""}>{tEnum("author_type", v.author_type)}</Badge>
            <span className="truncate text-muted-foreground">{v.author_name ?? ""} {v.instruction ? `· «${v.instruction}»` : ""}</span>
            <span className="ml-auto shrink-0 text-muted-foreground">{fmtDate(v.created_at)}</span>
          </button>
          {open === v.version ? (
            <div className="grid gap-2 border-t px-2 py-2">
              <p className="text-[11px] text-muted-foreground">{v.style_slug} v{v.style_version} · {tEnum("strategy", v.strategy)} · intensidad {v.intensity}{v.note ? ` · ${v.note}` : ""}</p>
              {v.diff.length ? <Diff ops={v.diff} /> : null}
              {v.version !== piece.current_version && can("piece.edit") && !["programado", "publicado", "descartado"].includes(piece.status) ? (
                <Button
                  size="xs"
                  variant="outline"
                  className="w-fit"
                  onClick={async () => {
                    try {
                      onChange(await api.post<PieceD>(`/pieces/${piece.id}/revert`, { version: v.version }));
                      await refresh("/pieces", "/proposals", "/cases");
                    } catch (err) {
                      toast.error(errMsg(err));
                    }
                  }}
                >
                  <RotateCcw />
                  {t("editor.revert")}
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

const QUICK = ["mas_corto", "mas_firme", "mas_formal", "menos_formal", "mas_empatico", "otro_angulo", "agregar_dato"] as const;

export function CopilotPanel({ piece, onChange }: { piece: PieceD; onChange: (p: PieceD) => void }) {
  const { can } = useSession();
  const [instruction, setInstruction] = useState("");
  const [style, setStyle] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [last, setLast] = useState<{ applied: boolean; message: string; suggested?: string | null } | null>(null);
  const locked = ["programado", "publicado", "descartado"].includes(piece.status) || !can("copilot.use");

  async function run(action: string, extra: Record<string, unknown> = {}) {
    setBusy(action);
    try {
      const r = await api.post<Schemas["CopilotOut"]>(`/pieces/${piece.id}/copilot`, { action, ...extra });
      onChange(r.piece);
      setLast({ applied: r.applied, message: r.applied ? `${t("editor.applied", { version: r.version ?? "" })} · ${r.message}` : r.message, suggested: r.suggested_style });
      if (r.applied) await refresh("/pieces", "/proposals", "/cases");
    } catch (err) {
      setLast({ applied: false, message: errMsg(err) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="grid gap-3">
      <p className="text-[11px] text-muted-foreground">{t("editor.copilotHelp")}</p>
      {piece.style_intensity?.length ? (
        <p className="text-[11px]">{t("editor.styleLimits", { min: piece.style_intensity[0], max: piece.style_intensity[1], current: piece.intensity })}</p>
      ) : null}
      <div className="flex flex-wrap gap-1.5">
        {QUICK.map((a) => (
          <Button key={a} size="xs" variant="outline" disabled={locked || busy !== null} onClick={() => run(a)}>
            {busy === a ? <Loader2 className="animate-spin" /> : null}
            {tEnum("copilot_action", a)}
          </Button>
        ))}
      </div>
      <div className="flex gap-2">
        <Select value={style} onValueChange={setStyle}>
          <SelectTrigger size="sm" className="flex-1"><SelectValue placeholder={t("editor.changeStyleTo")} /></SelectTrigger>
          <SelectContent>
            {(piece.allowed_styles ?? []).filter((s) => s !== piece.style_slug).map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button size="sm" variant="outline" disabled={locked || !style || busy !== null} onClick={() => run("cambiar_estilo", { style_slug: style })}>{tEnum("copilot_action", "cambiar_estilo")}</Button>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="cp-instr">{tEnum("copilot_action", "libre")}</Label>
        <Textarea id="cp-instr" rows={2} placeholder={t("editor.copilotPlaceholder")} value={instruction} onChange={(e) => setInstruction(e.target.value)} />
        <Button size="sm" className="w-fit" disabled={locked || !instruction.trim() || busy !== null} onClick={() => run("libre", { instruction })}>
          <Sparkles />
          {t("editor.send")}
        </Button>
      </div>
      {last ? (
        <div className={cn("rounded-md border p-2 text-xs", last.applied ? "border-status-ok/40 bg-status-ok/5" : "border-status-warn/50 bg-status-warn/5")}>
          {!last.applied ? <p className="font-medium">{t("editor.refused")}</p> : null}
          <p>{last.message}</p>
          {last.suggested ? (
            <Button size="xs" variant="outline" className="mt-1" disabled={locked} onClick={() => run("cambiar_estilo", { style_slug: last.suggested })}>
              {t("editor.changeStyleTo")} {last.suggested}
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function PieceLegalPanel({ piece, onChange }: { piece: PieceD; onChange: (p: PieceD) => void }) {
  const { can } = useSession();
  const [note, setNote] = useState("");
  if (!piece.legal_required) return null;
  async function act(action: string) {
    try {
      onChange(await api.post<PieceD>(`/pieces/${piece.id}/legal`, { action, note }));
      await refresh("/pieces", "/inbox");
    } catch (err) {
      toast.error(errMsg(err));
    }
  }
  return (
    <div className="grid gap-2 text-xs">
      <div className="flex items-center gap-2"><Badge variant="outline" className="border-veda/50 text-veda">{tEnum("legal_status", piece.legal_status)}</Badge><span>{piece.legal_reason}</span></div>
      {piece.legal_note ? <p className="rounded bg-muted p-2">{piece.legal_note}</p> : null}
      {can("piece.legal") && piece.legal_status === "pendiente" ? (
        <>
          <Textarea rows={2} placeholder={t("editor.legalNote")} value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex gap-2">
            <Button size="xs" disabled={note.trim().length < 3} onClick={() => act("liberar")}>{t("cases.legalRelease")}</Button>
            <Button size="xs" variant="destructive" disabled={note.trim().length < 3} onClick={() => act("bloquear")}>{t("cases.legalBlock")}</Button>
          </div>
        </>
      ) : null}
    </div>
  );
}

export function ConsentPanel({ piece, onChange }: { piece: PieceD; onChange: (p: PieceD) => void }) {
  const { can } = useSession();
  const [person, setPerson] = useState("");
  const [testimony, setTestimony] = useState("");
  const [signed, setSigned] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  if (piece.creative_slug !== "voz_ciudadana") return null;
  const consent = piece.consent as { person_label?: string } | null;
  return (
    <div className="grid gap-2 text-xs">
      <p className="text-muted-foreground">{t("editor.consentHelp")}</p>
      {consent ? <p className="text-status-ok">{t("editor.consentAttached", { name: consent.person_label ?? "" })}</p> : null}
      {can("piece.edit") ? (
        <>
          <Label>{t("editor.consentPerson")}</Label>
          <Input value={person} onChange={(e) => setPerson(e.target.value)} />
          <Label>{t("editor.consentTestimony")}</Label>
          <Textarea rows={3} value={testimony} onChange={(e) => setTestimony(e.target.value)} />
          <Label>{t("editor.consentSigned")}</Label>
          <Input type="date" value={signed} onChange={(e) => setSigned(e.target.value)} />
          <Label>{t("editor.consentFile")}</Label>
          <Input type="file" accept="application/pdf,image/png,image/jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <Button
            size="xs"
            className="w-fit"
            disabled={busy || !person.trim() || !testimony.trim() || !file}
            onClick={async () => {
              setBusy(true);
              try {
                const fd = new FormData();
                fd.append("person_label", person);
                fd.append("testimony", testimony);
                if (signed) fd.append("signed_at", `${signed}T00:00:00Z`);
                if (file) fd.append("file", file);
                onChange(await api.upload<PieceD>(`/pieces/${piece.id}/consent`, fd));
              } catch (err) {
                toast.error(errMsg(err));
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("common.save")}
          </Button>
        </>
      ) : null}
    </div>
  );
}

export function ValidationFindings({ piece }: { piece: PieceS }) {
  return <FindingList findings={piece.validation as never} />;
}
