<a id="top"></a>

# codex-review-loop

**Language:** English | [简体中文](README.zh-CN.md)

Codex skill for P0/P1 repository review/fix loops with paired or batch `codex exec` runners.

Recommended GitHub description:

```text
Codex skill for P0/P1 repository review/fix loops with paired or batch codex exec runners.
```

## Contents

- [What It Is](#what-it-is)
- [When To Use It](#when-to-use-it)
- [Install](#install)
- [Common Usage](#common-usage)
- [Runner Modes](#runner-modes)
- [Configuration](#configuration)
- [Prompt Overrides](#prompt-overrides)
- [Description Guidance](#description-guidance)
- [License](#license)

<a id="what-it-is"></a>

## What It Is

`codex-review-loop` is a Codex skill for repeatable repository review/fix passes. It keeps the loop focused on severe, actionable issues instead of turning a review into a general backlog.

By default it:

- reviews only for real P0/P1 correctness, security, data integrity, and core workflow failures;
- keeps review sessions read-only;
- fixes only the selected issue or selected safe batch;
- adds or updates regression coverage;
- commits fixes after tests pass;
- records durable loop state in `review-loop.md`.

[Back to top](#top)

<a id="when-to-use-it"></a>

## When To Use It

Use it when you want Codex to:

- check a release-critical workflow before shipping;
- verify a local install/run path;
- look for serious regressions after a large change;
- run several review/fix rounds without keeping the current chat in an open-ended loop.

Do not use it as a replacement for CI, broad style review, or P2/P3 backlog generation.

[Back to top](#top)

<a id="install"></a>

## Install

Clone this repository into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
git clone git@github.com:7oru/codex-review-loop.git ~/.codex/skills/review-fix-loop
```

Start a new Codex session in your target repository and ask:

```text
Use $review-fix-loop to run one review/fix loop in this repository.
```

[Back to top](#top)

<a id="common-usage"></a>

## Common Usage

Run one pass:

```text
Use $review-fix-loop to run one review/fix loop in this repository.
```

Run up to three rounds:

```text
Use $review-fix-loop with max round 3.
```

Limit the review scope:

```text
Use $review-fix-loop with max round 3. Review only the local one-click install/run path.
```

If you want a scheduled automation, say the cadence explicitly. `max round 3` is only a cap:

```text
Use $review-fix-loop with max round 3, hourly.
```

[Back to top](#top)

<a id="runner-modes"></a>

## Runner Modes

The bundled runner starts child `codex exec` sessions for you.

Batch mode is lighter: one review session can report up to N P0/P1 findings, then one fix session repairs the safe coherent batch.

```bash
python3 ~/.codex/skills/review-fix-loop/scripts/run_codex_pair_loop.py \
  --repo /path/to/repo \
  --max-rounds 3 \
  --runner-mode batch \
  --test-profile focused \
  --review-prompt "review only the local one-click install/run path"
```

Paired mode is stricter: each round starts a fresh review session and, when needed, a fresh fix session.

```bash
python3 ~/.codex/skills/review-fix-loop/scripts/run_codex_pair_loop.py \
  --repo /path/to/repo \
  --max-rounds 3 \
  --runner-mode paired \
  --review-prompt "review whether most users can run this locally in one command"
```

Useful options:

- `--runner-mode batch`: faster local multi-finding review/fix.
- `--runner-mode paired`: stricter per-round traceability.
- `--test-profile focused`: run cheap tests for touched behavior.
- `--test-profile final-full`: run focused tests during the loop and broader validation at the end.
- `--test-profile full`: run the broadest practical validation after each fix.
- `--state-dir tmp`: keep loop state outside the target repository.
- `--prompt-profile skill`: load the full skill in child sessions, mainly for debugging the skill itself.
- `--ignore-user-config`: reduce noise from user-level config or plugin sync.

On macOS, the runner prefers `/Applications/Codex.app/Contents/Resources/codex` over the npm wrapper. Override it with `CODEX_BIN` or `--codex-bin` when needed.

[Back to top](#top)

<a id="configuration"></a>

## Configuration

`max_loop` is a round cap, not a schedule. Configuration precedence:

1. Current user request.
2. Repository config: `.codex/review-loop.config.md`.
3. User config: `${CODEX_HOME:-~/.codex}/review-loop.config.md`.
4. Default: `10`.

Config files use simple `key: value` lines:

```yaml
max_loop: 10
state_dir: tmp
continuous_mode: pair-sessions
session_runner: codex-exec
automation_cadence: require-explicit
```

Supported `state_dir` values:

- `auto`: use repo `.codex` only if it already exists and is writable; otherwise use tmp.
- `repo`: use repo `.codex` and create it if needed.
- `tmp`: use `${TMPDIR:-/tmp}/codex-review-loop/<repo-id>`.
- absolute path: use that path.

[Back to top](#top)

<a id="prompt-overrides"></a>

## Prompt Overrides

Create `review-loop.prompts.md` in the resolved state directory or in the repository `.codex/` directory:

```markdown
# Review Prompt

Review only the payment and auth paths. Keep the P0/P1 severity gate, and prioritize permission bypass, account isolation, and data-loss bugs.

# Fix Prompt

Fix the selected issue with the smallest patch possible. Prefer existing helpers and add a focused regression test before broadening the suite.
```

Each section is optional. Missing sections fall back to the default prompts. Current user instructions for a run take priority over the file.

[Back to top](#top)

<a id="description-guidance"></a>

## Description Guidance

For the GitHub repository description, use a short product-style sentence:

```text
Codex skill for P0/P1 repository review/fix loops with paired or batch codex exec runners.
```

For the skill frontmatter `description`, use trigger-oriented wording so Codex knows when to load it:

```text
Use when the user asks Codex to review a repository for actionable P0/P1 issues, fix the selected issue or safe batch, add regression tests, commit the fix, and record loop state. Supports single-pass, paired, batch, max-round, prompt overrides, tmp/repo state, and explicit automations.
```

[Back to top](#top)

<a id="license"></a>

## License

MIT

[Back to top](#top)
