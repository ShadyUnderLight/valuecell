import { describe, expect, test } from "bun:test";
import {
  SETTINGS_STORE_NAME,
  settingsStorePersistOptions,
} from "./settings-store.persist";

describe("settingsStorePersistOptions", () => {
  test("wires schema versioned migration metadata", () => {
    expect(settingsStorePersistOptions.name).toBe(SETTINGS_STORE_NAME);
    expect(settingsStorePersistOptions.version).toBe(1);
    expect(typeof settingsStorePersistOptions.migrate).toBe("function");
  });

  test("normalizes legacy snapshots through persist migrate", async () => {
    const migrated = await settingsStorePersistOptions.migrate?.(
      {
        stockColorMode: "RED_UP_GREEN_DOWN",
        language: "zh-Hans",
      },
      0,
    );

    expect(migrated).toEqual({
      stockColorMode: "RED_UP_GREEN_DOWN",
      language: "zh_CN",
    });
  });

  test("sanitizes malformed current-version snapshots through persist migrate", async () => {
    const migrated = await settingsStorePersistOptions.migrate?.(
      {
        stockColorMode: "BLUE_UP_PURPLE_DOWN",
        language: 42,
      },
      1,
    );

    expect(migrated).toEqual({
      stockColorMode: "GREEN_UP_RED_DOWN",
      language: "en",
    });
  });
});
