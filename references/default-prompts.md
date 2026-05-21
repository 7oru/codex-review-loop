# Default Prompts

Load this file when `SKILL.md` asks for the default review or fix prompt. These prompts are defaults only; current user instructions or `.codex/review-loop.prompts.md` may replace either phase.

## Review Prompt

Review the current repository for exactly one review/fix loop pass. Focus only on P0/P1 correctness, security, data integrity, and core workflow failures.

Findings are actionable only when they include a concrete code path, a clear trigger condition, serious user impact, file and line references, and an explanation of why existing tests missed the issue. Do not report speculative issues. Do not inflate P2/P3 issues into P1. If no actionable P0/P1 issue exists, report `CLEAN`.

Output:

- outcome: `CLEAN` or `FOUND`
- highest-severity finding, if any
- why the issue is P0/P1
- affected files and lines
- test gap
- recommended minimal fix direction

## Fix Prompt

Fix only the selected P0/P1 issue from the review phase. Keep the patch minimal and consistent with the repository's existing patterns.

Add or update a regression test that would have caught the issue. Run the relevant tests, broadening to the full suite when risk warrants it. Do not include unrelated refactors or unrelated user changes. If a blocker prevents a safe fix, record `BLOCKED` with the evidence gathered.

Output:

- outcome: `FIXED` or `BLOCKED`
- fix summary
- regression test added or updated
- test commands and results
- affected files
- commit hash, when committed
