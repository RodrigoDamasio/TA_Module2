"use client";

import type { ChangeEvent } from "react";
import { ACCEPTED_FILES, ANALYSIS_TYPES, LANGUAGES, MAX_CODE_CHARS } from "@/lib/languages";
import type { AnalysisType, Language, Sample } from "@/lib/schemas";

type Props = {
  code: string;
  language: Language;
  analysisType: AnalysisType;
  samples: Sample[];
  disabled: boolean;
  onCodeChange: (code: string) => void;
  onLanguageChange: (language: Language) => void;
  onAnalysisTypeChange: (type: AnalysisType) => void;
  onUpload: (file: File) => void;
  onSample: (id: string) => void;
};

const SELECT =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900";

export default function CodeInput(props: Props) {
  const { code, language, analysisType, samples, disabled } = props;
  const lines = code ? code.split("\n").length : 0;
  const tooLarge = code.length > MAX_CODE_CHARS;

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) props.onUpload(file);
    e.target.value = ""; // allow re-uploading the same file
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm font-medium">
          <span>Language</span>
          <select
            className={SELECT}
            value={language}
            disabled={disabled}
            onChange={(e) => props.onLanguageChange(e.target.value as Language)}
          >
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm font-medium">
          <span>Analysis type</span>
          <select
            className={SELECT}
            value={analysisType}
            disabled={disabled}
            onChange={(e) => props.onAnalysisTypeChange(e.target.value as AnalysisType)}
          >
            {ANALYSIS_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label} — {t.hint}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label
          className={`cursor-pointer rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800 ${disabled ? "pointer-events-none opacity-50" : ""}`}
        >
          Upload file
          <input
            type="file"
            accept={ACCEPTED_FILES}
            className="sr-only"
            disabled={disabled}
            onChange={handleFile}
          />
        </label>
        {samples.length > 0 && (
          <select
            aria-label="Try a sample"
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value=""
            disabled={disabled}
            onChange={(e) => e.target.value && props.onSample(e.target.value)}
          >
            <option value="">Try a sample…</option>
            {samples.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} ({s.language})
              </option>
            ))}
          </select>
        )}
      </div>

      <label className="block space-y-1 text-sm font-medium">
        <span>Code</span>
        <textarea
          value={code}
          onChange={(e) => props.onCodeChange(e.target.value)}
          readOnly={disabled}
          spellCheck={false}
          rows={18}
          placeholder="Paste your code here, upload a file, or try a sample."
          className="w-full resize-y rounded-lg border border-zinc-300 bg-white p-3 font-mono text-xs leading-5 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/30 dark:border-zinc-700 dark:bg-zinc-900"
        />
      </label>
      <p
        className={`text-xs ${tooLarge ? "font-semibold text-red-700 dark:text-red-400" : "text-zinc-500"}`}
        aria-live="polite"
      >
        {lines} lines · {code.length.toLocaleString("en-US")} / {MAX_CODE_CHARS.toLocaleString("en-US")}{" "}
        characters{tooLarge ? " — too large to analyze" : ""}
      </p>
      <p className="text-xs text-zinc-500">
        🔒 Your code is sent to Google Gemini (free tier) for analysis. Don&apos;t paste secrets or
        proprietary code.
      </p>
    </div>
  );
}
