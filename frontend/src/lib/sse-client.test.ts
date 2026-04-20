import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import SSEClient, { SSEReadyState } from "./sse-client";

describe("SSEClient", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    mock.restore();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("aggregates fragmented SSE chunks and emits parsed payloads in order", async () => {
    const encoder = new TextEncoder();
    const states: SSEReadyState[] = [];
    const payloads: unknown[] = [];

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"type":"chunk","content":"hel'),
        );
        controller.enqueue(encoder.encode('lo"}\n\n'));
        controller.enqueue(
          encoder.encode('data: {"type":"done","content":"ok"}\n\n'),
        );
        controller.close();
      },
    });

    globalThis.fetch = mock(async () => {
      return new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    }) as typeof fetch;

    await new Promise<void>((resolve, reject) => {
      const client = new SSEClient(
        { url: "http://localhost/stream", timeout: 1000 },
        {
          onData: (data) => payloads.push(data),
          onError: reject,
          onStateChange: (state) => states.push(state),
          onClose: () => resolve(),
        },
      );

      void client.connect(JSON.stringify({ message: "ping" }));
    });

    expect(states).toEqual([
      SSEReadyState.CONNECTING,
      SSEReadyState.OPEN,
      SSEReadyState.CLOSED,
    ]);
    expect(payloads).toEqual([
      { type: "chunk", content: "hello" },
      { type: "done", content: "ok" },
    ]);
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost/stream",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "ping" }),
      }),
    );
  });

  test("reports handshake timeout as an error and closes the stream", async () => {
    globalThis.fetch = mock(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        }),
    ) as typeof fetch;

    const states: SSEReadyState[] = [];

    const error = await new Promise<Error>((resolve) => {
      const client = new SSEClient(
        { url: "http://localhost/timeout", timeout: 10 },
        {
          onStateChange: (state) => states.push(state),
          onError: resolve,
        },
      );

      void client.connect();
    });

    expect(error.message).toBe("Handshake timeout");
    expect(states).toEqual([SSEReadyState.CONNECTING, SSEReadyState.CLOSED]);
  });
});
