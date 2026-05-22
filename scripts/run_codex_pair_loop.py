#!/usr/bin/env python3
"""Run review/fix loop rounds as separate Codex exec sessions."""

from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import re
import shlex
import shutil
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


def default_codex_bin() -> str:
    env_path = os.environ.get("CODEX_BIN")
    if env_path:
        return env_path

    app_bundle = Path("/Applications/Codex.app/Contents/Resources/codex")
    if app_bundle.exists() and os.access(app_bundle, os.X_OK):
        return str(app_bundle)

    return shutil.which("codex") or "codex"


@lru_cache(maxsize=None)
def help_text(codex_bin: str, args: tuple[str, ...]) -> str:
    try:
        return subprocess.check_output(
            [codex_bin, *args, "--help"],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""


def supports_option(codex_bin: str, args: tuple[str, ...], option: str) -> bool:
    return option in help_text(codex_bin, args)


def warm_summary_instruction(
    context_file: Optional[Path], round_number: int, phase: str = "review"
) -> str:
    if not context_file:
        return "- No warm summary file is configured."
    if phase == "fix":
        return (
            f"- Read {context_file} if it exists before fixing, then update it with the fix summary, "
            "useful test commands, and any remaining P0/P1 risks."
        )
    if round_number <= 1:
        return (
            f"- Create or update {context_file} with a compact repo map, reviewed areas, "
            "useful test commands, selected findings, and unresolved risks."
        )
    return (
        f"- Read {context_file} before scanning. Reuse its repo map and prior decisions; "
        "focus on the previous diff, touched files, and unresolved P0/P1 risks before widening scope."
    )


def test_instruction(test_profile: str, is_final_round: bool) -> str:
    if test_profile == "full":
        return "- Run the full available validation suite after each fix, plus any focused regression test."
    if test_profile == "final-full":
        if is_final_round:
            return "- Run focused regression tests, then run the broadest practical validation suite for the final round."
        return "- Run focused regression tests for touched behavior; defer broad validation to the final round unless risk warrants it now."
    return "- Run the cheapest relevant tests for touched behavior; broaden only when shared contracts or high-risk paths changed."


def clean_review_test_instruction(test_profile: str, is_final_round: bool) -> str:
    if test_profile == "full":
        return "- When the outcome is CLEAN, run the full available validation suite."
    if test_profile == "final-full":
        if is_final_round:
            return "- When the outcome is CLEAN, run the broadest practical validation suite for the final round."
        return "- When the outcome is CLEAN, run only the cheapest relevant validation and leave broad validation for the final round."
    return "- When the outcome is CLEAN, run the cheapest relevant validation for the scoped workflow."


def build_review_prompt(
    round_number: int,
    max_rounds: int,
    runner_mode: str,
    max_findings: int,
    state_dir: Path,
    review_file: Path,
    review_prompt: str,
    prompt_profile: str,
    context_file: Optional[Path],
    test_profile: str,
    is_final_round: bool,
) -> str:
    if runner_mode == "batch":
        finding_word = "finding" if max_findings == 1 else "findings"
        finding_instruction = (
            f"- Find up to {max_findings} actionable P0/P1 {finding_word}, ordered by severity. "
            "Do not include P2/P3 backlog items."
        )
        outcome_instruction = "- If at least one actionable finding exists, write FOUND; otherwise write CLEAN."
    else:
        finding_instruction = "- If one exists, write exactly the single highest-severity finding."
        outcome_instruction = "- If no actionable P0/P1 issue exists, write CLEAN."
    write_scope = "the review output file and review-loop.md"
    if context_file:
        write_scope += ", plus the warm summary file"

    if prompt_profile == "skill":
        return f"""Use $review-fix-loop for REVIEW ONLY.

Round: {round_number}/{max_rounds}
Runner mode: {runner_mode}
State directory: {state_dir}
Review output file: {review_file}

Review prompt override:
{review_prompt}

Rules:
- Start a fresh review-only pass for this repository.
- Do not edit repository files and do not fix issues in this review session.
- Review only for actionable P0/P1 correctness, security, data integrity, and core workflow failures.
- Treat the review prompt override as the review boundary; widen only for direct P0/P1 blockers to that workflow.
{outcome_instruction}
{finding_instruction}
- Write the review result to the review output file and update review-loop.md in the state directory.
- End the final response with exactly one marker line: REVIEW_LOOP_OUTCOME=CLEAN, REVIEW_LOOP_OUTCOME=FOUND, or REVIEW_LOOP_OUTCOME=BLOCKED.
"""

    return f"""Repository review-only pass for a review/fix loop.

Round: {round_number}/{max_rounds}
Runner mode: {runner_mode}
State directory: {state_dir}
Review output file: {review_file}
Review focus:
{review_prompt}

Protocol:
- Read repository instructions such as AGENTS.md if present.
- Read {state_dir}/review-loop.md if it exists and avoid re-reporting issues already fixed, rejected, or marked non-P0/P1.
- Do not edit repository files and do not fix issues in this review session.
- You may write only {write_scope} in the state directory.
- Treat the Review focus as the review boundary; widen only for direct P0/P1 blockers to that workflow.
{warm_summary_instruction(context_file, round_number)}
- Review only for actionable P0/P1 correctness, security, data integrity, and core workflow failures.
- A valid P1 needs a concrete code path, clear trigger, serious user impact, file/line references, and why existing tests missed it.
{outcome_instruction}
{finding_instruction}
{clean_review_test_instruction(test_profile, is_final_round)}
- Write a concise Markdown result to the review output file and update review-loop.md in the state directory.
- End the final response with exactly one marker line: REVIEW_LOOP_OUTCOME=CLEAN, REVIEW_LOOP_OUTCOME=FOUND, or REVIEW_LOOP_OUTCOME=BLOCKED.
"""


def build_fix_prompt(
    round_number: int,
    max_rounds: int,
    runner_mode: str,
    state_dir: Path,
    review_file: Path,
    fix_file: Path,
    fix_prompt: str,
    prompt_profile: str,
    context_file: Optional[Path],
    test_profile: str,
    is_final_round: bool,
) -> str:
    effective_fix_prompt = fix_prompt or "Use the default review-fix-loop fix prompt."
    if runner_mode == "batch":
        fix_instruction = (
            "- Fix every selected P0/P1 finding in the review input that can be fixed safely in one cohesive patch. "
            "If batching would mix unrelated risky changes, fix the highest-severity coherent subset and record the rest as deferred."
        )
    else:
        fix_instruction = "- Read the review input file and fix only the selected P0/P1 issue."

    if prompt_profile == "skill":
        return f"""Use $review-fix-loop for FIX ONLY.

Round: {round_number}/{max_rounds}
Runner mode: {runner_mode}
State directory: {state_dir}
Review input file: {review_file}
Fix output file: {fix_file}

Fix prompt override:
{effective_fix_prompt}

Rules:
- Start a fresh fix-only pass for this repository.
{fix_instruction}
- Keep the patch minimal and consistent with existing repo patterns.
- Add or update a regression test that would have caught the issue.
{test_instruction(test_profile, is_final_round)}
- Commit the fix and regression test together after tests pass.
- Do not push or open a PR unless explicitly instructed by the user.
- Write the fix result to the fix output file and update review-loop.md in the state directory.
- End the final response with exactly one marker line: FIX_LOOP_OUTCOME=FIXED, FIX_LOOP_OUTCOME=NOOP, or FIX_LOOP_OUTCOME=BLOCKED.
"""

    return f"""Repository fix-only pass for a review/fix loop.

Round: {round_number}/{max_rounds}
Runner mode: {runner_mode}
State directory: {state_dir}
Review input file: {review_file}
Fix output file: {fix_file}
Fix focus:
{effective_fix_prompt}

Protocol:
- Read repository instructions such as AGENTS.md if present.
{warm_summary_instruction(context_file, round_number, "fix")}
{fix_instruction}
- Keep the patch minimal and consistent with existing repository patterns.
- Add or update a regression test that would have caught the issue.
{test_instruction(test_profile, is_final_round)}
- Commit the fix and regression test together after tests pass.
- Do not push or open a PR unless explicitly instructed by the user.
- Write a concise Markdown result to the fix output file and update review-loop.md in the state directory. Update the warm summary file when configured.
- End the final response with exactly one marker line: FIX_LOOP_OUTCOME=FIXED, FIX_LOOP_OUTCOME=NOOP, or FIX_LOOP_OUTCOME=BLOCKED.
"""


def build_codex_command(
    codex_bin: str,
    repo: Path,
    state_dir: Path,
    output_file: Path,
    model: Optional[str],
    approval: Optional[str],
    sandbox: Optional[str],
    ephemeral: bool,
    ignore_user_config: bool,
    prompt: str,
) -> list[str]:
    top_level_approval = approval and supports_option(codex_bin, (), "--ask-for-approval")
    exec_approval = approval and supports_option(codex_bin, ("exec",), "--ask-for-approval")

    cmd = [codex_bin]
    if top_level_approval and not exec_approval:
        cmd.extend(["--ask-for-approval", approval])

    cmd.extend(
        [
            "exec",
            "-C",
            str(repo),
            "--add-dir",
            str(state_dir),
            "--output-last-message",
            str(output_file),
        ]
    )
    if ephemeral and supports_option(codex_bin, ("exec",), "--ephemeral"):
        cmd.append("--ephemeral")
    if ignore_user_config and supports_option(codex_bin, ("exec",), "--ignore-user-config"):
        cmd.append("--ignore-user-config")
    if exec_approval:
        cmd.extend(["--ask-for-approval", approval])
    if model:
        cmd.extend(["--model", model])
    if sandbox:
        cmd.extend(["--sandbox", sandbox])
    cmd.append(prompt)
    return cmd


def run_codex(
    codex_bin: str,
    repo: Path,
    state_dir: Path,
    prompt: str,
    output_file: Path,
    model: Optional[str],
    approval: Optional[str],
    sandbox: Optional[str],
    ephemeral: bool,
    ignore_user_config: bool,
    dry_run: bool,
) -> str:
    cmd = build_codex_command(
        codex_bin,
        repo,
        state_dir,
        output_file,
        model,
        approval,
        sandbox,
        ephemeral,
        ignore_user_config,
        prompt,
    )

    if dry_run:
        print("DRY RUN:", shlex.join(cmd))
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
        description="Run review/fix loop rounds as lightweight Codex exec sessions."
    )
    parser.add_argument("--repo", default=".", help="Repository root to review.")
    parser.add_argument(
        "--max-rounds",
        type=int,
        required=True,
        help="Maximum review/fix pairs in paired mode; maximum findings in batch mode.",
    )
    parser.add_argument("--review-prompt", required=True, help="Review prompt override.")
    parser.add_argument("--fix-prompt", default="", help="Fix prompt override.")
    parser.add_argument("--state-dir", help="State directory. Defaults to tmp.")
    parser.add_argument(
        "--codex-bin",
        default=default_codex_bin(),
        help="Codex executable. Defaults to CODEX_BIN, then the Codex.app bundled binary, then PATH.",
    )
    parser.add_argument("--model", help="Model to pass to codex exec.")
    parser.add_argument("--ask-for-approval", default="never", help="Approval policy.")
    parser.add_argument("--sandbox", default="workspace-write", help="Sandbox mode.")
    parser.add_argument(
        "--runner-mode",
        choices=("paired", "batch"),
        default="paired",
        help="paired runs one review/fix pair per round; batch runs one review and one fix session total.",
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        help="Maximum findings for batch mode. Defaults to --max-rounds.",
    )
    parser.add_argument(
        "--test-profile",
        choices=("focused", "final-full", "full"),
        default="focused",
        help="Verification guidance for fix sessions.",
    )
    parser.add_argument(
        "--no-warm-summary",
        dest="warm_summary",
        action="store_false",
        help="Disable loop-context.md reuse between child sessions.",
    )
    parser.add_argument(
        "--prompt-profile",
        choices=("light", "skill"),
        default="light",
        help="Use concise built-in prompts by default, or load the full skill in child sessions.",
    )
    parser.add_argument(
        "--persist-sessions",
        action="store_true",
        help="Do not pass --ephemeral to child codex exec sessions.",
    )
    parser.add_argument(
        "--ignore-user-config",
        action="store_true",
        help="Pass --ignore-user-config to child codex exec sessions when supported.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them.")
    parser.set_defaults(warm_summary=True)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if args.max_rounds < 1:
        parser.error("--max-rounds must be positive")
    if args.max_findings is not None and args.max_findings < 1:
        parser.error("--max-findings must be positive")
    if args.runner_mode == "batch" and args.prompt_profile == "skill":
        parser.error("--runner-mode batch requires --prompt-profile light")

    state_dir = Path(args.state_dir).resolve() if args.state_dir else default_state_dir(repo)
    state_dir.mkdir(parents=True, exist_ok=True)
    context_file = state_dir / "loop-context.md" if args.warm_summary else None
    max_findings = args.max_findings or args.max_rounds

    print(f"repo={repo}")
    print(f"state_dir={state_dir}")
    print(f"max_rounds={args.max_rounds}")
    print(f"runner_mode={args.runner_mode}")
    print(f"max_findings={max_findings}")
    print(f"test_profile={args.test_profile}")
    print(f"warm_summary={args.warm_summary}")
    print(f"prompt_profile={args.prompt_profile}")
    print(f"ephemeral_sessions={not args.persist_sessions}")

    if args.runner_mode == "batch":
        review_file = state_dir / "batch-review.md"
        fix_file = state_dir / "batch-fix.md"
        review_prompt = build_review_prompt(
            1,
            args.max_rounds,
            args.runner_mode,
            max_findings,
            state_dir,
            review_file,
            args.review_prompt,
            args.prompt_profile,
            context_file,
            args.test_profile,
            True,
        )
        review_text = run_codex(
            args.codex_bin,
            repo,
            state_dir,
            review_prompt,
            review_file,
            args.model,
            args.ask_for_approval,
            args.sandbox,
            not args.persist_sessions,
            args.ignore_user_config,
            args.dry_run,
        )
        review_outcome = outcome(review_text, "REVIEW_LOOP_OUTCOME")
        print(f"batch review outcome={review_outcome or 'UNKNOWN'}")
        if review_outcome in {"CLEAN", "BLOCKED"}:
            return 0 if review_outcome == "CLEAN" else 1
        if review_outcome != "FOUND":
            print("Review session did not emit a valid outcome marker.", file=sys.stderr)
            return 1

        fix_prompt = build_fix_prompt(
            1,
            args.max_rounds,
            args.runner_mode,
            state_dir,
            review_file,
            fix_file,
            args.fix_prompt,
            args.prompt_profile,
            context_file,
            args.test_profile,
            True,
        )
        fix_text = run_codex(
            args.codex_bin,
            repo,
            state_dir,
            fix_prompt,
            fix_file,
            args.model,
            args.ask_for_approval,
            args.sandbox,
            not args.persist_sessions,
            args.ignore_user_config,
            args.dry_run,
        )
        fix_outcome = outcome(fix_text, "FIX_LOOP_OUTCOME")
        print(f"batch fix outcome={fix_outcome or 'UNKNOWN'}")
        return 1 if fix_outcome == "BLOCKED" or fix_outcome is None else 0

    for round_number in range(1, args.max_rounds + 1):
        review_file = state_dir / f"round-{round_number}-review.md"
        fix_file = state_dir / f"round-{round_number}-fix.md"

        review_prompt = build_review_prompt(
            round_number,
            args.max_rounds,
            args.runner_mode,
            1,
            state_dir,
            review_file,
            args.review_prompt,
            args.prompt_profile,
            context_file,
            args.test_profile,
            round_number == args.max_rounds,
        )
        review_text = run_codex(
            args.codex_bin,
            repo,
            state_dir,
            review_prompt,
            review_file,
            args.model,
            args.ask_for_approval,
            args.sandbox,
            not args.persist_sessions,
            args.ignore_user_config,
            args.dry_run,
        )
        review_outcome = outcome(review_text, "REVIEW_LOOP_OUTCOME")
        print(f"round {round_number} review outcome={review_outcome or 'UNKNOWN'}")
        if review_outcome in {"CLEAN", "BLOCKED"}:
            return 0 if review_outcome == "CLEAN" else 1
        if review_outcome != "FOUND":
            print("Review session did not emit a valid outcome marker.", file=sys.stderr)
            return 1

        fix_prompt = build_fix_prompt(
            round_number,
            args.max_rounds,
            args.runner_mode,
            state_dir,
            review_file,
            fix_file,
            args.fix_prompt,
            args.prompt_profile,
            context_file,
            args.test_profile,
            round_number == args.max_rounds,
        )
        fix_text = run_codex(
            args.codex_bin,
            repo,
            state_dir,
            fix_prompt,
            fix_file,
            args.model,
            args.ask_for_approval,
            args.sandbox,
            not args.persist_sessions,
            args.ignore_user_config,
            args.dry_run,
        )
        fix_outcome = outcome(fix_text, "FIX_LOOP_OUTCOME")
        print(f"round {round_number} fix outcome={fix_outcome or 'UNKNOWN'}")
        if fix_outcome == "BLOCKED" or fix_outcome is None:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
