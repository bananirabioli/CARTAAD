"use client";

import { ShieldAlert } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/i18n";
import { api, ApiError, useApi, type Schemas } from "@/lib/api/client";

const DEMO_PASSWORD = "demo1234";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("analista@demo.mx");
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: demoUsers } = useApi<Schemas["UserOut"][]>("/auth/demo-users", { shouldRetryOnError: false });

  async function submit(e?: React.FormEvent, as?: string) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/login", { email: as ?? email, password: as ? DEMO_PASSWORD : password });
      router.replace(params.get("next") ?? "/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <div className="grid w-full max-w-4xl gap-6 md:grid-cols-2">
        <div className="flex flex-col justify-center gap-3">
          <div className="flex items-center gap-2 text-primary">
            <ShieldAlert className="size-7" />
            <span className="text-2xl font-semibold tracking-wide">{t("app.name")}</span>
          </div>
          <p className="text-lg">{t("app.fullName")}</p>
          <p className="text-sm text-muted-foreground">{t("app.tagline")}</p>
          <p className="text-xs text-muted-foreground">{t("app.beta")}</p>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{t("auth.title")}</CardTitle>
            <CardDescription>{t("auth.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <form className="grid gap-3" onSubmit={submit}>
              <div className="grid gap-1.5">
                <Label htmlFor="email">{t("auth.email")}</Label>
                <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="password">{t("auth.password")}</Label>
                <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
              </div>
              {error ? <p className="text-sm text-status-block">{error}</p> : null}
              <Button type="submit" disabled={busy}>
                {busy ? t("auth.submitting") : t("auth.submit")}
              </Button>
            </form>
            {demoUsers?.length ? (
              <div className="grid gap-2 border-t pt-3">
                <p className="text-xs font-medium text-muted-foreground">{t("auth.demoUsers")}</p>
                <div className="flex flex-wrap gap-2">
                  {demoUsers.map((u) => (
                    <Button key={u.id} size="sm" variant="outline" disabled={busy} onClick={() => submit(undefined, u.email)}>
                      {t(`roles.${u.role}`)}
                      {u.kb_owner ? ` · ${t("roles.kb_owner")}` : ""}
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">{t("auth.demoHint", { password: DEMO_PASSWORD })}</p>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
