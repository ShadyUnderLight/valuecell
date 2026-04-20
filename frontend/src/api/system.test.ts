import { describe, expect, test } from "bun:test";
import { getVisibleConfigHealthIssues, normalizeConfigHealth } from "./system";

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

  test("drops issue entries that are missing required shape", () => {
    expect(
      normalizeConfigHealth({
        status: "error",
        primary_provider: "openai",
        enabled_providers: ["openai"],
        issues: [
          {
            scope: "provider:openai",
            message: "Missing OPENAI_API_KEY",
          },
          "bad-entry",
        ],
      }),
    ).toEqual({
      status: "error",
      primary_provider: "openai",
      enabled_providers: ["openai"],
      issues: [],
    });
  });
});

describe("getVisibleConfigHealthIssues", () => {
  test("returns no issues for healthy config health", () => {
    expect(
      getVisibleConfigHealthIssues({
        status: "healthy",
        primary_provider: "openai",
        enabled_providers: ["openai"],
        issues: [
          {
            level: "warning",
            scope: "provider:openai",
            message: "Missing OPENAI_API_KEY",
          },
        ],
      }),
    ).toEqual([]);
  });

  test("keeps only actionable warning or error messages", () => {
    expect(
      getVisibleConfigHealthIssues({
        status: "warning",
        primary_provider: "openai",
        enabled_providers: [],
        issues: [
          {
            level: "warning",
            scope: "providers",
            message:
              "No enabled providers with valid credentials were detected.",
          },
          {
            level: "error",
            scope: "provider:openai",
            message: "",
          },
        ],
      }),
    ).toEqual([
      {
        level: "warning",
        scope: "providers",
        message: "No enabled providers with valid credentials were detected.",
      },
    ]);
  });
});
