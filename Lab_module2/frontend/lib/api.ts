import type { z } from "zod";
import {
  type AnalysisResult,
  AnalysisResultSchema,
  type AnalysisType,
  type Language,
  ProblemSchema,
  type Sample,
  type SampleDetail,
  SampleDetailSchema,
  SampleSchema,
} from "./schemas";

export type ApiErrorKind =
  | "validation"
  | "too_large"
  | "rate_limited"
  | "unavailable"
  | "llm_failed"
  | "server"
  | "network"
  | "timeout"
  | "invalid_response";

export class ApiError extends Error {
  constructor(
    public kind: ApiErrorKind,
    message: string,
    public retryAfter?: number,
    public fieldErrors: string[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const TIMEOUT_MS = 120_000; // a chunked analysis can take ~40 s with pacing

const FIELD_LABELS: Record<string, string> = {
  "#/code": "Code",
  "#/language": "Language",
  "#/analysis_type": "Analysis type",
};

function apiUrl(): string {
  // Referenced directly so Next.js inlines the value at build time.
  return (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
}

async function toApiError(res: Response): Promise<ApiError> {
  const retryHeader = Number(res.headers.get("Retry-After"));
  const retryAfter = Number.isFinite(retryHeader) && retryHeader > 0 ? retryHeader : undefined;
  let detail: string | undefined;
  let fieldErrors: string[] = [];
  try {
    const problem = ProblemSchema.safeParse(await res.json());
    if (problem.success) {
      detail = problem.data.detail;
      fieldErrors = (problem.data.errors ?? []).map(
        (e) => `${FIELD_LABELS[e.pointer] ?? e.pointer}: ${e.detail}`,
      );
    }
  } catch {
    // Not JSON (e.g. a proxy error page) — fall back to generic messages below.
  }

  switch (res.status) {
    case 400:
    case 422:
      return new ApiError("validation", detail ?? "The request is not valid.", undefined, fieldErrors);
    case 413:
      return new ApiError("too_large", detail ?? "The code is too large to analyze.");
    case 429:
      return new ApiError("rate_limited", "Too many analyses in a short time.", retryAfter);
    case 502:
    case 504:
      return new ApiError("llm_failed", detail ?? "The analysis could not be completed. Please try again.");
    case 503:
      return new ApiError("unavailable", detail ?? "The analyzer is busy or unavailable.", retryAfter);
    default:
      return new ApiError("server", "Something went wrong on the server. Please try again.");
  }
}

async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${apiUrl()}${path}`, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new ApiError("timeout", "The analysis took too long. Please try again.");
    }
    throw new ApiError("network", "Can't reach the analyzer. Check your connection and try again.");
  }
  if (!res.ok) throw await toApiError(res);

  const parsed = schema.safeParse(await res.json().catch(() => undefined));
  if (!parsed.success) {
    throw new ApiError("invalid_response", "Unexpected response from the server.");
  }
  return parsed.data;
}

export function analyze(body: {
  code: string;
  language: Language;
  analysis_type: AnalysisType;
}): Promise<AnalysisResult> {
  return request("/analyze", AnalysisResultSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function listSamples(): Promise<Sample[]> {
  return request("/samples", SampleSchema.array());
}

export function getSample(id: string, analysisType: AnalysisType): Promise<SampleDetail> {
  const query = new URLSearchParams({ analysis_type: analysisType });
  return request(`/samples/${encodeURIComponent(id)}?${query}`, SampleDetailSchema);
}
