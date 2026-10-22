import type { Metadata } from "next";

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { LOCALE, t } from "@/i18n";

import "./globals.css";

export const metadata: Metadata = {
  title: t("app.name"),
  description: t("app.fullName"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang={LOCALE} className="h-full antialiased">
      <body className="min-h-full bg-background font-sans text-foreground">
        <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
        <Toaster richColors position="bottom-right" />
      </body>
    </html>
  );
}
