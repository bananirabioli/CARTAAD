"use client";

import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { t } from "@/i18n";
import type { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Loading({ label, className }: { label?: string; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2 py-8 text-sm text-muted-foreground", className)}>
      <Loader2 className="size-4 animate-spin" />
      {label ?? t("common.loading")}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError | Error | undefined; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-status-block/30 bg-status-block/5 p-4 text-sm">
      <AlertTriangle className="mt-0.5 size-4 text-status-block" />
      <div className="flex-1">
        <p className="font-medium">{t("common.error")}</p>
        <p className="text-muted-foreground">{error?.message}</p>
      </div>
      {onRetry ? (
        <Button size="sm" variant="outline" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ label, children }: { label?: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
      <Inbox className="size-5" />
      <p>{label ?? t("common.empty")}</p>
      {children}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-muted-foreground">
      <span>{t("common.total", { count: total })}</span>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          {t("common.prev")}
        </Button>
        <span>{t("common.page", { page, pages })}</span>
        <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          {t("common.next")}
        </Button>
      </div>
    </div>
  );
}

export function ReasonDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  required = true,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  onConfirm: (reason: string) => Promise<void> | void;
  required?: boolean;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const invalid = required && reason.trim().length < 3;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="reason">{t("common.reason")}</Label>
          <Textarea id="reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={3} />
          {invalid && reason ? <p className="text-xs text-status-block">{t("common.reasonRequired")}</p> : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button
            disabled={invalid || busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirm(reason.trim());
                setReason("");
                onOpenChange(false);
              } finally {
                setBusy(false);
              }
            }}
          >
            {confirmLabel ?? t("common.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function KeyValue({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("grid gap-0.5", className)}>
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
      <div className="text-sm">{children}</div>
    </div>
  );
}

export function JsonBlock({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="text-muted-foreground">{t("common.none")}</span>;
  return <pre className="max-h-48 overflow-auto rounded bg-muted p-2 font-mono text-[11px] leading-snug">{JSON.stringify(value, null, 1)}</pre>;
}
