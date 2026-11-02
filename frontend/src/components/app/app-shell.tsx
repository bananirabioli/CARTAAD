"use client";

import {
  Activity,
  BookOpen,
  Camera,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Palette,
  Settings,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { fmtDate, t, tEnum } from "@/i18n";
import { cn } from "@/lib/utils";

import { ErrorState, Loading } from "./common";
import { SessionProvider, useSession } from "./session";

type NavItem = { href: string; label: string; icon: React.ComponentType<{ className?: string }> };

// MVP: one short flow (capture → analysis → generate) plus the catalogs. The other screens still exist by URL.
const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "nav.sectionOperation",
    items: [
      { href: "/", label: "nav.dashboard", icon: LayoutDashboard },
      { href: "/captura", label: "nav.capture", icon: Camera },
      { href: "/casos", label: "nav.cases", icon: FolderOpen },
    ],
  },
  {
    section: "nav.sectionKnowledge",
    items: [
      { href: "/base", label: "nav.facts", icon: BookOpen },
      { href: "/estilos", label: "nav.catalogs", icon: Palette },
    ],
  },
  {
    section: "nav.sectionAdmin",
    items: [{ href: "/configuracion", label: "nav.settings", icon: Settings }],
  },
];

const VIEW_AS: { role: string; kb: boolean; label: string }[] = [
  { role: "analista", kb: false, label: "roles.analista" },
  { role: "aprobador", kb: false, label: "roles.aprobador" },
  { role: "legal", kb: false, label: "roles.legal" },
  { role: "diseno", kb: false, label: "roles.diseno" },
  { role: "admin", kb: false, label: "roles.admin" },
  { role: "analista", kb: true, label: "roles.kb_owner" },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-sidebar text-sidebar-foreground md:flex">
      <div className="flex items-center gap-2 px-4 py-4">
        <ShieldAlert className="size-5 text-sidebar-primary" />
        <div className="leading-tight">
          <div className="text-sm font-semibold tracking-wide">{t("app.name")}</div>
          <div className="text-[10px] text-sidebar-foreground/60">{t("app.beta")}</div>
        </div>
      </div>
      <nav className="flex-1 space-y-4 overflow-y-auto px-2 pb-4">
        {NAV.map((group) => (
          <div key={group.section}>
            <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/50">{t(group.section)}</div>
            {group.items.map((item) => {
              const Icon = item.icon;
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
                    active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60",
                  )}
                >
                  <Icon className="size-4" />
                  {t(item.label)}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="border-t border-sidebar-border px-4 py-3 text-[10px] text-sidebar-foreground/50">{t("app.tagline")}</div>
    </aside>
  );
}

function VedaBanner() {
  const { me } = useSession();
  const r = me?.restriction as
    | { name: string; ends_at: string | null; blocked_formats: string[]; blocked_creatives: string[]; mandatory_legends: string[] }
    | null
    | undefined;
  if (!r) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 bg-veda px-4 py-2 text-xs text-veda-foreground" role="status">
      <span className="font-semibold">{t("topbar.vedaActive", { name: r.name })}</span>
      <span>
        {t("topbar.vedaDetail", {
          formats: r.blocked_formats.map((f) => tEnum("format", f)).join(", ") || t("topbar.none"),
          creatives: r.blocked_creatives.map((c) => tEnum("creative", c)).join(", ") || t("topbar.none"),
          until: fmtDate(r.ends_at),
        })}
      </span>
      {r.mandatory_legends.length ? <span>{t("topbar.vedaLegends", { legends: r.mandatory_legends.join(" · ") })}</span> : null}
    </div>
  );
}

function Topbar() {
  const { me, selectClient, viewAs, logout } = useSession();
  if (!me) return null;
  const currentViewAs = `${me.user.role}${me.user.kb_owner ? ":kb" : ""}`;
  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
      <VedaBanner />
      <div className="flex flex-wrap items-center gap-3 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{t("topbar.client")}</span>
          <Select value={String(me.client.id)} onValueChange={(v) => selectClient(Number(v))}>
            <SelectTrigger size="sm" className="min-w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {me.clients.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.name} · {t(`enums.client_type.${c.client_type}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {me.demo_mode ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{t("topbar.viewAs")}</span>
                <Select
                  value={currentViewAs}
                  onValueChange={(v) => {
                    const [role, kb] = v.split(":");
                    void viewAs(role, kb === "kb");
                  }}
                >
                  <SelectTrigger size="sm" className="min-w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {VIEW_AS.map((v) => (
                      <SelectItem key={v.label} value={`${v.role}${v.kb ? ":kb" : ""}`}>
                        {t(v.label)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </TooltipTrigger>
            <TooltipContent>{t("topbar.viewAsHint")}</TooltipContent>
          </Tooltip>
        ) : null}
        <div className="ml-auto flex items-center gap-3">
          <Badge variant="outline" className="gap-1">
            <Sparkles className="size-3" />
            {me.llm_provider === "mock" ? t("topbar.mockMode") : t("topbar.liveMode", { provider: me.llm_provider })}
          </Badge>
          <div className="text-right text-xs leading-tight">
            <div className="font-medium">{me.user.name}</div>
            <div className="text-muted-foreground">
              {t(`roles.${me.user.role}`)}
              {me.user.kb_owner ? ` · ${t("roles.kb_owner")}` : ""}
            </div>
          </div>
          <Button size="icon-sm" variant="ghost" onClick={logout} aria-label={t("auth.logout")}>
            <LogOut />
          </Button>
        </div>
      </div>
      {me.reminders.length ? (
        <div className="flex items-center gap-2 border-t bg-status-warn/10 px-4 py-1.5 text-xs">
          <Activity className="size-3.5 text-status-warn" />
          {me.reminders.map((r, i) => (
            <span key={i}>{String((r as { message?: string }).message ?? "")}</span>
          ))}
        </div>
      ) : null}
    </header>
  );
}

function ShellBody({ children }: { children: React.ReactNode }) {
  const { me, loading, error, reload } = useSession();
  // A 401 is already redirecting to /login; any other failure must not look like an endless load.
  if (!me && error && error.status !== 401) {
    return (
      <div className="p-8">
        <ErrorState error={error} onRetry={() => void reload()} />
      </div>
    );
  }
  if (loading || !me) return <Loading className="p-8" />;
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main key={me.client.id} className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 md:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <ShellBody>{children}</ShellBody>
    </SessionProvider>
  );
}
