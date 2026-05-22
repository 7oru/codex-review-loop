# codex-review-loop

A Codex skill for running repository review/fix passes. It reviews for real P0/P1 issues, fixes one highest-severity issue when found, adds a regression test, commits the fix, and records durable loop state either in the repo or in tmp.

For `max round N`, the default mode is paired sessions: each round runs a fresh review-only `codex exec` session, then a fresh fix-only `codex exec` session if the review found an actionable issue.

## Install

Clone this repository into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
git clone git@github.com:7oru/codex-review-loop.git ~/.codex/skills/review-fix-loop
```

Then start a fresh Codex session and ask:

```text
Use $review-fix-loop to run one review/fix loop in this repository.
```

## What It Does

- Runs exactly one review/fix pass by default.
- Gates actionable findings to real P0/P1 issues only.
- Tracks loop history in the resolved `review-loop.md`.
- Commits fixes after tests pass.
- Supports paired review/fix sessions through `codex exec`.
- Supports explicit Codex automations when the user asks for a schedule.
- Supports custom review and fix prompt overrides per repository.
- Supports configurable max loop counts from user-level and repo-level config.
- Supports tmp-backed loop state so target repos do not need an internal `.codex` directory.

## Configuration

The continuous loop stops after `max_loop` total rounds. A request like "max loop 3", "max round 3", "最多 3 轮", "keep looping", or "until clean" is treated as continuous mode.

Continuous mode defaults to paired sessions, not app automation and not current-chat looping. `max round 3` means up to 3 review sessions and up to 3 fix sessions.

`max_loop` is only the cap. It is not a cadence. With the default config, `max round 3` alone should not create an hourly job.

The skill resolves `max_loop` in this order:

1. Current user instructions for the run.
2. Repository config: `.codex/review-loop.config.md`.
3. User Codex config: `${CODEX_HOME:-~/.codex}/review-loop.config.md`.
4. Default: `10`.

The skill resolves `state_dir` in the same order, with default `auto`.

Supported `state_dir` values:

- `auto`: use repo `.codex` only if it already exists and is writable; otherwise use tmp.
- `repo`: use repo `.codex` and create it if needed.
- `tmp`: use `${TMPDIR:-/tmp}/codex-review-loop/<repo-id>`.
- absolute path: use that path.

Config files use simple `key: value` lines:

```yaml
max_loop: 10
state_dir: tmp
continuous_mode: pair-sessions
session_runner: codex-exec
automation_cadence: require-explicit
```

Use the Codex config for your personal default across repos, and the repo config when a project needs a different cap or state location.

## Prompt Overrides

By default, the skill uses `references/default-prompts.md`. To customize the review or fix phases, create `review-loop.prompts.md` in the resolved state directory or `.codex/review-loop.prompts.md` in the repository:

```markdown
# Review Prompt

Review only the payment and auth paths. Keep the P0/P1 severity gate, and prioritize permission bypass, account isolation, and data-loss bugs.

# Fix Prompt

Fix the selected issue with the smallest patch possible. Prefer existing helpers and add a focused regression test before broadening the suite.
```

Each section is optional. If `# Review Prompt` is missing, the default review prompt is used. If `# Fix Prompt` is missing, the default fix prompt is used. Current user instructions for a run take priority over the file.

Prompt overrides can tune scope, output shape, and project-specific constraints. They do not replace the skill's safety, state-file, branch, commit, PR, or P0/P1 severity requirements unless the current user explicitly asks for that.

## Continuous Mode

For paired sessions, run:

```bash
python3 ~/.codex/skills/review-fix-loop/scripts/run_codex_pair_loop.py \
  --repo /path/to/repo \
  --max-rounds 3 \
  --review-prompt "review repo，看是否能满足大部分用户的本地一键使用"
```

On macOS the runner prefers `/Applications/Codex.app/Contents/Resources/codex` over the npm wrapper, because the npm wrapper can resolve differently from tmp state directories. Override with `CODEX_BIN` or `--codex-bin` when needed.

Or ask Codex:

```text
Use $review-fix-loop with max round 3.
```

With the default config, that should launch paired `codex exec` sessions. To create an active hourly automation instead, say:

```text
Use $review-fix-loop with max round 3, hourly.
```

The skill records state in the resolved `review-loop.md`, so later jobs can reuse the same loop branch and PR instead of starting over. With `state_dir: tmp`, the target repo does not need `.codex`.

## License

MIT
