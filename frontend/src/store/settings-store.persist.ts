import type { PersistOptions } from "zustand/middleware";
import {
  migrateSettingsPersistedState,
  SETTINGS_STORE_VERSION,
} from "./settings-store.migrate";
import type { LanguageCode, StockColorMode } from "./settings-store.types";

export interface SettingsStorePersistedState {
  stockColorMode: StockColorMode;
  language: LanguageCode;
}

export const SETTINGS_STORE_NAME = "valuecell-settings";

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
