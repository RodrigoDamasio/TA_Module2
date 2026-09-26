import type { Issue, Severity } from "./schemas";

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

/** Badge colors per severity. The badge always shows the severity as text too. */
export const SEVERITY_STYLE: Record<Severity, string> = {
  critical: "bg-red-700 text-white",
  high: "bg-orange-700 text-white", // orange-600 fails WCAG contrast with white text
  medium: "bg-amber-300 text-amber-950",
  low: "bg-sky-200 text-sky-950",
  info: "bg-zinc-200 text-zinc-800",
};

/** Left border of an issue card, matching its badge. */
export const SEVERITY_BORDER: Record<Severity, string> = {
  critical: "border-l-red-700",
  high: "border-l-orange-700",
  medium: "border-l-amber-400",
  low: "border-l-sky-400",
  info: "border-l-zinc-400",
};

export function sortIssues(issues: Issue[]): Issue[] {
  return [...issues].sort(
    (a, b) =>
      SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity) || a.line - b.line,
  );
}

export function countBySeverity(issues: Issue[]): Partial<Record<Severity, number>> {
  const counts: Partial<Record<Severity, number>> = {};
  for (const issue of issues) counts[issue.severity] = (counts[issue.severity] ?? 0) + 1;
  return counts;
}
