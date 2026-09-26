# Evaluation report — `gemini-3.5-flash-lite`, prompt v1, set `smoke`

- Cases scored: **3/3**
- Schema validity: **3/3** (every stored result passed strict Pydantic validation)
- Recall of planted issues: **4/4 = 100%** (target ≥ 90%) ✅
- False alarms on clean code: **0** ✅
- Real LLM calls in the last run: **7** (cached cases cost 0)

| Case | Status | Found | Missed | False alarms | Calls | Chunks | Tool rounds | Tokens in / out |
|---|---|---|---|---|---|---|---|---|
| sql-injection.security | ran | 1/1 | — | — | 3 | 1 | 1 | 4157 / 300 |
| buggy.general | ran | 3/3 | — | — | 2 | 1 | 0 | 2617 / 485 |
| clean.general | ran | 0/0 | — | — | 2 | 1 | 0 | 2637 / 169 |
