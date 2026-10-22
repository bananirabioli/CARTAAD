"use client";

import Link from "next/link";
import { useState } from "react";

import { AlertBadge, Sparkline } from "@/components/app/badges";
import { KeyValue, Loading } from "@/components/app/common";
import { FormDialog } from "@/components/app/form-dialog";
import { useSession } from "@/components/app/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { fmtDate, fmtNum, t, tEnum } from "@/i18n";
import { api, fileUrl, refresh, useApi, type Schemas } from "@/lib/api/client";

export function PostSheet({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { can } = useSession();
  const { data: p, mutate } = useApi<Schemas["PostDetail"]>(id ? `/posts/${id}` : null);
  const [snapOpen, setSnapOpen] = useState(false);
  const points = (p?.snapshots ?? []).map((s) => ({ x: new Date(s.taken_at).getTime(), y: s.likes + s.comments + s.shares }));
  return (
    <Sheet open={id !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        {!p ? <Loading className="p-6" /> : (
          <>
            <SheetHeader>
              <SheetTitle className="flex flex-wrap items-center gap-2">
                {p.source_name ?? tEnum("origin", p.origin)} <AlertBadge level={p.alert_level} ratio={p.alert_ratio} />
              </SheetTitle>
            </SheetHeader>
            <div className="grid gap-4 px-4 pb-8 text-sm">
              {p.image_key ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={fileUrl(p.image_key)} alt="" className="max-h-80 rounded border object-contain" />
              ) : null}
              <p className="whitespace-pre-line">{p.text}</p>
              <div className="grid grid-cols-2 gap-3">
                <KeyValue label={t("monitoring.published")}>{fmtDate(p.published_at)}</KeyValue>
                <KeyValue label={t("monitoring.network")}>{tEnum("network", p.network)}</KeyValue>
                <KeyValue label={t("monitoring.velocity")}>{t("monitoring.velocityValue", { value: fmtNum(p.velocity ?? 0, 1) })}</KeyValue>
                <KeyValue label={t("monitoring.baseline")}>{p.baseline_per_hour ? t("monitoring.baselinePerHour", { value: fmtNum(p.baseline_per_hour, 1) }) : t("monitoring.baselineInsufficient")}</KeyValue>
                <KeyValue label={t("monitoring.interactions")}>{fmtNum(p.total_interactions)}</KeyValue>
                <KeyValue label={t("monitoring.case")}>{p.case_id ? <Link className="text-primary hover:underline" href={`/casos/${p.case_id}`}>{p.case_code}</Link> : t("monitoring.noCase")}</KeyValue>
              </div>
              {p.visual_context ? <KeyValue label={t("monitoring.visualContext")}>{p.visual_context}</KeyValue> : null}
              {p.names_blurred ? <Badge variant="secondary">{t("monitoring.blurred")}</Badge> : null}
              <div className="grid gap-1">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("monitoring.snapshots")}</p>
                  {can("case.capture") ? <Button size="xs" variant="outline" onClick={() => setSnapOpen(true)}>{t("monitoring.addSnapshot")}</Button> : null}
                </div>
                <Sparkline points={points} width={420} height={60} />
                <p className="text-xs text-muted-foreground">
                  {(p.snapshots ?? []).slice(-1).map((s) => `${t("monitoring.likes")}: ${fmtNum(s.likes)} · ${t("monitoring.comments")}: ${fmtNum(s.comments)} · ${t("monitoring.shares")}: ${fmtNum(s.shares)}`)}
                </p>
              </div>
              <div className="grid gap-1">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("monitoring.commentsAgg")}</p>
                {(p.comments ?? []).length ? (
                  <ul className="grid gap-1 text-xs">
                    {(p.comments ?? []).map((c) => <li key={c.id} className="rounded bg-muted px-2 py-1">{c.text}</li>)}
                  </ul>
                ) : <p className="text-xs text-muted-foreground">{t("common.empty")}</p>}
              </div>
            </div>
            <FormDialog
              open={snapOpen}
              onOpenChange={setSnapOpen}
              title={t("monitoring.addSnapshot")}
              fields={[
                { name: "likes", label: t("monitoring.likes"), type: "number", required: true, colSpan: 1 },
                { name: "comments", label: t("monitoring.comments"), type: "number", required: true, colSpan: 1 },
                { name: "shares", label: t("monitoring.shares"), type: "number", required: true, colSpan: 1 },
              ]}
              onSubmit={async (val) => {
                await api.post(`/posts/${p.id}/snapshots`, val);
                await mutate();
                await refresh("/posts");
              }}
            />
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
