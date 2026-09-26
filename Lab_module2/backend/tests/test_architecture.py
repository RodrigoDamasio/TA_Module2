"""Layering and security guards (S1–S3), as in Lab 1."""

import ast
import logging
import subprocess
import sys
from pathlib import Path

from fakes import report, text

APP = Path(__file__).resolve().parents[1] / "app"


def imported_modules(path: Path) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def offenders(layer: str, forbidden: set[str]) -> set[str]:
    return {
        f"{p.relative_to(APP)} imports {m}"
        for p in (APP / layer).rglob("*.py")
        for m in imported_modules(p)
        if any(m == f or m.startswith(f + ".") for f in forbidden)
    }


FRAMEWORKS = {"fastapi", "starlette", "google", "sqlite3", "lizard", "httpx"}


# S1
def test_domain_imports_only_stdlib_and_pydantic():
    assert (
        offenders(
            "domain", FRAMEWORKS | {"app.application", "app.infrastructure", "app.api", "app.tools"}
        )
        == set()
    )


def test_application_does_not_touch_frameworks_or_infrastructure():
    assert offenders("application", FRAMEWORKS | {"app.infrastructure", "app.api"}) == set()


# S2
def test_provider_sdk_sqlite_and_lizard_stay_in_their_modules():
    where = {"google": set(), "sqlite3": set(), "lizard": set()}
    for path in APP.rglob("*.py"):
        for module in imported_modules(path):
            for lib in where:
                if module == lib or module.startswith(lib + "."):
                    where[lib].add(str(path.relative_to(APP)))
    assert where["google"] == {"infrastructure/gemini_client.py"}
    assert where["sqlite3"] == {"infrastructure/sqlite_cache.py"}
    assert where["lizard"] == {"tools/metrics.py"}


# S3
def test_ruff_flags_sql_built_from_strings(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def f(c, x):\n    return c.execute(f\"SELECT * FROM t WHERE a = '{x}'\")\n")
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--select", "S608", str(bad)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "S608" in result.stdout


def test_logs_never_contain_code_or_key(client, llm, caplog):
    private_code = "TOP_SECRET_ALGORITHM = 42"
    llm.responses += [text(), report()]
    with caplog.at_level(logging.DEBUG):
        client.post("/analyze", json={"code": private_code, "language": "python"})
    logged = caplog.text
    assert "analyze language=python" in logged
    assert "TOP_SECRET_ALGORITHM" not in logged
    assert "test-key-never-used" not in logged
