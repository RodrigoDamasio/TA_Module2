import type { AnalysisResult, Sample, SampleDetail } from "@/lib/schemas";

export const CODE = "import os\n\ndef run(cmd):\n    os.system(cmd)\n    return eval(cmd)\n";

export const RESULT: AnalysisResult = {
  summary: "Runs shell commands and evaluates input; two serious injection risks.",
  issues: [
    {
      severity: "medium",
      line: 3,
      category: "maintainability",
      description: "No type hints on the public function.",
      suggestion: "def run(cmd: str) -> object:",
    },
    {
      severity: "critical",
      line: 5,
      category: "security",
      description: "eval() executes arbitrary user input.",
      suggestion: "Use ast.literal_eval or a parser for the expected format.",
    },
    {
      severity: "high",
      line: 4,
      category: "security",
      description: "os.system with user input allows command injection.",
      suggestion: "subprocess.run([...], check=True) without a shell.",
    },
  ],
  suggestions: ["Validate cmd against an allow-list."],
  metrics: { complexity: "low", readability: "good", test_coverage_estimate: "none" },
  meta: {
    analysis_type: "security",
    language: "python",
    model: "gemini-3.5-flash-lite",
    prompt_version: "1",
    cached: false,
    chunks: 1,
    tool_rounds: 1,
    llm_calls: 3,
    tokens: { input: 4000, output: 300, thinking: 100 },
    truncated: false,
    dropped_issues: 0,
  },
};

export const SAMPLES: Sample[] = [
  {
    id: "xss",
    title: "XSS and eval",
    language: "javascript",
    description: "innerHTML and eval",
    analysis_types: ["security"],
  },
];

export const SAMPLE_DETAIL: SampleDetail = {
  ...SAMPLES[0],
  code: 'box.innerHTML = "<h2>" + name + "</h2>";\neval(formula);\n',
  result: { ...RESULT, meta: { ...RESULT.meta, cached: true, language: "javascript" } },
};
