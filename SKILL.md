---
name: review-fix-loop
description: Use when the user asks to run one repository review/fix loop, one review-fix pass, continue or automate repeated review/fix sessions, customize review and fix prompts, configure max loop counts, or store loop state outside the repository for P0/P1 repo review and repair passes. Provides a single-pass workflow, durable loop state, branch/commit/PR lifecycle guidance, continuous automation guidance, prompt override support, max-loop configuration, and tmp state storage.
---

# Review/Fix Loop

Run exactly one review/fix pass for the current repository unless the user explicitly asks to start continuous mode. Treat any user request for `max_loop`, `max round`, `max rounds`, or "最多 N 轮" with a value greater than 1, repeated sessions, an automation, an interval, or "until clean" as explicit continuous mode. A clean pass is valid when no real P0/P1 issue exists.

## State File

Resolve the loop state directory before reading or writing state. Do not require the target repository to contain `.codex`.

Use the resolved state directory for:

- `review-loop.md`
- optional `review-loop.prompts.md`

State directory resolution:

1. Current user instructions for this run.
2. Repository config `.codex/review-loop.config.md`, if it exists.
3. User Codex config `${CODEX_HOME:-~/.codex}/review-loop.config.md`, if it exists.
4. Default `state_dir: auto`.

`state_dir` values:

- `auto`: use repository `.codex` only if it already exists and is writable; otherwise use tmp.
- `repo`: use repository `.codex` and create it if needed.
- `tmp`: use `${TMPDIR:-/tmp}/codex-review-loop/<repo-id>`.
- absolute path: use that path as the state directory.

When using tmp, choose a stable `<repo-id>` from the repository root path and remote URL if available, such as a readable slug plus a short hash. Record the resolved state path in the final response.

Before reviewing:

- Read `review-loop.md` from the resolved state directory if it exists.
- Avoid re-reporting issues already fixed, rejected, or marked non-P0/P1.
- Read repository instructions such as `AGENTS.md` if present.
- Resolve review and fix prompts using the prompt override rules below.

After the pass, update `review-loop.md` in the resolved state directory with:

- date
- loop number
- base branch
- working branch, if created
- PR URL or number, if created
- outcome: `CLEAN`, `FIXED`, or `BLOCKED`
- finding, if any
- affected files
- fix summary, if any
- regression test added or updated, if any
- test commands and results
- state directory and source used
- prompt sources used for review and fix
- max loop value and source used in continuous mode
- commit hash, when a fix was made
- consecutive clean count, when the outcome is `CLEAN`

## Configuration

Resolve configuration before each pass. Current user instructions override files.

Read simple `key: value` lines from config files:

```yaml
max_loop: 10
state_dir: tmp
```

Use this precedence for `max_loop`:

1. Current user instructions for this run.
2. Repository file `.codex/review-loop.config.md`.
3. User Codex file `${CODEX_HOME:-~/.codex}/review-loop.config.md`.
4. Default value `10`.

Use this precedence for `state_dir`:

1. Current user instructions for this run.
2. Repository file `.codex/review-loop.config.md`.
3. User Codex file `${CODEX_HOME:-~/.codex}/review-loop.config.md`.
4. Default value `auto`.

`max_loop` must be a positive integer. If a configured value is invalid or ambiguous, record `BLOCKED`, explain the invalid source, and ask the user to correct it.

`state_dir` must be `auto`, `repo`, `tmp`, or an absolute path. If it is invalid or cannot be created/written, fall back to tmp for `auto`; otherwise record `BLOCKED` and explain the invalid source.

In continuous mode, stop or pause the automation when `review-loop.md` shows total loop passes greater than or equal to the resolved `max_loop`. Record the resolved value and source in `review-loop.md`.

## Prompt Overrides

Use `references/default-prompts.md` for the default review and fix prompts.

Before the review phase, resolve prompts in this order:

1. Current user instructions for this run.
2. Resolved state directory file `review-loop.prompts.md`.
3. Repository file `.codex/review-loop.prompts.md`, if different from the resolved state directory and present.
4. Defaults from `references/default-prompts.md`.

The repository override file is optional. If it exists, parse these top-level headings:

```markdown
# Review Prompt

Full replacement prompt for the review phase.

# Fix Prompt

Full replacement prompt for the fix phase.
```

Each section is a full replacement for that phase only. If one section is missing or empty, use the default for that phase. Prompt overrides may tune scope, style, constraints, target areas, or output shape, but they do not override this skill's safety, state-file, branch, commit, PR, or severity-gate requirements unless the current user explicitly changes those requirements.

Record the prompt source used for each phase in `review-loop.md`, for example `default`, `user instruction`, `state:review-loop.prompts.md#Review Prompt`, or `.codex/review-loop.prompts.md#Review Prompt`.

## Branch, Commit, And PR Lifecycle

When the loop makes a fix, commit it. Do not leave completed fixes uncommitted.

For continuous mode:

- On the first fix, create a new working branch from the latest `main`.
- Before creating that branch, fetch the remote and update local `main` from `origin/main` with a fast-forward-only update.
- Use a branch name like `codex/review-fix-loop-YYYYMMDD`.
- Commit the fix and regression test together.
- Push the branch and open a new PR against `main`.
- Record the branch and PR URL or number in the resolved `review-loop.md`.
- On later jobs, reuse the recorded branch and PR. Do not create a second PR for the same loop.
- Add every later fix as a new commit on that same branch and push it to the same PR.
- If the repository has uncommitted user changes that would be mixed into the loop branch or commit, record `BLOCKED` and ask for intervention instead of stashing, discarding, or committing unrelated work.
- If PR creation is unavailable because auth, remote, or `gh` is missing, still commit the fix on the loop branch, record `BLOCKED`, and explain what is needed to open the PR.

For single-pass mode:

- Commit fixes after tests pass.
- Do not push or open a PR unless the user asked for that or the skill is running in continuous mode.

## Severity Gate

Only P0/P1 issues are actionable in this loop.

A P1 must have all of:

- concrete code path
- clear trigger condition
- serious user impact, such as data loss, permission bypass, security exposure, core workflow failure, incorrect critical result, or production-grade crash
- file and line reference
- explanation of why existing tests missed it

Do not inflate P2/P3 issues into P1 to produce findings. Do not report speculative issues. No finding is valid.

## Workflow

1. Inspect the repository enough to understand language, framework, test commands, and critical paths.
2. Perform a full-repo review focused only on P0/P1 correctness, security, data integrity, and core workflow failures, using the resolved review prompt.
3. If no actionable P0/P1 issue exists:
   - report `CLEAN`
   - run the most relevant available tests
   - update the resolved `review-loop.md`
   - stop
4. If multiple actionable issues exist:
   - choose the single highest-severity issue
   - record other issues briefly only if they are clearly P0/P1 and should be revisited
5. Fix only the chosen issue, using the resolved fix prompt.
6. Keep the patch minimal and consistent with existing repo patterns.
7. Add or update a regression test that would have caught the issue.
8. Run relevant tests, broadening to the full suite when risk warrants it.
9. Update the resolved `review-loop.md`.
10. Stop after this single pass.

## Continuous Mode

Use this section when the user explicitly asks to keep looping, create new sessions, run repeatedly, continue until clean, start an automation, or provides a max loop/max round count greater than 1.

Do not implement continuous mode as an infinite loop inside the current session. If the user asks for long-running or repeated work, directly create or update a Codex automation when automation tools are available. If the user explicitly asks to run multiple passes now, run at most the resolved `max_loop` passes and stop early on `CLEAN`, `BLOCKED`, or failing tests.

Recommended automation behavior:

- Run one review/fix pass per automation job.
- Reuse this skill's normal workflow inside each job.
- Use the resolved `review-loop.md` as the durable state between jobs.
- Prefer a tmp state directory when configured; do not create repository `.codex` unless `state_dir: repo` or the user asks for repo-local state.
- Re-resolve `max_loop` at the start of every job.
- Re-resolve `state_dir` at the start of every job.
- Re-resolve prompt overrides at the start of every job.
- Stop or pause the automation after the resolved `max_loop` total passes.
- Stop or pause the automation after two consecutive `CLEAN` outcomes with passing tests.
- If a fix is made, the next job should start from the updated repository state and loop log.
- If a PR already exists in `review-loop.md`, continue committing to that PR branch.
- If blocked, record `BLOCKED` and pause or ask the user for intervention rather than repeatedly retrying.

If Codex automation tools are available, create or update a recurring automation for the current repository with a prompt equivalent to:

```text
Use $review-fix-loop to run one review/fix loop in this repository. In continuous mode, commit every fix. On the first fix, create a branch from the latest main, push it, and open one PR; on later fixes, commit to the same PR branch recorded in the resolved `review-loop.md`. Resolve state_dir from the current user request, then `.codex/review-loop.config.md`, then `${CODEX_HOME:-~/.codex}/review-loop.config.md`, then default auto; if state_dir is tmp, do not create repo-local `.codex`. Resolve max_loop from the current user request, then `.codex/review-loop.config.md`, then `${CODEX_HOME:-~/.codex}/review-loop.config.md`, then default 10. Resolve review and fix prompts from the current user request, then the resolved state directory `review-loop.prompts.md`, then `.codex/review-loop.prompts.md`, then the skill defaults. If `review-loop.md` shows total loop passes greater than or equal to max_loop, pause this automation and report that the max loop count was reached. If `review-loop.md` shows two consecutive CLEAN outcomes with passing tests, pause this automation and report that the loop has converged. If a BLOCKED outcome is recorded, pause and report the blocker.
```

If automation tools are unavailable, explain that the skill can still be triggered manually in each fresh session with:

```text
Use $review-fix-loop to run one review/fix loop in this repository.
```

## Output

In the final response, include:

- outcome: `CLEAN`, `FIXED`, or `BLOCKED`
- concise finding/fix summary
- tests run and result
- max loop value and source used in continuous mode
- state directory used
- prompt override sources used
- path to `review-loop.md`

If blocked, explain the blocker and what evidence was gathered.
