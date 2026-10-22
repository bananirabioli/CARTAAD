"use client";

import { useMemo, useState, type Dispatch, type SetStateAction } from "react";

import { useApi, type Schemas } from "@/lib/api/client";

/** State that resets to `init()` whenever `key` changes, adjusted during render instead of in an effect. */
export function useStateResetOn<T>(key: unknown, init: () => T): [T, Dispatch<SetStateAction<T>>] {
  const [prevKey, setPrevKey] = useState(key);
  const [state, setState] = useState(init);
  if (!Object.is(prevKey, key)) {
    setPrevKey(key);
    setState(init());
  }
  return [state, setState];
}

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
