"use client";

import { createContext, useCallback, useContext, useMemo } from "react";

import { api, refresh, useApi, type ApiError, type Schemas } from "@/lib/api/client";

type Me = Schemas["MeOut"];

type SessionValue = {
  me: Me | undefined;
  loading: boolean;
  error: ApiError | undefined;
  can: (permission: string) => boolean;
  selectClient: (clientId: number) => Promise<void>;
  viewAs: (role: string, kbOwner?: boolean) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<unknown>;
};

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const { data, error, isLoading, mutate } = useApi<Me>("/auth/me");

  const can = useCallback((permission: string) => Boolean(data?.permissions.includes(permission)), [data]);

  const selectClient = useCallback(
    async (clientId: number) => {
      await api.post("/auth/select-client", { client_id: clientId });
      await mutate();
      await refresh("/");
    },
    [mutate],
  );

  const viewAs = useCallback(
    async (role: string, kbOwner = false) => {
      await api.post("/auth/view-as", { role, kb_owner: kbOwner });
      await mutate();
      await refresh("/");
    },
    [mutate],
  );

  const logout = useCallback(async () => {
    await api.post("/auth/logout");
    // Full reload on purpose: drops every cached SWR response of the previous session.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/login";
  }, []);

  const value = useMemo(
    () => ({ me: data, loading: isLoading, error, can, selectClient, viewAs, logout, reload: mutate }),
    [data, isLoading, error, can, selectClient, viewAs, logout, mutate],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
