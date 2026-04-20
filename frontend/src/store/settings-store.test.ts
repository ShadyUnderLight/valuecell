import { describe, expect, test } from "bun:test";
import {
  DEFAULT_LANGUAGE,
  migrateSettingsPersistedState,
} from "./settings-store.migrate";
import type { StockColorMode } from "./settings-store.types";

describe("migrateSettingsPersistedState", () => {
  test("normalizes legacy language codes and preserves valid color mode", () => {
    const migrated = migrateSettingsPersistedState(
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

  test("fills missing fields with defaults for older persisted snapshots", () => {
    const migrated = migrateSettingsPersistedState(
      {
        language: "ja-JP",
      },
      0,
    );

    expect(migrated).toEqual({
      stockColorMode: "GREEN_UP_RED_DOWN",
      language: "ja",
    });
  });

  test("falls back unknown legacy values to defaults", () => {
    const migrated = migrateSettingsPersistedState(
      {
        stockColorMode: "BLUE_UP_PURPLE_DOWN",
        language: "fr",
      },
      0,
    );

    expect(migrated).toEqual({
      stockColorMode: "GREEN_UP_RED_DOWN",
      language: DEFAULT_LANGUAGE,
    });
  });

  test("keeps current persisted values stable on newer versions", () => {
    const current = {
      stockColorMode: "GREEN_UP_RED_DOWN" as StockColorMode,
      language: "zh_TW",
    };

    expect(migrateSettingsPersistedState(current, 1)).toEqual(current);
  });
});
