"use client";

import useSWR, { type SWRConfiguration, mutate as globalMutate } from "swr";

import type { components } from "./schema";

export type Schemas = components["schemas"];

/** Browser → Next route handler (/api/*) → FastAPI. Same origin, so session cookies just work. */
export const API_BASE = "/api";

export class ApiError extends Error {
  status: number;
  code: string;
  ruleId?: string;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, ruleId?: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.ruleId = ruleId;
    this.details = details;
  }
}

type Body = unknown;

async function parseError(res: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    /* non JSON */
  }
  const err = (payload as { error?: { code?: string; message?: string; rule_id?: string; details?: Record<string, unknown> } })?.error;
  if (err) return new ApiError(res.status, err.code ?? "error", err.message ?? res.statusText, err.rule_id, err.details ?? {});
  const detail = (payload as { detail?: unknown })?.detail;
  const message = Array.isArray(detail)
    ? detail.map((d: { msg?: string; loc?: unknown[] }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`).join("; ")
    : typeof detail === "string"
      ? detail
      : res.statusText;
  return new ApiError(res.status, "http_error", message);
}

export async function apiFetch<T = unknown>(path: string, init: { method?: string; body?: Body; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (init.form) {
    body = init.form;
  } else if (init.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.body);
  }
  const res = await fetch(`${API_BASE}${path}`, { method: init.method ?? (body ? "POST" : "GET"), headers, body, credentials: "same-origin" });
  if (res.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- outside React; full reload clears cached data
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: Body) => apiFetch<T>(path, { method: "POST", body: body ?? {} }),
  patch: <T>(path: string, body: Body) => apiFetch<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body: Body) => apiFetch<T>(path, { method: "PUT", body }),
  del: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => apiFetch<T>(path, { method: "POST", form }),
};

export function useApi<T>(path: string | null, config?: SWRConfiguration<T, ApiError>) {
  return useSWR<T, ApiError>(path, (p: string) => apiFetch<T>(p), { revalidateOnFocus: false, ...config });
}

/** Revalidate every cached GET whose path starts with one of the prefixes. */
export function refresh(...prefixes: string[]) {
  return globalMutate((key) => typeof key === "string" && prefixes.some((p) => key.startsWith(p)));
}

export function fileUrl(key: string | null | undefined): string | undefined {
  return key ? `${API_BASE}/files/${key}` : undefined;
}

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}
