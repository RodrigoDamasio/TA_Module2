Correct finding:
  Code:  14│ query = f"SELECT * FROM users WHERE name = '{user_name}'"
  Issue: {"severity": "high", "line": 14, "category": "security",
          "description": "SQL query built from an f-string with the caller-supplied
          `user_name`; an attacker can inject SQL (e.g. user_name = \"' OR '1'='1\").",
          "suggestion": "Use a parameterized query:
          cursor.execute(\"SELECT * FROM users WHERE name = ?\", (user_name,))"}

Not a finding (do not report):
  Code:  3│ MAX_RETRIES = 3
  Why:   A named constant is good practice, not a problem.
