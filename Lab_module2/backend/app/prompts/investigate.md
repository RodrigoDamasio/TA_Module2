Analyze the code below for a "{analysis_type}" review. Work step by step:
1. Understand: what does this code do? Identify inputs, outputs, and external calls.
2. Inspect: go through the code looking for problems in your focus areas.
3. Verify: use the tools when they help you be precise — get_code_metrics for
   complexity, read_lines to re-read an exact range, find_text to locate every
   occurrence of a risky call.
You may call tools at most {max_tool_rounds} times. When you are done investigating,
reply with a short list of candidate findings (line + one sentence each).

{chunk_header}
<code language="{language}">
{numbered_code}
</code>
