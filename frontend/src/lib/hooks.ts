"use client";

import { useMemo } from "react";

import { useApi, type Schemas } from "@/lib/api/client";

export function useTopics() {
  const { data } = useApi<Schemas["TopicOut"][]>("/topics");
  return useMemo(() => {
    const list = data ?? [];
    const byId = new Map(list.map((t) => [t.id, t]));
    const bySlug = new Map(list.map((t) => [t.slug, t]));
    return { list, byId, bySlug, options: list.map((t) => ({ value: String(t.id), label: t.name })) };
  }, [data]);
}

export function useLevels() {
  const { data } = useApi<Schemas["GovLevelOut"][]>("/kb/gov-levels");
  return useMemo(() => {
    const list = data ?? [];
    const byId = new Map(list.map((l) => [l.id, l]));
    return { list, byId, options: list.map((l) => ({ value: String(l.id), label: l.name })) };
  }, [data]);
}

export function useDocuments() {
  const { data } = useApi<Schemas["DocumentOut"][]>("/kb/documents");
  return useMemo(() => {
    const list = data ?? [];
    return { list, options: list.map((d) => ({ value: String(d.id), label: d.title })) };
  }, [data]);
}
