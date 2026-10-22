"use client";

import { Search } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/app/common";
import { FactsTab } from "@/components/kb/facts-tab";
import { ActorsTab, BriefsTab, CompetencesTab, DocumentsTab, HistoryTab, ImagesTab, MessagesTab } from "@/components/kb/other-tabs";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fmtNum, t } from "@/i18n";
import { useApi, type Schemas } from "@/lib/api/client";

function SemanticSearch() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const { data } = useApi<Schemas["SearchHit"][]>(query.length >= 2 ? `/kb/search?q=${encodeURIComponent(query)}` : null);
  return (
    <div className="mb-4 grid gap-2">
      <form
        className="relative"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(q.trim());
        }}
      >
        <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
        <Input className="pl-8" placeholder={t("kb.searchPlaceholder")} value={q} onChange={(e) => setQ(e.target.value)} />
      </form>
      {query && data ? (
        <Card className="py-3">
          <CardContent className="grid gap-2 px-3">
            <p className="text-xs font-medium text-muted-foreground">{t("kb.searchResults")}</p>
            {data.map((h) => (
              <div key={`${h.kind}-${h.id}`} className="rounded border p-2 text-sm">
                <div className="mb-1 flex items-center gap-2 text-xs">
                  <Badge variant="secondary">{t(`kb.kind.${h.kind}`)}</Badge>
                  <span className="font-medium">{h.title}</span>
                  <span className="ml-auto text-muted-foreground">{t("kb.score", { score: fmtNum(h.score, 2) })}</span>
                </div>
                <p className="text-xs text-muted-foreground">{h.snippet}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

export default function KnowledgeBasePage() {
  return (
    <div>
      <PageHeader title={t("kb.title")} subtitle={t("kb.subtitle")} />
      <SemanticSearch />
      <Tabs defaultValue="facts">
        <TabsList className="flex-wrap">
          <TabsTrigger value="facts">{t("kb.tabs.facts")}</TabsTrigger>
          <TabsTrigger value="documents">{t("kb.tabs.documents")}</TabsTrigger>
          <TabsTrigger value="briefs">{t("kb.tabs.briefs")}</TabsTrigger>
          <TabsTrigger value="messages">{t("kb.tabs.messages")}</TabsTrigger>
          <TabsTrigger value="actors">{t("kb.tabs.actors")}</TabsTrigger>
          <TabsTrigger value="competences">{t("kb.tabs.competences")}</TabsTrigger>
          <TabsTrigger value="images">{t("kb.tabs.images")}</TabsTrigger>
          <TabsTrigger value="history">{t("kb.tabs.history")}</TabsTrigger>
        </TabsList>
        <TabsContent value="facts" className="mt-3"><FactsTab /></TabsContent>
        <TabsContent value="documents" className="mt-3"><DocumentsTab /></TabsContent>
        <TabsContent value="briefs" className="mt-3"><BriefsTab /></TabsContent>
        <TabsContent value="messages" className="mt-3"><MessagesTab /></TabsContent>
        <TabsContent value="actors" className="mt-3"><ActorsTab /></TabsContent>
        <TabsContent value="competences" className="mt-3"><CompetencesTab /></TabsContent>
        <TabsContent value="images" className="mt-3"><ImagesTab /></TabsContent>
        <TabsContent value="history" className="mt-3"><HistoryTab /></TabsContent>
      </Tabs>
    </div>
  );
}
