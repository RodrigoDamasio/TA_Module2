Now produce the final review as JSON matching the provided schema.
- summary: 2-3 sentences on what the code does and its overall quality.
- issues: from your candidate findings, only those that survive the checks below.
- suggestions: up to 5 general improvements not tied to a single line.
- metrics: complexity (low/medium/high, informed by get_code_metrics when available),
  readability (poor/fair/good/excellent), test_coverage_estimate
  (none/low/medium/high, based on visible tests or testability).

Before answering, verify each issue:
[ ] the line number exists in the listing and points at the problem
[ ] the severity matches the rubric
[ ] it is not a duplicate of another issue
[ ] the suggestion is a concrete change
[ ] it is within the "{analysis_type}" focus, or serious enough to mention anyway
Drop or fix any issue that fails a check. Output only the JSON.
