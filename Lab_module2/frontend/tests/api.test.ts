import { beforeEach, describe, expect, test, vi } from "vitest";
import { ApiError, analyze, getSample, listSamples } from "@/lib/api";
import { RESULT, SAMPLE_DETAIL, SAMPLES } from "./fixtures";

function mockFetch(impl: () => Promise<Response>) {
  const fetchMock = vi.fn<typeof fetch>(impl);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function respond(status: number, body: unknown, headers: Record<string, string> = {}) {
  return () =>
    Promise.resolve(
      new Response(typeof body === "string" ? body : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/problem+json", ...headers },
      }),
    );
}

const problem = (status: number, extra: object = {}) => ({
  type: `http://api.test/problems/x`,
  title: "Title",
  status,
  ...extra,
});

async function caught(promise: Promise<unknown>): Promise<ApiError> {
  const err = await promise.catch((e: unknown) => e);
  expect(err).toBeInstanceOf(ApiError);
  return err as ApiError;
}

const BODY = { code: "x = 1", language: "python" as const, analysis_type: "security" as const };

describe("api client", () => {
  beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test/"));

  test("analyze sends a JSON POST and returns the parsed result", async () => {
    const fetchMock = mockFetch(respond(200, RESULT));
    await expect(analyze(BODY)).resolves.toEqual(RESULT);
    const [url, init = {}] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/analyze");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(BODY);
  });

  test("samples endpoints", async () => {
    const fetchMock = mockFetch(respond(200, SAMPLES));
    await expect(listSamples()).resolves.toEqual(SAMPLES);
    fetchMock.mockImplementation(respond(200, SAMPLE_DETAIL));
    await expect(getSample("xss", "security")).resolves.toEqual(SAMPLE_DETAIL);
    expect(fetchMock.mock.calls[1][0]).toBe("http://api.test/samples/xss?analysis_type=security");
  });

  test("a response that breaks the schema is rejected, not rendered", async () => {
    mockFetch(respond(200, { ...RESULT, issues: [{ severity: "urgent" }] }));
    expect((await caught(analyze(BODY))).kind).toBe("invalid_response");
  });

  test("422 exposes field errors with readable labels", async () => {
    mockFetch(
      respond(422, problem(422, {
        detail: "The request body has 1 invalid field.",
        errors: [{ detail: "Code must not be blank.", pointer: "#/code" }],
      })),
    );
    const err = await caught(analyze(BODY));
    expect(err.kind).toBe("validation");
    expect(err.fieldErrors).toEqual(["Code: Code must not be blank."]);
  });

  test.each([
    [413, "too_large", { detail: "The code has 70000 characters; the maximum is 60000." }, undefined],
    [429, "rate_limited", {}, 17],
    [503, "unavailable", { detail: "The free-tier analysis quota is used up." }, 3600],
    [502, "llm_failed", { detail: "The model's answer was not valid." }, undefined],
    [504, "llm_failed", {}, undefined],
    [500, "server", {}, undefined],
  ])("%i → %s", async (status, kind, extra, retry) => {
    const headers: Record<string, string> = retry ? { "Retry-After": String(retry) } : {};
    mockFetch(respond(status, problem(status, extra), headers));
    const err = await caught(analyze(BODY));
    expect(err.kind).toBe(kind);
    expect(err.retryAfter).toBe(retry);
    if ("detail" in extra) expect(err.message).toBe(extra.detail);
  });

  test("non-JSON error page falls back to a generic message", async () => {
    mockFetch(respond(502, "<html>Bad gateway</html>"));
    const err = await caught(analyze(BODY));
    expect(err.kind).toBe("llm_failed");
    expect(err.message).toMatch(/could not be completed/);
  });

  test("network failure and timeout", async () => {
    mockFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    expect((await caught(analyze(BODY))).kind).toBe("network");
    mockFetch(() => Promise.reject(new DOMException("timed out", "TimeoutError")));
    expect((await caught(analyze(BODY))).kind).toBe("timeout");
  });
});
