"use client";

import { PageHeader } from "@/components/app/common";
import { useSession } from "@/components/app/session";
import { t } from "@/i18n";

export default function DashboardPage() {
  const { me } = useSession();
  return (
    <div>
      <PageHeader title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />
      <p className="text-sm text-muted-foreground">{t("dashboard.welcome", { name: me?.user.name })}</p>
    </div>
  );
}
