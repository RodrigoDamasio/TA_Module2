import { expect, test } from "vitest";
import { ACCEPTED_FILES, detectLanguage } from "@/lib/languages";
import { countBySeverity, sortIssues } from "@/lib/severity";
import { RESULT } from "./fixtures";

test.each([
  ["app.py", "python"],
  ["Main.JAVA", "java"],
  ["index.tsx", "typescript"],
  ["util.mjs", "javascript"],
  ["server.go", "go"],
  ["notes.txt", null],
])("detectLanguage(%s) = %s", (name, expected) => {
  expect(detectLanguage(name)).toBe(expected);
});

test("accepted files cover every language", () => {
  expect(ACCEPTED_FILES.split(",")).toEqual(
    expect.arrayContaining([".py", ".js", ".ts", ".tsx", ".java", ".go"]),
  );
});

test("issues sort by severity, then line", () => {
  expect(sortIssues(RESULT.issues).map((i) => [i.severity, i.line])).toEqual([
    ["critical", 5],
    ["high", 4],
    ["medium", 3],
  ]);
  expect(countBySeverity(RESULT.issues)).toEqual({ critical: 1, high: 1, medium: 1 });
});
