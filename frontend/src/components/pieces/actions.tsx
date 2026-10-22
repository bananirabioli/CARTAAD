"use client";

import { CheckCircle2, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ReasonDialog } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { t } from "@/i18n";
import { api, refresh } from "@/lib/api/client";

import { errMsg, type PieceD } from "./parts";

/** Approve / discard. Approval is gated server-side by HR-09 (figures verified, legal, consent, no blocking findings). */
export function PieceActions({ piece, onChange }: { piece: PieceD; onChange: (p: PieceD) => void }) {
  const { can } = useSession();
  const [discardOpen, setDiscardOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!["generado", "bloqueado", "aprobado"].includes(piece.status)) return null;

  async function approve() {
    setBusy(true);
    try {
      onChange(await api.post<PieceD>(`/pieces/${piece.id}/approve`, { note: "" }));
      await refresh("/inbox", "/cases", "/proposals", "/dashboard");
      toast.success(t("inbox.approved"));
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {can("piece.approve") && piece.status !== "aprobado" ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <span>
              <Button disabled={busy || !piece.approvable} onClick={approve}>
                <CheckCircle2 />
                {t("inbox.approve")}
              </Button>
            </span>
          </TooltipTrigger>
          {!piece.approvable ? <TooltipContent className="max-w-xs text-xs">{piece.approval_blockers?.join(" · ")}</TooltipContent> : null}
        </Tooltip>
      ) : null}
      {can("piece.discard") ? (
        <Button variant="outline" onClick={() => setDiscardOpen(true)}>
          <Trash2 />
          {t("inbox.discard")}
        </Button>
      ) : null}
      <ReasonDialog
        open={discardOpen}
        onOpenChange={setDiscardOpen}
        title={t("inbox.discard")}
        onConfirm={async (reason) => {
          onChange(await api.post<PieceD>(`/pieces/${piece.id}/discard`, { reason }));
          await refresh("/inbox", "/cases", "/proposals");
        }}
      />
    </div>
  );
}
