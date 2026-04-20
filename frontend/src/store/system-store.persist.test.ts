import { describe, expect, test } from "bun:test";
import {
  INITIAL_SYSTEM_INFO,
  migrateSystemPersistedState,
  SYSTEM_STORE_NAME,
  SYSTEM_STORE_VERSION,
  systemStorePersistOptions,
} from "./system-store.persist";

describe("systemStorePersistOptions", () => {
  test("wires schema versioned migration metadata", () => {
    expect(systemStorePersistOptions.name).toBe(SYSTEM_STORE_NAME);
    expect(systemStorePersistOptions.version).toBe(SYSTEM_STORE_VERSION);
    expect(typeof systemStorePersistOptions.migrate).toBe("function");
  });

  test("sanitizes legacy persisted snapshots through persist migrate", async () => {
    const migrated = await systemStorePersistOptions.migrate?.(
      {
        access_token: "token",
        refresh_token: 123,
        id: "user-1",
        email: null,
        name: "Asata",
      },
      0,
    );

    expect(migrated).toEqual({
      ...INITIAL_SYSTEM_INFO,
      access_token: "token",
      id: "user-1",
      name: "Asata",
    });
  });

  test("sanitizes malformed current-version snapshots through persist migrate", async () => {
    const migrated = await systemStorePersistOptions.migrate?.(
      {
        access_token: ["token"],
        refresh_token: "refresh",
        id: "user-1",
        email: 123,
        name: "Asata",
        avatar: { url: "https://example.com/avatar.png" },
        created_at: null,
        updated_at: "2026-04-20T08:05:00Z",
      },
      1,
    );

    expect(migrated).toEqual({
      ...INITIAL_SYSTEM_INFO,
      refresh_token: "refresh",
      id: "user-1",
      name: "Asata",
      updated_at: "2026-04-20T08:05:00Z",
    });
  });
});

describe("migrateSystemPersistedState", () => {
  test("fills missing fields with safe defaults", () => {
    expect(migrateSystemPersistedState(undefined)).toEqual(INITIAL_SYSTEM_INFO);
  });

  test("keeps valid current snapshot values stable", () => {
    const current = {
      ...INITIAL_SYSTEM_INFO,
      access_token: "access",
      refresh_token: "refresh",
      id: "42",
      email: "user@example.com",
      name: "ValueCell",
      avatar: "https://example.com/avatar.png",
      created_at: "2026-04-20T08:00:00Z",
      updated_at: "2026-04-20T08:05:00Z",
    };

    expect(migrateSystemPersistedState(current)).toEqual(current);
  });
});
