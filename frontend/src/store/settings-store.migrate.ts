import type { LanguageCode, StockColorMode } from "./settings-store.types";

export const DEFAULT_LANGUAGE = "en";
export const SETTINGS_STORE_VERSION = 1;
export const DEFAULT_STOCK_COLOR_MODE: StockColorMode = "GREEN_UP_RED_DOWN";

export const normalizeLanguageCode = (language: unknown): LanguageCode => {
  const map: Record<string, LanguageCode> = {
    en: "en",
    ja: "ja",
    "ja-JP": "ja",
    zh_CN: "zh_CN",
    "zh-CN": "zh_CN",
    "zh-Hans": "zh_CN",
    zh_TW: "zh_TW",
    "zh-TW": "zh_TW",
    "zh-Hant": "zh_TW",
  };

  return typeof language === "string"
    ? (map[language] ?? DEFAULT_LANGUAGE)
    : DEFAULT_LANGUAGE;
};

export const normalizeStockColorMode = (mode: unknown): StockColorMode => {
  return mode === "RED_UP_GREEN_DOWN"
    ? "RED_UP_GREEN_DOWN"
    : DEFAULT_STOCK_COLOR_MODE;
};

export const migrateSettingsPersistedState = (
  persistedState:
    | Partial<
        Pick<
          {
            stockColorMode: StockColorMode;
            language: LanguageCode;
          },
          "stockColorMode" | "language"
        >
      >
    | undefined,
  version: number,
): {
  stockColorMode: StockColorMode;
  language: LanguageCode;
} => {
  if (version >= SETTINGS_STORE_VERSION) {
    return {
      stockColorMode: normalizeStockColorMode(persistedState?.stockColorMode),
      language: normalizeLanguageCode(persistedState?.language),
    };
  }

  return {
    stockColorMode: normalizeStockColorMode(persistedState?.stockColorMode),
    language: normalizeLanguageCode(persistedState?.language),
  };
};
