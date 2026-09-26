/** Zod schemas mirroring the backend's Pydantic models. Every API response is parsed. */
import { z } from "zod";

export const SEVERITIES = ["critical", "high", "medium", "low", "info"] as const;
export const CATEGORIES = ["bug", "security", "performance", "style", "maintainability"] as const;
export const LANGUAGE_VALUES = ["python", "javascript", "typescript", "java", "go"] as const;
export const ANALYSIS_TYPE_VALUES = ["general", "security", "performance"] as const;

export const IssueSchema = z.object({
  severity: z.enum(SEVERITIES),
  line: z.number().int().min(1),
  category: z.enum(CATEGORIES),
  description: z.string(),
  suggestion: z.string(),
});

export const MetricsSchema = z.object({
  complexity: z.enum(["low", "medium", "high"]),
  readability: z.enum(["poor", "fair", "good", "excellent"]),
  test_coverage_estimate: z.enum(["none", "low", "medium", "high"]),
});

export const MetaSchema = z.object({
  analysis_type: z.enum(ANALYSIS_TYPE_VALUES),
  language: z.enum(LANGUAGE_VALUES),
  model: z.string(),
  prompt_version: z.string(),
  cached: z.boolean(),
  chunks: z.number().int(),
  tool_rounds: z.number().int(),
  llm_calls: z.number().int(),
  tokens: z.object({ input: z.number(), output: z.number(), thinking: z.number() }),
  truncated: z.boolean(),
  dropped_issues: z.number().int(),
});

export const AnalysisResultSchema = z.object({
  summary: z.string(),
  issues: z.array(IssueSchema),
  suggestions: z.array(z.string()),
  metrics: MetricsSchema,
  meta: MetaSchema,
});

export const SampleSchema = z.object({
  id: z.string(),
  title: z.string(),
  language: z.enum(LANGUAGE_VALUES),
  description: z.string(),
  analysis_types: z.array(z.enum(ANALYSIS_TYPE_VALUES)),
});

export const SampleDetailSchema = SampleSchema.extend({
  code: z.string(),
  result: AnalysisResultSchema.nullable(),
});

export const ProblemSchema = z.object({
  type: z.string(),
  title: z.string(),
  status: z.number(),
  detail: z.string().optional(),
  errors: z.array(z.object({ detail: z.string(), pointer: z.string() })).optional(),
});

export type Issue = z.infer<typeof IssueSchema>;
export type Severity = Issue["severity"];
export type AnalysisResult = z.infer<typeof AnalysisResultSchema>;
export type Sample = z.infer<typeof SampleSchema>;
export type SampleDetail = z.infer<typeof SampleDetailSchema>;
export type Language = (typeof LANGUAGE_VALUES)[number];
export type AnalysisType = (typeof ANALYSIS_TYPE_VALUES)[number];
