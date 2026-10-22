"use client";

import { PageHeader } from "@/components/app/common";
import { DirectivesTab } from "@/components/styles/directives-tab";
import { HardRulesTab, MatrixTab, TagsTab } from "@/components/styles/matrix-tab";
import { StylesTab } from "@/components/styles/styles-tab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { t } from "@/i18n";

export default function StylesPage() {
  return (
    <div>
      <PageHeader title={t("styles.title")} subtitle={t("styles.subtitle")} />
      <Tabs defaultValue="styles">
        <TabsList>
          <TabsTrigger value="styles">{t("styles.tabs.styles")}</TabsTrigger>
          <TabsTrigger value="directives">{t("styles.tabs.directives")}</TabsTrigger>
          <TabsTrigger value="matrix">{t("styles.tabs.matrix")}</TabsTrigger>
          <TabsTrigger value="tags">{t("styles.tabs.tags")}</TabsTrigger>
          <TabsTrigger value="hard">{t("styles.tabs.hardRules")}</TabsTrigger>
        </TabsList>
        <TabsContent value="styles" className="mt-3"><StylesTab /></TabsContent>
        <TabsContent value="directives" className="mt-3"><DirectivesTab /></TabsContent>
        <TabsContent value="matrix" className="mt-3"><MatrixTab /></TabsContent>
        <TabsContent value="tags" className="mt-3"><TagsTab /></TabsContent>
        <TabsContent value="hard" className="mt-3"><HardRulesTab /></TabsContent>
      </Tabs>
    </div>
  );
}
