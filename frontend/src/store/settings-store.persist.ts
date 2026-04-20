import type { PersistOptions } from "zustand/middleware";
import { SETTINGS_PERSIST_VERSION_DOMAIN } from "./persist-version-domains";
import {
  migrateSettingsPersistedState,
  SETTINGS_STORE_VERSION,
} from "./settings-store.migrate";
import type { LanguageCode, StockColorMode } from "./settings-store.types";

export interface SettingsStorePersistedState {
  stockColorMode: StockColorMode;
  language: LanguageCode;
}

export const SETTINGS_STORE_NAME = SETTINGS_PERSIST_VERSION_DOMAIN.storageKey;

export const settingsStorePersistOptions: Pick<
  PersistOptions<SettingsStorePersistedState>,
  "name" | "version" | "migrate"
> = {
  name: SETTINGS_STORE_NAME,
  version: SETTINGS_STORE_VERSION,
  migrate: (persistedState, version) =>
    migrateSettingsPersistedState(
      persistedState as Partial<SettingsStorePersistedState>,
      version,
    ),
};
