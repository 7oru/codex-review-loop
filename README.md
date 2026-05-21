# codex-review-loop

A Codex skill for running one repository review/fix pass at a time. It is designed for repeated sessions: review for real P0/P1 issues, fix one highest-severity issue when found, add a regression test, commit the fix, and record durable state in `.codex/review-loop.md`.

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
- Tracks loop history in `.codex/review-loop.md`.
- Commits fixes after tests pass.
- Supports continuous mode through Codex automations instead of an in-session infinite loop.
- Supports custom review and fix prompt overrides per repository.

## Prompt Overrides

By default, the skill uses `references/default-prompts.md`. To customize the review or fix phases for a repository, create `.codex/review-loop.prompts.md` in that repository:

```markdown
# Review Prompt

Review only the payment and auth paths. Keep the P0/P1 severity gate, and prioritize permission bypass, account isolation, and data-loss bugs.

# Fix Prompt

Fix the selected issue with the smallest patch possible. Prefer existing helpers and add a focused regression test before broadening the suite.
```

Each section is optional. If `# Review Prompt` is missing, the default review prompt is used. If `# Fix Prompt` is missing, the default fix prompt is used. Current user instructions for a run take priority over the file.

Prompt overrides can tune scope, output shape, and project-specific constraints. They do not replace the skill's safety, state-file, branch, commit, PR, or P0/P1 severity requirements unless the current user explicitly asks for that.

## Continuous Mode

For repeated sessions, ask Codex to create or update an automation:

```text
Use $review-fix-loop to run one review/fix loop in this repository every hour until two consecutive CLEAN passes.
```

The skill records state in `.codex/review-loop.md`, so later jobs can reuse the same loop branch and PR instead of starting over.

## License

MIT
