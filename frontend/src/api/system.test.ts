import { describe, expect, test } from "bun:test";
import { normalizeConfigHealth } from "./system";

describe("normalizeConfigHealth", () => {
  test("keeps valid config health payload stable", () => {
    expect(
      normalizeConfigHealth({
        status: "warning",
        primary_provider: "openai",
        enabled_providers: ["openai", "google"],
        issues: [
          {
            level: "error",
            scope: "provider:openai",
            message: "Missing OPENAI_API_KEY",
          },
        ],
      }),
    ).toEqual({
      status: "warning",
      primary_provider: "openai",
      enabled_providers: ["openai", "google"],
      issues: [
        {
          level: "error",
          scope: "provider:openai",
          message: "Missing OPENAI_API_KEY",
        },
      ],
    });
  });

  test("sanitizes malformed payloads to safe defaults", () => {
    expect(
      normalizeConfigHealth({
        status: "broken",
        primary_provider: 123,
        enabled_providers: ["openai", null, 1],
        issues: [
          {
            level: "unexpected",
            scope: 42,
            message: null,
          },
          null,
        ],
      }),
    ).toEqual({
      status: "healthy",
      primary_provider: "",
      enabled_providers: ["openai"],
      issues: [
        {
          level: "warning",
          scope: "unknown",
          message: "",
        },
      ],
    });
  });
});
