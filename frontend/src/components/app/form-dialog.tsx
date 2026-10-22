"use client";

import { useState } from "react";

import { useStateResetOn } from "@/lib/hooks";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { t } from "@/i18n";
import { ApiError } from "@/lib/api/client";

export type FieldSpec = {
  name: string;
  label: string;
  type?: "text" | "textarea" | "number" | "date" | "select" | "checkbox" | "tags" | "file";
  options?: { value: string; label: string }[];
  required?: boolean;
  placeholder?: string;
  help?: string;
  rows?: number;
  accept?: string;
  colSpan?: 1 | 2;
};

export type FormValues = Record<string, unknown>;

const NONE = "__none__";

function toInputDate(v: unknown): string {
  if (!v || typeof v !== "string") return "";
  return v.slice(0, 10);
}

export function FormDialog({
  open,
  onOpenChange,
  title,
  description,
  fields,
  initial,
  submitLabel,
  onSubmit,
  wide,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  fields: FieldSpec[];
  initial?: FormValues;
  submitLabel?: string;
  onSubmit: (values: FormValues) => Promise<unknown>;
  wide?: boolean;
}) {
  const [values, setValues] = useStateResetOn<FormValues>(open, () => initial ?? {});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useStateResetOn<string | null>(open, () => null);

  const set = (name: string, value: unknown) => setValues((prev) => ({ ...prev, [name]: value }));
  const missing = fields.some((f) => f.required && (values[f.name] === undefined || values[f.name] === null || values[f.name] === ""));

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const out: FormValues = {};
      for (const f of fields) {
        let v = values[f.name];
        if (f.type === "number") v = v === "" || v === undefined || v === null ? null : Number(v);
        if (f.type === "date") v = v ? `${String(v).slice(0, 10)}T00:00:00Z` : null;
        if (f.type === "select" && v === NONE) v = null;
        if (f.type === "tags") v = Array.isArray(v) ? v : String(v ?? "").split(",").map((s) => s.trim()).filter(Boolean);
        out[f.name] = v;
      }
      await onSubmit(out);
      toast.success(t("common.saved"));
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={wide ? "sm:max-w-3xl" : "sm:max-w-lg"}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>
        <div className="grid max-h-[65vh] grid-cols-2 gap-3 overflow-y-auto pr-1">
          {fields.map((f) => {
            const id = `fd-${f.name}`;
            const v = values[f.name];
            const span = f.colSpan === 1 ? "col-span-1" : "col-span-2";
            return (
              <div key={f.name} className={`grid gap-1.5 ${span}`}>
                {f.type === "checkbox" ? (
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox id={id} checked={Boolean(v)} onCheckedChange={(c) => set(f.name, Boolean(c))} />
                    {f.label}
                  </label>
                ) : (
                  <Label htmlFor={id}>
                    {f.label}
                    {f.required ? " *" : ""}
                  </Label>
                )}
                {f.type === "textarea" ? (
                  <Textarea id={id} rows={f.rows ?? 4} value={String(v ?? "")} placeholder={f.placeholder} onChange={(e) => set(f.name, e.target.value)} />
                ) : f.type === "select" ? (
                  <Select value={v === null || v === undefined || v === "" ? NONE : String(v)} onValueChange={(nv) => set(f.name, nv)}>
                    <SelectTrigger id={id} className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {!f.required ? <SelectItem value={NONE}>{t("common.none")}</SelectItem> : null}
                      {(f.options ?? []).map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : f.type === "checkbox" ? null : f.type === "file" ? (
                  <Input id={id} type="file" accept={f.accept} onChange={(e) => set(f.name, e.target.files?.[0] ?? null)} />
                ) : (
                  <Input
                    id={id}
                    type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                    step={f.type === "number" ? "any" : undefined}
                    value={f.type === "date" ? toInputDate(v) : f.type === "tags" && Array.isArray(v) ? v.join(", ") : String(v ?? "")}
                    placeholder={f.placeholder}
                    onChange={(e) => set(f.name, e.target.value)}
                  />
                )}
                {f.help ? <p className="text-xs text-muted-foreground">{f.help}</p> : null}
              </div>
            );
          })}
        </div>
        {error ? <p className="text-sm text-status-block">{error}</p> : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button disabled={busy || missing} onClick={submit}>
            {busy ? t("common.saving") : (submitLabel ?? t("common.save"))}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Build multipart form data from FormDialog values (files and scalars). */
export function toFormData(values: FormValues): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(values)) {
    if (v === null || v === undefined || v === "") continue;
    if (v instanceof File) fd.append(k, v);
    else if (Array.isArray(v)) fd.append(k, v.join(","));
    else fd.append(k, String(v));
  }
  return fd;
}
