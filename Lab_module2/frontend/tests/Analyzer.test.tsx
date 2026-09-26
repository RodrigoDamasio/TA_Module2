import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import Analyzer from "@/components/Analyzer";
import { ApiError, analyze, getSample, listSamples } from "@/lib/api";
import { CODE, RESULT, SAMPLE_DETAIL, SAMPLES } from "./fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  analyze: vi.fn(),
  listSamples: vi.fn(),
  getSample: vi.fn(),
}));
const mockAnalyze = vi.mocked(analyze);
const mockSamples = vi.mocked(listSamples);
const mockSample = vi.mocked(getSample);

beforeEach(() => {
  mockAnalyze.mockReset();
  mockSample.mockReset();
  mockSamples.mockReset().mockResolvedValue(SAMPLES);
});

async function setup() {
  const user = userEvent.setup();
  render(<Analyzer />);
  await screen.findByRole("combobox", { name: "Try a sample" });
  return {
    user,
    code: screen.getByLabelText("Code"),
    analyzeButton: screen.getByRole("button", { name: /analyze/i }),
  };
}

async function paste(user: ReturnType<typeof userEvent.setup>, code: HTMLElement, text: string) {
  await user.click(code);
  await user.paste(text);
}

// C1
test("C1: initial render", async () => {
  const { code, analyzeButton } = await setup();
  expect(code).toHaveValue("");
  expect(analyzeButton).toBeDisabled();
  expect(screen.getByLabelText("Language")).toHaveValue("python");
  expect(screen.getByLabelText("Analysis type")).toHaveValue("general");
  expect(screen.getByText(/sent to Google Gemini/)).toBeInTheDocument();
  expect(screen.getByText(/Results will appear here/)).toBeInTheDocument();
});

// C2
test("C2: typing enables Analyze; counter; too large disables", async () => {
  const { user, code, analyzeButton } = await setup();
  await paste(user, code, "a = 1\nb = 2");
  expect(analyzeButton).toBeEnabled();
  expect(screen.getByText(/2 lines · 11 \/ 60,000 characters/)).toBeInTheDocument();
  await paste(user, code, "x".repeat(60_000));
  expect(analyzeButton).toBeDisabled();
  expect(screen.getByText(/too large to analyze/)).toBeInTheDocument();
});

// C3
test("C3: upload fills the code and detects the language", async () => {
  const { user } = await setup();
  const file = new File(["const x: number = 1;\n"], "demo.ts", { type: "text/plain" });
  await user.upload(screen.getByLabelText("Upload file"), file);
  expect(await screen.findByDisplayValue("const x: number = 1;")).toBeInTheDocument();
  expect(screen.getByLabelText("Language")).toHaveValue("typescript");
});

// C4
test("C4: analyze sends the request, shows loading, blocks double submit", async () => {
  let resolve: (r: typeof RESULT) => void = () => {};
  mockAnalyze.mockReturnValue(new Promise((r) => (resolve = r)));
  const { user, code, analyzeButton } = await setup();
  await paste(user, code, CODE);
  await user.selectOptions(screen.getByLabelText("Analysis type"), "security");
  await user.click(analyzeButton);

  expect(mockAnalyze).toHaveBeenCalledWith({ code: CODE, language: "python", analysis_type: "security" });
  expect(analyzeButton).toBeDisabled();
  expect(analyzeButton).toHaveTextContent(/Analyzing…/);
  expect(analyzeButton).toHaveAttribute("aria-busy", "true");
  await user.click(analyzeButton);
  expect(mockAnalyze).toHaveBeenCalledTimes(1);
  await act(async () => resolve(RESULT));
  expect(await screen.findByTestId("results")).toBeInTheDocument();
});

// C5
test("C5: results are sorted, color-coded with text, with line preview and meta", async () => {
  mockAnalyze.mockResolvedValue(RESULT);
  const { user, code, analyzeButton } = await setup();
  await paste(user, code, CODE);
  await user.click(analyzeButton);

  const results = await screen.findByTestId("results");
  expect(within(results).getByText(RESULT.summary)).toBeInTheDocument();
  const items = within(results).getAllByRole("listitem").filter((li) => li.textContent?.includes("Line"));
  expect(items.map((li) => li.querySelector("span")?.textContent)).toEqual(["critical", "high", "medium"]);
  expect(items[0].querySelector("span")).toHaveClass("bg-red-700");
  expect(items[0]).toHaveClass("border-l-red-700");
  expect(within(items[0]).getByText("5│ return eval(cmd)", { exact: false })).toBeInTheDocument();
  expect(within(items[0]).getByText(/ast.literal_eval/)).toBeInTheDocument();
  expect(within(results).getByText("Complexity").nextSibling).toHaveTextContent("low");
  expect(within(results).getByText("Validate cmd against an allow-list.")).toBeInTheDocument();
  expect(screen.getByTestId("meta")).toHaveTextContent("3 LLM calls");
});

// C6
test("C6: no issues", async () => {
  mockAnalyze.mockResolvedValue({ ...RESULT, issues: [] });
  const { user, code, analyzeButton } = await setup();
  await paste(user, code, CODE);
  await user.click(analyzeButton);
  expect(await screen.findByText(/No issues found/)).toBeInTheDocument();
});

// C7
test("C7: field errors are listed", async () => {
  mockAnalyze.mockRejectedValue(
    new ApiError("validation", "The request is not valid.", undefined, ["Code: must not be blank"]),
  );
  const { user, code, analyzeButton } = await setup();
  await paste(user, code, CODE);
  await user.click(analyzeButton);
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("The request is not valid.");
  expect(alert).toHaveTextContent("Code: must not be blank");
});

// C8
test("C8: Retry-After starts a countdown that keeps Analyze disabled", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockAnalyze.mockRejectedValueOnce(new ApiError("rate_limited", "Too many analyses.", 3));
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  render(<Analyzer />);
  await screen.findByRole("combobox", { name: "Try a sample" });
  await user.click(screen.getByLabelText("Code"));
  await user.paste(CODE);
  const button = screen.getByRole("button", { name: /analyze/i });
  await user.click(button);

  expect(await screen.findByText("You can try again in 3 s.")).toBeInTheDocument();
  expect(button).toBeDisabled();
  for (const remaining of [2, 1]) {
    await act(async () => vi.advanceTimersByTime(1000)); // one tick per second, as in a browser
    expect(screen.getByText(`You can try again in ${remaining} s.`)).toBeInTheDocument();
  }
  await act(async () => vi.advanceTimersByTime(1000));
  expect(screen.queryByText(/You can try again/)).not.toBeInTheDocument();
  expect(button).toBeEnabled();
});

// C9
test("C9: a sample loads code and its stored result without analyzing", async () => {
  mockSample.mockResolvedValue(SAMPLE_DETAIL);
  const { user } = await setup();
  await user.selectOptions(screen.getByRole("combobox", { name: "Try a sample" }), "xss");

  expect(mockSample).toHaveBeenCalledWith("xss", "security");
  expect(await screen.findByTestId("results")).toBeInTheDocument();
  expect(screen.getByLabelText("Code")).toHaveValue(SAMPLE_DETAIL.code);
  expect(screen.getByLabelText("Language")).toHaveValue("javascript");
  expect(screen.getByLabelText("Analysis type")).toHaveValue("security");
  expect(screen.getByTestId("meta")).toHaveTextContent("Cached result");
  expect(mockAnalyze).not.toHaveBeenCalled();
});

// C10
test("C10: a new analysis clears the previous error", async () => {
  mockAnalyze
    .mockRejectedValueOnce(new ApiError("network", "Can't reach the analyzer."))
    .mockResolvedValueOnce(RESULT);
  const { user, code, analyzeButton } = await setup();
  await paste(user, code, CODE);
  await user.click(analyzeButton);
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  await user.click(analyzeButton);
  expect(await screen.findByTestId("results")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("samples failing to load hides the menu but keeps the analyzer usable", async () => {
  mockSamples.mockRejectedValue(new ApiError("network", "down"));
  render(<Analyzer />);
  await act(async () => {});
  expect(screen.queryByRole("combobox", { name: "Try a sample" })).not.toBeInTheDocument();
  expect(screen.getByLabelText("Code")).toBeInTheDocument();
});

test("unexpected errors get a generic message", async () => {
  mockAnalyze.mockRejectedValue(new Error("boom"));
  const { user, code, analyzeButton } = await setup();
  await paste(user, code, CODE);
  await user.click(analyzeButton);
  expect(await screen.findByRole("alert")).toHaveTextContent(/Unexpected error/);
});
