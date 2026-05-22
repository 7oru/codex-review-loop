import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_codex_pair_loop.py"

spec = importlib.util.spec_from_file_location("run_codex_pair_loop", SCRIPT)
runner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runner)


class RunCodexPairLoopTests(unittest.TestCase):
    def test_build_codex_command_places_approval_at_supported_level(self) -> None:
        def fake_supports(_codex_bin: str, args: tuple[str, ...], option: str) -> bool:
            supported = {
                ((), "--ask-for-approval"),
                (("exec",), "--ephemeral"),
                (("exec",), "--ignore-user-config"),
            }
            return (args, option) in supported

        with patch.object(runner, "supports_option", side_effect=fake_supports):
            cmd = runner.build_codex_command(
                "codex",
                Path("/repo"),
                Path("/state"),
                Path("/state/out.md"),
                "gpt-test",
                "never",
                "workspace-write",
                True,
                True,
                "hello",
            )

        self.assertEqual(cmd[:3], ["codex", "--ask-for-approval", "never"])
        self.assertEqual(cmd.count("--ask-for-approval"), 1)
        self.assertIn("--ephemeral", cmd)
        self.assertIn("--ignore-user-config", cmd)
        self.assertEqual(cmd[-1], "hello")

    def test_build_codex_command_places_exec_approval_when_supported(self) -> None:
        def fake_supports(_codex_bin: str, args: tuple[str, ...], option: str) -> bool:
            return (args, option) == (("exec",), "--ask-for-approval")

        with patch.object(runner, "supports_option", side_effect=fake_supports):
            cmd = runner.build_codex_command(
                "codex",
                Path("/repo"),
                Path("/state"),
                Path("/state/out.md"),
                None,
                "on-request",
                None,
                True,
                True,
                "hello",
            )

        self.assertEqual(cmd[0:2], ["codex", "exec"])
        self.assertIn("--ask-for-approval", cmd)
        self.assertGreater(cmd.index("--ask-for-approval"), cmd.index("exec"))

    def test_batch_review_prompt_limits_findings_and_reuses_context(self) -> None:
        prompt = runner.build_review_prompt(
            1,
            3,
            "batch",
            3,
            Path("/state"),
            Path("/state/batch-review.md"),
            "local one-click install/run path only",
            "light",
            Path("/state/loop-context.md"),
            "focused",
            True,
        )

        self.assertIn("Runner mode: batch", prompt)
        self.assertIn("Find up to 3 actionable P0/P1 findings", prompt)
        self.assertIn("Treat the Review focus as the review boundary", prompt)
        self.assertIn("loop-context.md", prompt)
        self.assertIn("cheapest relevant validation", prompt)

    def test_paired_later_round_prompt_uses_warm_summary(self) -> None:
        prompt = runner.build_review_prompt(
            2,
            3,
            "paired",
            1,
            Path("/state"),
            Path("/state/round-2-review.md"),
            "review core workflow",
            "light",
            Path("/state/loop-context.md"),
            "final-full",
            False,
        )

        self.assertIn("Read /state/loop-context.md before scanning", prompt)
        self.assertIn("single highest-severity finding", prompt)
        self.assertIn("leave broad validation for the final round", prompt)


if __name__ == "__main__":
    unittest.main()
