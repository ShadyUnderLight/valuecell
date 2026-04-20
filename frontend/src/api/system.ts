import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { API_QUERY_KEYS, VALUECELL_BACKEND_URL } from "@/constants/api";
import i18n from "@/i18n";
import { type ApiResponse, apiClient } from "@/lib/api-client";
import { useLanguage } from "@/store/settings-store";
import { useSystemStore } from "@/store/system-store";
import type {
  ConfigHealth,
  StrategyDetail,
  StrategyRankItem,
  StrategyReport,
  SystemInfo,
} from "@/types/system";

export interface DefaultTicker {
  ticker: string;
  symbol: string;
  name: string;
}

export interface DefaultTickersResponse {
  region: string;
  tickers: DefaultTicker[];
}

export const normalizeConfigHealth = (value: unknown): ConfigHealth => {
  const data = (value ?? {}) as Partial<ConfigHealth>;
  const issues = Array.isArray(data.issues)
    ? data.issues
        .filter(
          (issue): issue is ConfigHealth["issues"][number] =>
            typeof issue === "object" &&
            issue !== null &&
            (issue as { level?: unknown }).level !== undefined,
        )
        .map((issue): ConfigHealth["issues"][number] => ({
          level: issue.level === "error" ? "error" : "warning",
          scope: typeof issue.scope === "string" ? issue.scope : "unknown",
          message: typeof issue.message === "string" ? issue.message : "",
        }))
    : [];

  return {
    status:
      data.status === "error" ||
      data.status === "warning" ||
      data.status === "healthy"
        ? data.status
        : "healthy",
    primary_provider:
      typeof data.primary_provider === "string" ? data.primary_provider : "",
    enabled_providers: Array.isArray(data.enabled_providers)
      ? data.enabled_providers.filter(
          (provider): provider is string => typeof provider === "string",
        )
      : [],
    issues,
  };
};

export const getVisibleConfigHealthIssues = (
  configHealth: ConfigHealth | null | undefined,
) => {
  if (!configHealth || configHealth.status === "healthy") {
    return [];
  }

  return configHealth.issues.filter((issue) => issue.message.trim().length > 0);
};

export const useConfigHealth = () => {
  return useQuery({
    queryKey: API_QUERY_KEYS.SYSTEM.configHealth,
    queryFn: () =>
      apiClient.get<ApiResponse<ConfigHealth>>(
        `${VALUECELL_BACKEND_URL}/system/config-health`,
      ),
    select: (data) => normalizeConfigHealth(data.data),
    retry: false,
    staleTime: 30_000,
  });
};

export const useBackendHealth = () => {
  return useQuery({
    queryKey: ["backend-health"],
    queryFn: () => apiClient.get<boolean>("/healthz"),
    retry: false,
    refetchInterval: (query) => {
      return query.state.status === "error" ? 2000 : 10000;
    },
    refetchOnWindowFocus: true,
  });
};

export const getUserInfo = async (token: string) => {
  const { data } = await apiClient.get<
    ApiResponse<Omit<SystemInfo, "access_token" | "refresh_token">>
  >(`${VALUECELL_BACKEND_URL}/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return data;
};

export const useSignOut = () => {
  return useMutation({
    mutationFn: () =>
      apiClient.post<ApiResponse<void>>(
        `${VALUECELL_BACKEND_URL}/auth/logout`,
        null,
        {
          requiresAuth: true,
        },
      ),

    onSuccess: () => {
      useSystemStore.getState().clearSystemInfo();
    },
    onError: (error) => {
      toast.error(JSON.stringify(error));
      useSystemStore.getState().clearSystemInfo();
    },
  });
};

export const useGetStrategyList = (
  params: { limit: number; days: number } = { limit: 10, days: 7 },
) => {
  const language = useLanguage();

  return useQuery({
    queryKey: API_QUERY_KEYS.SYSTEM.strategyList([
      ...Object.values(params),
      language,
    ]),
    queryFn: () =>
      apiClient.get<ApiResponse<StrategyRankItem[]>>(
        `${VALUECELL_BACKEND_URL}/strategy/list?limit=${params.limit}&days=${params.days}&language=${language}`,
      ),
    select: (data) => data.data,
  });
};

export const useGetStrategyDetail = (id: number | null) => {
  const language = useLanguage();

  return useQuery({
    queryKey: API_QUERY_KEYS.SYSTEM.strategyDetail([id ?? "", language]),
    queryFn: () =>
      apiClient.get<ApiResponse<StrategyDetail>>(
        `${VALUECELL_BACKEND_URL}/strategy/detail/${id}?language=${language}`,
      ),
    select: (data) => data.data,
    enabled: !!id,
  });
};

export const usePublishStrategy = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: StrategyReport) => {
      return apiClient.post<ApiResponse<void>>(
        `${VALUECELL_BACKEND_URL}/strategy/report`,
        data,
        {
          requiresAuth: true,
        },
      );
    },
    onSuccess: () => {
      toast.success(i18n.t("strategy.toast.published"));
      queryClient.invalidateQueries({
        queryKey: API_QUERY_KEYS.SYSTEM.strategyList([]),
      });
    },
    onError: (error) => {
      toast.error(JSON.stringify(error));
    },
  });
};

/**
 * Get region-aware default tickers for homepage display.
 * Returns A-share indices for China mainland users,
 * global indices for other regions.
 *
 * @param region - Optional region override for testing (e.g., "cn" or "default").
 *                 In development, you can set this to test different regions.
 */
export const useGetDefaultTickers = (region?: string) => {
  const language = useLanguage();

  return useQuery({
    queryKey: ["system", "default-tickers", region, language],
    queryFn: () => {
      const regionParam = region ? `region=${region}` : "";
      const langParam = `language=${language}`;
      const params = [regionParam, langParam].filter(Boolean).join("&");

      return apiClient.get<ApiResponse<DefaultTickersResponse>>(
        `system/default-tickers?${params}`,
      );
    },
    select: (data) => data.data,
    staleTime: 1000 * 60 * 60, // Cache for 1 hour, region doesn't change frequently
  });
};
