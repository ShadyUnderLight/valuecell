export interface PersistVersionDomain {
  domain: string;
  storageKey: string;
  schemaVersion: number;
}

export const PERSIST_VERSION_DOMAINS = {
  settings: {
    domain: "frontend.persist.settings",
    storageKey: "valuecell-settings",
    schemaVersion: 1,
  },
  system: {
    domain: "frontend.persist.system",
    storageKey: "valuecell-system-store",
    schemaVersion: 1,
  },
} as const satisfies Record<string, PersistVersionDomain>;

export const SETTINGS_PERSIST_VERSION_DOMAIN = PERSIST_VERSION_DOMAINS.settings;
export const SYSTEM_PERSIST_VERSION_DOMAIN = PERSIST_VERSION_DOMAINS.system;
