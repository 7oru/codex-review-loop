#!/usr/bin/env python3
"""Run review/fix loop rounds as separate Codex exec sessions."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Optional


def repo_id(repo: Path) -> str:
    remote = ""
    try:
        remote = subprocess.check_output(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        pass
    digest = hashlib.sha256(f"{repo.resolve()}\n{remote}".encode()).hexdigest()[:12]
    return f"{repo.name}-{digest}"


def default_state_dir(repo: Path) -> Path:
    root = Path(os.environ.get("TMPDIR") or "/tmp")
    return root / "codex-review-loop" / repo_id(repo)


def run_codex(
    codex_bin: str,
    repo: Path,
    state_dir: Path,
    prompt: str,
    output_file: Path,
    model: Optional[str],
    approval: Optional[str],
    sandbox: Optional[str],
    dry_run: bool,
) -> str:
    cmd = [
        codex_bin,
        "exec",
        "-C",
        str(repo),
        "--add-dir",
        str(state_dir),
        "--output-last-message",
        str(output_file),
    ]
    if model:
        cmd.extend(["--model", model])
    if approval:
        cmd.extend(["--ask-for-approval", approval])
    if sandbox:
        cmd.extend(["--sandbox", sandbox])
    cmd.append(prompt)

    if dry_run:
        print("DRY RUN:", " ".join(cmd))
        if "review" in output_file.name:
            return "REVIEW_LOOP_OUTCOME=FOUND"
        return "FIX_LOOP_OUTCOME=FIXED"

    subprocess.run(cmd, check=True)
    return output_file.read_text(encoding="utf-8") if output_file.exists() else ""


def outcome(text: str, marker: str) -> str | None:
    match = re.search(rf"^{re.escape(marker)}=(CLEAN|FOUND|FIXED|NOOP|BLOCKED)\s*$", text, re.M)
    return match.group(1) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run max_rounds review/fix pairs as separate codex exec sessions."
    )
    parser.add_argument("--repo", default=".", help="Repository root to review.")
    parser.add_argument("--max-rounds", type=int, required=True, help="Maximum review/fix pairs.")
    parser.add_argument("--review-prompt", required=True, help="Review prompt override.")
    parser.add_argument("--fix-prompt", default="", help="Fix prompt override.")
    parser.add_argument("--state-dir", help="State directory. Defaults to tmp.")
    parser.add_argument("--codex-bin", default="codex", help="Codex executable.")
    parser.add_argument("--model", help="Model to pass to codex exec.")
    parser.add_argument("--ask-for-approval", default="on-request", help="Approval policy.")
    parser.add_argument("--sandbox", default="workspace-write", help="Sandbox mode.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them.")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if args.max_rounds < 1:
        parser.error("--max-rounds must be positive")

    state_dir = Path(args.state_dir).resolve() if args.state_dir else default_state_dir(repo)
    state_dir.mkdir(parents=True, exist_ok=True)

    print(f"repo={repo}")
    print(f"state_dir={state_dir}")
    print(f"max_rounds={args.max_rounds}")

    for round_number in range(1, args.max_rounds + 1):
        review_file = state_dir / f"round-{round_number}-review.md"
        fix_file = state_dir / f"round-{round_number}-fix.md"

        review_prompt = f"""Use $review-fix-loop for REVIEW ONLY.

Round: {round_number}/{args.max_rounds}
State directory: {state_dir}
Review output file: {review_file}

Review prompt override:
{args.review_prompt}

Rules:
- Start a fresh review-only pass for this repository.
- Do not edit repository files and do not fix issues in this review session.
- Review only for actionable P0/P1 correctness, security, data integrity, and core workflow failures.
- If no actionable P0/P1 issue exists, write CLEAN.
- If one exists, write exactly the single highest-severity finding with file/line references and why existing tests missed it.
- Write the review result to the review output file and update review-loop.md in the state directory.
- End the final response with exactly one marker line: REVIEW_LOOP_OUTCOME=CLEAN, REVIEW_LOOP_OUTCOME=FOUND, or REVIEW_LOOP_OUTCOME=BLOCKED.
"""
        review_text = run_codex(
            args.codex_bin,
            repo,
            state_dir,
            review_prompt,
            review_file,
            args.model,
            args.ask_for_approval,
            args.sandbox,
            args.dry_run,
        )
        review_outcome = outcome(review_text, "REVIEW_LOOP_OUTCOME")
        print(f"round {round_number} review outcome={review_outcome or 'UNKNOWN'}")
        if review_outcome in {"CLEAN", "BLOCKED"}:
            return 0 if review_outcome == "CLEAN" else 1
        if review_outcome != "FOUND":
            print("Review session did not emit a valid outcome marker.", file=sys.stderr)
            return 1

        fix_prompt = f"""Use $review-fix-loop for FIX ONLY.

Round: {round_number}/{args.max_rounds}
State directory: {state_dir}
Review input file: {review_file}
Fix output file: {fix_file}

Fix prompt override:
{args.fix_prompt or "Use the default review-fix-loop fix prompt."}

Rules:
- Start a fresh fix-only pass for this repository.
- Read the review input file and fix only the selected P0/P1 issue.
- Keep the patch minimal and consistent with existing repo patterns.
- Add or update a regression test that would have caught the issue.
- Run relevant tests, broadening to the full suite when risk warrants it.
- Commit the fix and regression test together after tests pass.
- Do not push or open a PR unless explicitly instructed by the user.
- Write the fix result to the fix output file and update review-loop.md in the state directory.
- End the final response with exactly one marker line: FIX_LOOP_OUTCOME=FIXED, FIX_LOOP_OUTCOME=NOOP, or FIX_LOOP_OUTCOME=BLOCKED.
"""
        fix_text = run_codex(
            args.codex_bin,
            repo,
            state_dir,
            fix_prompt,
            fix_file,
            args.model,
            args.ask_for_approval,
            args.sandbox,
            args.dry_run,
        )
        fix_outcome = outcome(fix_text, "FIX_LOOP_OUTCOME")
        print(f"round {round_number} fix outcome={fix_outcome or 'UNKNOWN'}")
        if fix_outcome == "BLOCKED" or fix_outcome is None:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
