"use client";

import { Download, ShieldCheck } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Loading } from "@/components/app/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fmtDate, t } from "@/i18n";
import { api, ApiError, useApi, type Schemas } from "@/lib/api/client";

/** Public page (token + expiry, no login) with the approved pieces for allies and spokespeople. */
export default function AllyPackagePage() {
  const { token } = useParams<{ token: string }>();
  const { data, error, isLoading } = useApi<Schemas["PublicPackage"]>(`/public/ally/${token}`, { shouldRetryOnError: false });
  const [account, setAccount] = useState("");
  const [name, setName] = useState("");
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (isLoading) return <Loading className="p-8" />;
  if (error || !data) return <div className="p-10 text-center text-sm text-muted-foreground">{t("ally.expired")}</div>;
  return (
    <div className="mx-auto grid max-w-4xl gap-5 p-6">
      <div className="flex items-center gap-2 text-primary"><ShieldCheck className="size-5" /><span className="text-sm font-semibold">{t("app.name")}</span></div>
      <div>
        <h1 className="text-2xl font-semibold">{data.title}</h1>
        <p className="text-sm text-muted-foreground">{t("ally.from", { client: data.client_name })} · {t("ally.expires", { date: fmtDate(data.expires_at) })}</p>
        {data.message ? <p className="mt-2">{data.message}</p> : null}
      </div>
      {data.suggested_copy ? (
        <Card className="gap-2 py-4">
          <CardHeader className="px-4"><CardTitle className="text-sm">{t("ally.suggested")}</CardTitle></CardHeader>
          <CardContent className="px-4"><p className="whitespace-pre-line text-sm">{data.suggested_copy}</p></CardContent>
        </Card>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        {data.pieces.map((p) => (
          <Card key={p.id} className="gap-2 overflow-hidden py-0">
            {p.images.length ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={p.images[0]} alt="" className="w-full" />
            ) : null}
            <CardContent className="p-3 text-xs text-muted-foreground whitespace-pre-line">{p.text}</CardContent>
          </Card>
        ))}
      </div>
      <Button asChild className="w-fit"><a href={data.download_url}><Download />{t("ally.download")}</a></Button>
      <Card className="gap-3 py-4">
        <CardHeader className="px-4"><CardTitle className="text-sm">{t("ally.markShared")}</CardTitle></CardHeader>
        <CardContent className="grid gap-3 px-4">
          <p className="text-xs text-muted-foreground">{t("ally.onlyRegistered")}</p>
          {done ? <p className="text-sm text-status-ok">{t("ally.thanks")}</p> : (
            <>
              <div className="grid gap-1.5"><Label>{t("ally.account")}</Label>
                <Select value={account} onValueChange={setAccount}>
                  <SelectTrigger className="w-full"><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>{data.accounts.map((a) => <SelectItem key={String(a.id)} value={String(a.id)}>{String(a.name)} · {String(a.handle)}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5"><Label>{t("ally.name")}</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
              {err ? <p className="text-sm text-status-block">{err}</p> : null}
              <Button
                className="w-fit"
                disabled={!account || name.trim().length < 2}
                onClick={async () => {
                  try {
                    await api.post(`/public/ally/${token}/shared`, { account_id: Number(account), shared_by_name: name });
                    setDone(true);
                  } catch (e) {
                    setErr(e instanceof ApiError ? e.message : String(e));
                  }
                }}
              >
                {t("ally.markShared")}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
