import type { AnalysisResult } from "@/lib/schemas";
import { countBySeverity, SEVERITY_BORDER, SEVERITY_ORDER, SEVERITY_STYLE, sortIssues } from "@/lib/severity";

type Props = { result: AnalysisResult; code: string };

const CARD = "rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900";

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-zinc-100 px-3 py-2 dark:bg-zinc-800">
      <div className="text-xs text-zinc-600 dark:text-zinc-400">{label}</div>
      <div className="font-semibold capitalize">{value}</div>
    </div>
  );
}

export default function Results({ result, code }: Props) {
  const lines = code.split("\n");
  const issues = sortIssues(result.issues);
  const counts = countBySeverity(result.issues);
  const { meta, metrics } = result;

  return (
    <div className="space-y-4" data-testid="results">
      <section className={CARD} aria-labelledby="summary-h">
        <h2 id="summary-h" className="mb-2 text-lg font-semibold">
          Summary
        </h2>
        <p className="text-sm leading-6">{result.summary}</p>
      </section>

      <section className={CARD} aria-labelledby="metrics-h">
        <h2 id="metrics-h" className="mb-3 text-lg font-semibold">
          Metrics
        </h2>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Chip label="Complexity" value={metrics.complexity} />
          <Chip label="Readability" value={metrics.readability} />
          <Chip label="Test coverage (est.)" value={metrics.test_coverage_estimate} />
        </div>
      </section>

      <section className={CARD} aria-labelledby="issues-h">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 id="issues-h" className="text-lg font-semibold">
            Issues ({issues.length})
          </h2>
          {SEVERITY_ORDER.filter((s) => counts[s]).map((s) => (
            <span key={s} className={`rounded px-2 py-0.5 text-xs font-semibold ${SEVERITY_STYLE[s]}`}>
              {counts[s]} {s}
            </span>
          ))}
        </div>
        {issues.length === 0 ? (
          <p className="text-sm text-zinc-600 dark:text-zinc-400">No issues found. 🎉</p>
        ) : (
          <ul className="space-y-3">
            {issues.map((issue, n) => (
              <li
                key={`${issue.line}-${n}`}
                className={`rounded-md border border-l-4 border-zinc-200 p-3 dark:border-zinc-800 ${SEVERITY_BORDER[issue.severity]}`}
              >
                <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
                  <span className={`rounded px-2 py-0.5 font-bold uppercase ${SEVERITY_STYLE[issue.severity]}`}>
                    {issue.severity}
                  </span>
                  <span className="rounded bg-zinc-100 px-2 py-0.5 dark:bg-zinc-800">{issue.category}</span>
                  <span className="text-zinc-500">Line {issue.line}</span>
                </div>
                {lines[issue.line - 1]?.trim() && (
                  <pre className="mb-2 overflow-x-auto rounded bg-zinc-100 px-2 py-1 font-mono text-xs dark:bg-zinc-800">
                    <code>
                      {issue.line}│ {lines[issue.line - 1]}
                    </code>
                  </pre>
                )}
                <p className="text-sm">{issue.description}</p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">
                  <span className="font-semibold">Fix: </span>
                  {issue.suggestion}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {result.suggestions.length > 0 && (
        <section className={CARD} aria-labelledby="suggestions-h">
          <h2 id="suggestions-h" className="mb-2 text-lg font-semibold">
            Suggestions
          </h2>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {result.suggestions.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-xs text-zinc-500" data-testid="meta">
        {meta.cached ? "Cached result · " : ""}
        {meta.model} · {meta.analysis_type} review · {meta.llm_calls} LLM calls · {meta.tool_rounds} tool rounds
        · {meta.chunks} {meta.chunks === 1 ? "part" : "parts"} ·{" "}
        {(meta.tokens.input + meta.tokens.output + meta.tokens.thinking).toLocaleString("en-US")} tokens
        {meta.truncated ? " · answer was shortened" : ""}
      </p>
    </div>
  );
}
