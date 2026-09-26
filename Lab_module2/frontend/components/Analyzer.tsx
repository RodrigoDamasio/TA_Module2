"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, analyze, getSample, listSamples } from "@/lib/api";
import { detectLanguage, MAX_CODE_CHARS } from "@/lib/languages";
import type { AnalysisResult, AnalysisType, Language, Sample } from "@/lib/schemas";
import CodeInput from "./CodeInput";
import Results from "./Results";

export default function Analyzer() {
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState<Language>("python");
  const [analysisType, setAnalysisType] = useState<AnalysisType>("general");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [resultCode, setResultCode] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const busy = useRef(false);

  useEffect(() => {
    listSamples()
      .then(setSamples)
      .catch(() => setSamples([])); // samples are optional; the analyzer still works
  }, []);

  useEffect(() => {
    if (!loading) return;
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  function fail(err: unknown) {
    const apiError =
      err instanceof ApiError ? err : new ApiError("server", "Unexpected error. Please try again.");
    setError(apiError);
    setCooldown(apiError.retryAfter ?? 0);
  }

  async function run(action: () => Promise<void>) {
    if (busy.current) return;
    busy.current = true;
    setError(null);
    setResult(null);
    setElapsed(0);
    setLoading(true);
    try {
      await action();
    } catch (err) {
      fail(err);
    } finally {
      busy.current = false;
      setLoading(false);
    }
  }

  function handleAnalyze() {
    const submitted = code;
    return run(async () => {
      setResult(await analyze({ code: submitted, language, analysis_type: analysisType }));
      setResultCode(submitted);
    });
  }

  function handleSample(id: string) {
    const sample = samples.find((s) => s.id === id);
    if (!sample) return;
    const type = sample.analysis_types.includes(analysisType) ? analysisType : sample.analysis_types[0];
    return run(async () => {
      const detail = await getSample(id, type);
      setCode(detail.code);
      setLanguage(detail.language);
      setAnalysisType(type);
      setResult(detail.result);
      setResultCode(detail.code);
    });
  }

  async function handleUpload(file: File) {
    const text = await file.text();
    setCode(text);
    const detected = detectLanguage(file.name);
    if (detected) setLanguage(detected);
    setResult(null);
    setError(null);
  }

  const canAnalyze = code.trim().length > 0 && code.length <= MAX_CODE_CHARS && !loading && cooldown === 0;

  return (
    <div className="grid w-full grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="space-y-3">
        <CodeInput
          code={code}
          language={language}
          analysisType={analysisType}
          samples={samples}
          disabled={loading}
          onCodeChange={setCode}
          onLanguageChange={setLanguage}
          onAnalysisTypeChange={setAnalysisType}
          onUpload={handleUpload}
          onSample={handleSample}
        />
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={!canAnalyze}
          aria-busy={loading}
          className="w-full rounded-lg bg-blue-600 px-5 py-3 font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
        >
          {loading ? `Analyzing… ${elapsed}s` : "Analyze"}
        </button>
      </div>

      <div aria-live="polite" className="min-w-0">
        {loading && (
          <div className="flex items-center gap-3 rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
            <span>
              The agent is reading your code and using its tools… {elapsed}s (usually 5–15 s)
            </span>
          </div>
        )}
        {error && (
          <div role="alert" className="space-y-1 rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-red-950/50 dark:text-red-200">
            <p className="font-semibold">{error.message}</p>
            {error.fieldErrors.map((f) => (
              <p key={f}>{f}</p>
            ))}
            {cooldown > 0 && <p>You can try again in {cooldown} s.</p>}
          </div>
        )}
        {result && <Results result={result} code={resultCode} />}
        {!loading && !error && !result && (
          <div className="rounded-lg border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-500 dark:border-zinc-700">
            Results will appear here: a summary, issues color-coded by severity, suggestions, and
            metrics.
          </div>
        )}
      </div>
    </div>
  );
}
