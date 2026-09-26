import Analyzer from "@/components/Analyzer";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-8 sm:py-12">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Code Analyzer</h1>
        <p className="max-w-3xl text-zinc-600 dark:text-zinc-400">
          An AI agent reviews your code and returns a summary, issues color-coded by severity,
          suggestions, and metrics. Choose a general, security, or performance review.
        </p>
      </header>
      <Analyzer />
    </main>
  );
}
