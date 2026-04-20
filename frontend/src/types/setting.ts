export type MemoryItem = {
  id: number;
  content: string;
};

export type ModelProvider = {
  provider: string;
};

export type ProviderModelInfo = {
  model_id: string;
  model_name: string;
};

export type ProviderDetail = {
  api_key: string;
  api_key_url: string;
  base_url: string;
  is_default: boolean;
  // Provider-native default model id used by current settings mutations/UI.
  default_model_id: string;
  // Canonical shared-contract field for cross-provider model selection.
  default_model_ref?: string;
  // Canonical recommended refs from backend provider config.
  recommended_model_refs: string[];
  models: ProviderModelInfo[];
};

export type CatalogModelItem = {
  canonical_ref: string;
  provider: string;
  native_model_id: string;
  display_name: string;
  status?: string;
  visibility?: string;
};

// --- Model availability check ---
export type CheckModelRequest = {
  provider?: string;
  model_id?: string;
  api_key?: string;
};

export type CheckModelResult = {
  ok: boolean;
  provider: string;
  model_id: string;
  status?: string;
  error?: string;
};
