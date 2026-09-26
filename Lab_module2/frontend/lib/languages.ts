import type { AnalysisType, Language } from "./schemas";

export const MAX_CODE_CHARS = 60_000; // same limit as the backend (413 above it)

export const LANGUAGES: { value: Language; label: string; extensions: string[] }[] = [
  { value: "python", label: "Python", extensions: [".py"] },
  { value: "javascript", label: "JavaScript", extensions: [".js", ".jsx", ".mjs", ".cjs"] },
  { value: "typescript", label: "TypeScript", extensions: [".ts", ".tsx"] },
  { value: "java", label: "Java", extensions: [".java"] },
  { value: "go", label: "Go", extensions: [".go"] },
];

export const ANALYSIS_TYPES: { value: AnalysisType; label: string; hint: string }[] = [
  { value: "general", label: "General review", hint: "Bugs, readability, maintainability" },
  { value: "security", label: "Security", hint: "Injection, secrets, XSS, unsafe APIs" },
  { value: "performance", label: "Performance", hint: "Complexity, data structures, I/O" },
];

export const ACCEPTED_FILES = LANGUAGES.flatMap((l) => l.extensions).join(",");

/** Language from a file name's extension, or null if unknown. */
export function detectLanguage(fileName: string): Language | null {
  const lower = fileName.toLowerCase();
  const match = LANGUAGES.find((l) => l.extensions.some((ext) => lower.endsWith(ext)));
  return match ? match.value : null;
}
