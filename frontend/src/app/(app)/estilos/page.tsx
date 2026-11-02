"use client";

import { PageHeader } from "@/components/app/common";
import { CatalogTab, TopicsTab } from "@/components/settings/catalog-tabs";
import { MatrixTab, TagsTab } from "@/components/styles/matrix-tab";
import { StylesTab } from "@/components/styles/styles-tab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { t } from "@/i18n";

// MVP: every catalog of the client in one place. Directives and hard rules keep working but leave the menu.
export default function CatalogsPage() {
  return (
    <div>
      <PageHeader title={t("mvp.catalogsTitle")} subtitle={t("mvp.catalogsSubtitle")} />
      <Tabs defaultValue="topics">
        <TabsList className="h-auto flex-wrap">
          <TabsTrigger value="topics">{t("settings.tabs.topics")}</TabsTrigger>
          <TabsTrigger value="styles">{t("styles.tabs.styles")}</TabsTrigger>
          <TabsTrigger value="catalog">{t("mvp.formatsCreatives")}</TabsTrigger>
          <TabsTrigger value="matrix">{t("styles.tabs.matrix")}</TabsTrigger>
          <TabsTrigger value="tags">{t("styles.tabs.tags")}</TabsTrigger>
        </TabsList>
        <TabsContent value="topics" className="mt-3"><TopicsTab /></TabsContent>
        <TabsContent value="styles" className="mt-3"><StylesTab /></TabsContent>
        <TabsContent value="catalog" className="mt-3"><CatalogTab /></TabsContent>
        <TabsContent value="matrix" className="mt-3"><MatrixTab /></TabsContent>
        <TabsContent value="tags" className="mt-3"><TagsTab /></TabsContent>
      </Tabs>
    </div>
  );
}
