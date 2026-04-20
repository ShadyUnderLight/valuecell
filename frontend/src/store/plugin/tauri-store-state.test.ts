import { beforeEach, describe, expect, mock, test } from "bun:test";

let isTauriValue = false;
let loadCalls: string[] = [];
let saveCalls = 0;
let setCalls: Array<{ key: string; value: string }> = [];
let deleteCalls: string[] = [];
let storeValues = new Map<string, string>();

mock.module("@tauri-apps/api/core", () => ({
  isTauri: () => isTauriValue,
}));

mock.module("@tauri-apps/plugin-store", () => ({
  load: async (storeName: string) => {
    loadCalls.push(storeName);
    return {
      get: async (key: string) => storeValues.get(key) ?? null,
      set: async (key: string, value: string) => {
        setCalls.push({ key, value });
        storeValues.set(key, value);
      },
      delete: async (key: string) => {
        deleteCalls.push(key);
        storeValues.delete(key);
      },
      save: async () => {
        saveCalls += 1;
      },
    };
  },
}));

const { TauriStoreState } = await import("./tauri-store-state");

describe("TauriStoreState", () => {
  beforeEach(() => {
    isTauriValue = false;
    loadCalls = [];
    saveCalls = 0;
    setCalls = [];
    deleteCalls = [];
    storeValues = new Map<string, string>();
    Object.defineProperty(globalThis, "window", {
      value: {},
      writable: true,
      configurable: true,
    });
  });

  test("falls back to inert storage outside Tauri", async () => {
    const storage = new TauriStoreState("valuecell-settings.json");

    await storage.init();
    await storage.setItem("foo", "bar");
    await storage.removeItem("foo");

    expect(loadCalls).toEqual([]);
    await expect(storage.getItem("foo")).resolves.toBeNull();
  });

  test("loads the Tauri store and debounces save operations", async () => {
    isTauriValue = true;
    const storage = new TauriStoreState("valuecell-settings.json");

    await storage.init();
    await storage.setItem("theme", '{"dark":true}');
    await storage.setItem("language", '"zh_CN"');
    await storage.removeItem("theme");

    expect(loadCalls).toEqual(["valuecell-settings.json"]);
    expect(setCalls).toEqual([
      { key: "theme", value: '{"dark":true}' },
      { key: "language", value: '"zh_CN"' },
    ]);
    expect(deleteCalls).toEqual(["theme"]);

    await new Promise((resolve) => setTimeout(resolve, 1100));

    expect(saveCalls).toBe(1);
    await expect(storage.getItem("language")).resolves.toBe('"zh_CN"');
    await expect(storage.getItem("theme")).resolves.toBeNull();
  });
});
