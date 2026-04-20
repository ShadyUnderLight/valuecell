import type { PersistOptions } from "zustand/middleware";
import type { SystemInfo } from "@/types/system";

export const SYSTEM_STORE_NAME = "valuecell-system-store";
export const SYSTEM_STORE_VERSION = 1;

export type SystemStorePersistedState = SystemInfo;

export const INITIAL_SYSTEM_INFO: SystemStorePersistedState = {
  access_token: "",
  refresh_token: "",
  id: "",
  email: "",
  name: "",
  avatar: "",
  created_at: "",
  updated_at: "",
};

const normalizeStringField = (value: unknown): string =>
  typeof value === "string" ? value : "";

export const migrateSystemPersistedState = (
  persistedState: Partial<SystemStorePersistedState> | undefined,
): SystemStorePersistedState => ({
  access_token: normalizeStringField(persistedState?.access_token),
  refresh_token: normalizeStringField(persistedState?.refresh_token),
  id: normalizeStringField(persistedState?.id),
  email: normalizeStringField(persistedState?.email),
  name: normalizeStringField(persistedState?.name),
  avatar: normalizeStringField(persistedState?.avatar),
  created_at: normalizeStringField(persistedState?.created_at),
  updated_at: normalizeStringField(persistedState?.updated_at),
});

export const systemStorePersistOptions: Pick<
  PersistOptions<SystemStorePersistedState>,
  "name" | "version" | "migrate"
> = {
  name: SYSTEM_STORE_NAME,
  version: SYSTEM_STORE_VERSION,
  migrate: (persistedState) =>
    migrateSystemPersistedState(
      persistedState as Partial<SystemStorePersistedState> | undefined,
    ),
};
