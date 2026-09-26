# Evaluation report — `gemini-3.5-flash-lite`, prompt v1, set `full`

- Cases scored: **12/12**
- Schema validity: **12/12** (every stored result passed strict Pydantic validation)
- Recall of planted issues: **15/15 = 100%** (target ≥ 90%) ✅
- False alarms on clean code: **0** ✅
- Real LLM calls in the last run: **0** (cached cases cost 0)

| Case | Status | Found | Missed | False alarms | Calls | Chunks | Tool rounds | Tokens in / out |
|---|---|---|---|---|---|---|---|---|
| sql-injection.security | cached | 1/1 | — | — | 3 | 1 | 1 | 4157 / 300 |
| sql-injection.general | cached | 1/1 | — | — | 3 | 1 | 1 | 4060 / 319 |
| hardcoded-secret.security | cached | 1/1 | — | — | 3 | 1 | 1 | 4258 / 318 |
| slow-lookup.performance | cached | 2/2 | — | — | 3 | 1 | 1 | 4336 / 477 |
| slow-lookup.general | cached | 1/1 | — | — | 3 | 1 | 1 | 4462 / 691 |
| buggy.general | cached | 3/3 | — | — | 2 | 1 | 0 | 2617 / 485 |
| xss.security | cached | 2/2 | — | — | 3 | 1 | 1 | 4211 / 572 |
| loose-types.general | cached | 2/2 | — | — | 3 | 1 | 1 | 4115 / 612 |
| clean.general | cached | 0/0 | — | — | 2 | 1 | 0 | 2637 / 169 |
| clean.security | cached | 0/0 | — | — | 3 | 1 | 1 | 4242 / 219 |
| prompt-injection.security | cached | 1/1 | — | — | 3 | 1 | 1 | 4166 / 473 |
| large-module.security | cached | 1/1 | — | — | 6 | 3 | 1 | 20630 / 640 |
