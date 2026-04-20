import { create } from "zustand";
import { createJSONStorage, devtools, persist } from "zustand/middleware";
import { useShallow } from "zustand/shallow";
import type { SystemInfo } from "@/types/system";
import { TauriStoreState } from "./plugin/tauri-store-state";
import {
  INITIAL_SYSTEM_INFO,
  SYSTEM_STORE_NAME,
  systemStorePersistOptions,
} from "./system-store.persist";

interface SystemStoreState extends SystemInfo {
  setSystemInfo: (info: Partial<SystemInfo>) => void;
  clearSystemInfo: () => void;
}

const store = new TauriStoreState(SYSTEM_STORE_NAME);
await store.init();

export const useSystemStore = create<SystemStoreState>()(
  devtools(
    persist(
      (set) => ({
        ...INITIAL_SYSTEM_INFO,
        setSystemInfo: (info) => set((state) => ({ ...state, ...info })),
        clearSystemInfo: () => set(INITIAL_SYSTEM_INFO),
      }),
      {
        ...systemStorePersistOptions,
        storage: createJSONStorage(() => store),
      },
    ),
    { name: "SystemStore", enabled: import.meta.env.DEV },
  ),
);

export const useSystemInfo = () =>
  useSystemStore(
    useShallow((state) => ({
      id: state.id,
      email: state.email,
      name: state.name,
      avatar: state.avatar,
      created_at: state.created_at,
      updated_at: state.updated_at,
    })),
  );

export const useSystemAccessToken = () =>
  useSystemStore((state) => state.access_token);

export const useIsLoggedIn = () =>
  useSystemStore(useShallow((state) => !!state.id && !!state.access_token));
