import { describe, expect, test } from "bun:test";
import { normalizeProviderDetail } from "./setting";

describe("normalizeProviderDetail", () => {
  test("keeps provider-native and canonical model selection fields distinct", () => {
    expect(
      normalizeProviderDetail({
        api_key: "sk-test",
        api_key_url: "https://platform.openai.com/api-keys",
        base_url: "https://api.openai.com/v1",
        is_default: true,
        default_model_id: "gpt-5",
        default_model_ref: "openai/gpt-5.4",
        recommended_model_refs: ["openai/gpt-5.4", null, 1, "openai/gpt-4.1"],
        models: [
          { model_id: "gpt-5", model_name: "GPT-5" },
          { model_id: "gpt-4.1", model_name: null },
        ],
      }),
    ).toEqual({
      api_key: "sk-test",
      api_key_url: "https://platform.openai.com/api-keys",
      base_url: "https://api.openai.com/v1",
      is_default: true,
      default_model_id: "gpt-5",
      default_model_ref: "openai/gpt-5.4",
      recommended_model_refs: ["openai/gpt-5.4", "openai/gpt-4.1"],
      models: [
        { model_id: "gpt-5", model_name: "GPT-5" },
        { model_id: "gpt-4.1", model_name: "" },
      ],
    });
  });

  test("falls back malformed payloads to safe shared-contract defaults", () => {
    expect(
      normalizeProviderDetail({
        api_key: null,
        api_key_url: 42,
        base_url: undefined,
        is_default: "yes",
        default_model_id: ["gpt-5"],
        default_model_ref: 123,
        recommended_model_refs: "openai/gpt-5.4",
        models: [null, { model_name: "Missing id" }],
      }),
    ).toEqual({
      api_key: "",
      api_key_url: "",
      base_url: "",
      is_default: false,
      default_model_id: "",
      default_model_ref: undefined,
      recommended_model_refs: [],
      models: [],
    });
  });
});
