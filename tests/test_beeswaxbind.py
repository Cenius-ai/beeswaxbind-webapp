"""Smoke and table-driven tests for BeeswaxBind.

Run with either:
    python -m unittest discover -s tests
    pytest
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "beeswaxbind.py"
sys.path.insert(0, str(ROOT))

import beeswaxbind as bb  # noqa: E402  (path set up above)


def run_cli(*args, stdin=None, cwd=None):
    """Run the delivered CLI exactly as a user would."""
    return subprocess.run(
        [sys.executable, str(ENTRY)] + list(args),
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(cwd or ROOT),
    )


class CLITestCase(unittest.TestCase):
    def assertNoTraceback(self, result):
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("Traceback", result.stdout)

    def assertOk(self, result):
        self.assertNoTraceback(result)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return result.stdout

    def assertUsageError(self, result):
        self.assertNoTraceback(result)
        self.assertEqual(result.returncode, 2, msg=result.stdout + result.stderr)
        return result.stderr


# ---------------------------------------------------------------------------
# F1 needle and thread recommender
# ---------------------------------------------------------------------------


class TestNeedleRecommender(CLITestCase):
    def test_recommends_primary_and_alternate_needles(self):
        out = self.assertOk(run_cli("needle", "--thread", "18/3", "--leather", "4oz"))
        self.assertIn("18/3", out)
        self.assertIn("4 oz", out)
        self.assertIn("primary", out)
        self.assertIn("alternate", out)
        self.assertIn("1.40 mm", out)
        self.assertIn("US 3", out)
        self.assertIn("1.20 mm", out)
        self.assertIn("US 4", out)

    def test_rationale_names_thread_and_leather(self):
        out = self.assertOk(run_cli("needle", "--thread", "18/3", "--leather", "4oz"))
        rationale = [line for line in out.splitlines() if line.strip().startswith("why")][0]
        self.assertIn("18/3", rationale)
        self.assertIn("4 oz", rationale)
        self.assertIn("1.40 mm", rationale)

    def test_millimetre_leather_shows_ounce_equivalent(self):
        out = self.assertOk(run_cli("needle", "--thread", "18/3", "--leather", "2mm"))
        self.assertIn("2 mm", out)
        self.assertIn("5 oz", out)

    def test_default_leather_is_stated_on_stdout(self):
        out = self.assertOk(run_cli("needle", "--thread", "18/3"))
        self.assertIn("4 oz leather assumed", out)

    def test_unknown_thread_lists_known_numbers(self):
        result = run_cli("needle", "--thread", "99/9")
        err = self.assertUsageError(result)
        self.assertIn("unknown thread number '99/9'", err)
        self.assertIn("known thread numbers are", err)
        self.assertIn("18/3, 18/4, 25/3", err)
        self.assertEqual(result.stdout, "")

    def test_no_flags_without_a_terminal_explains_the_flag(self):
        result = run_cli("needle", stdin="")
        err = self.assertUsageError(result)
        self.assertIn("--thread", err)
        self.assertIn("beeswaxbind needle --thread 18/3", err)

    def test_every_bundled_thread_gets_a_recommendation(self):
        for thread in bb.THREADS:
            with self.subTest(thread=thread.number):
                out = self.assertOk(run_cli("needle", "--thread", thread.number))
                self.assertIn(thread.number, out)
                self.assertIn("harness needle", out)

    def test_every_thread_has_two_needles_to_choose_from(self):
        for thread in bb.THREADS:
            with self.subTest(thread=thread.number):
                primary, alternate = bb.pick_needles(thread, 4.0)
                self.assertIsNotNone(alternate)
                self.assertIn(thread.number, primary.fits_threads)
                self.assertIn(thread.number, alternate.fits_threads)
                self.assertNotEqual(primary.name, alternate.name)


# ---------------------------------------------------------------------------
# F2 stitch tension calculator
# ---------------------------------------------------------------------------


class TestTensionCalculator(CLITestCase):
    def test_spi_becomes_a_stitch_length(self):
        out = self.assertOk(run_cli("tension", "--spi", "6"))
        self.assertIn("6.00 spi", out)
        self.assertIn("4.23 mm", out)
        self.assertIn("0.17 in", out)
        self.assertIn("thread 18/3 and 4 oz leather assumed", out)

    def test_length_becomes_a_stitch_density(self):
        out = self.assertOk(run_cli("tension", "--length", "4mm"))
        self.assertIn("6.35 spi", out)
        self.assertIn("4.00 mm", out)
        self.assertIn("0.16 in", out)

    def test_millimetre_and_inch_values_agree(self):
        report = bb.build_tension_report(6.0, bb.THREAD_BY_NUMBER["18/3"], bb.parse_leather("4oz"), "both", [])
        self.assertAlmostEqual(report.length_mm / bb.MM_PER_INCH, report.length_in, places=6)
        self.assertAlmostEqual(report.length_mm, 4.2333, places=3)

    def test_verdict_line_and_reason(self):
        out = self.assertOk(run_cli("tension", "--spi", "6", "--thread", "18/3", "--leather", "4oz"))
        verdict_lines = [line for line in out.splitlines() if line.strip().startswith("verdict")]
        self.assertEqual(len(verdict_lines), 1)
        self.assertIn(verdict_lines[0].split()[-1], ("tight", "standard", "loose"))
        reason = [line for line in out.splitlines() if line.strip().startswith("reason")][0]
        self.assertIn("18/3", reason)
        self.assertIn("harness needle", reason)

    def test_standard_tension_on_default_leather(self):
        out = self.assertOk(run_cli("tension", "--spi", "6", "--leather", "4oz"))
        verdict = [line for line in out.splitlines() if line.strip().startswith("verdict")][0]
        self.assertEqual(verdict.split()[-1], "standard")

    def test_two_inputs_are_rejected(self):
        err = self.assertUsageError(run_cli("tension", "--spi", "6", "--length", "4mm"))
        self.assertIn("not both", err)

    def test_no_input_flags_asks_for_one(self):
        err = self.assertUsageError(run_cli("tension", stdin=""))
        self.assertIn("--spi", err)
        self.assertIn("--length", err)
        self.assertIn("beeswaxbind tension --spi 6", err)

    def test_zero_spi_is_rejected(self):
        err = self.assertUsageError(run_cli("tension", "--spi", "0"))
        self.assertIn("spi must be greater than 0", err)

    def test_unparseable_spi_is_rejected(self):
        err = self.assertUsageError(run_cli("tension", "--spi", "abc"))
        self.assertIn("spi must be a number such as 6", err)

    def test_boundary_densities(self):
        for spi, expected in [("1", "loose"), ("6", "standard"), ("20", "tight")]:
            with self.subTest(spi=spi):
                out = self.assertOk(run_cli("tension", "--spi", spi))
                verdict = [line for line in out.splitlines() if line.strip().startswith("verdict")][0]
                self.assertEqual(verdict.split()[-1], expected)

    def test_boundary_leather_weights(self):
        for leather in ("2oz", "20oz"):
            with self.subTest(leather=leather):
                out = self.assertOk(run_cli("tension", "--spi", "3", "--leather", leather))
                self.assertIn("spi", out)

    def test_verdict_follows_the_leather_band(self):
        heavy = self.assertOk(run_cli("tension", "--spi", "4", "--leather", "18oz"))
        verdict = [line for line in heavy.splitlines() if line.strip().startswith("verdict")][0]
        self.assertEqual(verdict.split()[-1], "standard")


# ---------------------------------------------------------------------------
# F3 wax blend ratio helper
# ---------------------------------------------------------------------------


class TestWaxBlend(CLITestCase):
    def test_gram_batch_scales_both_components(self):
        out = self.assertOk(run_cli("wax", "--parts", "5:1", "--batch", "100g"))
        self.assertIn("5:1", out)
        self.assertIn("83.3 g", out)
        self.assertIn("16.7 g", out)
        self.assertIn("83%", out)
        self.assertIn("17%", out)
        self.assertIn("oz", out)

    def test_ounce_batch_scales_both_components(self):
        out = self.assertOk(run_cli("wax", "--parts", "5:1", "--batch", "2oz"))
        self.assertIn("47.2 g", out)
        self.assertIn("9.4 g", out)
        self.assertIn("1.67 oz", out)
        self.assertIn("0.33 oz", out)

    def test_default_batch_is_fifty_grams(self):
        out = self.assertOk(run_cli("wax", "--parts", "5:1"))
        self.assertIn("50 g batch assumed", out)
        self.assertIn("41.7 g", out)
        self.assertIn("8.3 g", out)

    def test_preset_prints_name_ratio_and_weights(self):
        out = self.assertOk(run_cli("wax", "--preset", "soft"))
        self.assertIn("5:1", out)
        self.assertIn("41.7 g", out)
        self.assertIn("8.3 g", out)
        self.assertIn("everyday hand sewing", out)

    def test_boundary_one_gram_batch(self):
        out = self.assertOk(run_cli("wax", "--parts", "1:1", "--batch", "1g"))
        self.assertIn("0.5 g", out)
        self.assertIn("50%", out)

    def test_every_preset_scales(self):
        for recipe in bb.WAX_RECIPES:
            with self.subTest(preset=recipe.preset):
                out = self.assertOk(run_cli("wax", "--preset", recipe.preset, "--batch", "100g"))
                self.assertIn(recipe.ratio_label, out)
                total = float(recipe.beeswax_parts) + float(recipe.rosin_parts)
                expected = 100.0 * float(recipe.beeswax_parts) / total
                self.assertIn(bb.fmt_g(expected), out)

    def test_zero_parts_is_rejected(self):
        err = self.assertUsageError(run_cli("wax", "--parts", "5:0"))
        self.assertIn("both beeswax and rosin parts must be greater than zero", err)

    def test_negative_batch_is_rejected(self):
        err = self.assertUsageError(run_cli("wax", "--batch", "-5"))
        self.assertIn("batch weight must be greater than zero", err)

    def test_non_numeric_batch_is_rejected(self):
        err = self.assertUsageError(run_cli("wax", "--batch", "abc"))
        self.assertIn("batch weight must be a positive number such as 50 or 50g", err)

    def test_unknown_preset_is_rejected(self):
        err = self.assertUsageError(run_cli("wax", "--preset", "candle"))
        self.assertIn("unknown preset 'candle'", err)

    def test_no_input_flags_asks_for_one(self):
        err = self.assertUsageError(run_cli("wax", stdin=""))
        self.assertIn("--parts", err)
        self.assertIn("--preset", err)

    def test_blend_percentages_sum_to_one_hundred(self):
        for parts in ("5:1", "4:1", "3:1", "2:1", "8:1", "7:2"):
            with self.subTest(parts=parts):
                report = json.loads(self.assertOk(run_cli("wax", "--parts", parts, "--json")))
                self.assertEqual(report["beeswax_pct"] + report["rosin_pct"], 100)
                self.assertAlmostEqual(
                    report["beeswax_grams"] + report["rosin_grams"], report["batch_grams"], delta=0.1
                )


# ---------------------------------------------------------------------------
# F5 bundled reference tables and search
# ---------------------------------------------------------------------------


class TestReferenceTables(CLITestCase):
    def test_thread_table_lists_at_least_ten_threads(self):
        out = self.assertOk(run_cli("reference", "--show", "threads"))
        for thread in bb.THREADS:
            with self.subTest(thread=thread.number):
                self.assertIn(thread.number, out)
        self.assertGreaterEqual(len(bb.THREADS), 10)
        for number in ("18/4", "25/3"):
            self.assertIn(number, out)

    def test_thread_rows_carry_diameter_and_strength(self):
        out = self.assertOk(run_cli("reference", "--show", "threads"))
        row = [line for line in out.splitlines() if line.startswith("18/3")][0]
        self.assertIn("0.65 mm", row)
        self.assertIn("15 lb", row)
        self.assertIn("6.8 kg", row)

    def test_needle_table_shows_metric_and_us(self):
        out = self.assertOk(run_cli("reference", "--show", "needles"))
        self.assertGreaterEqual(len(bb.NEEDLES), 10)
        for needle in bb.NEEDLES:
            with self.subTest(needle=needle.name):
                row = [line for line in out.splitlines() if line.startswith(needle.name)][0]
                self.assertIn("%.2f mm" % needle.metric_mm, row)
                self.assertIn(needle.us_size, row)
                self.assertIn(needle.fits_threads[0], row)

    def test_wax_table_lists_presets_with_ratios(self):
        out = self.assertOk(run_cli("reference", "--show", "wax"))
        self.assertGreaterEqual(len(bb.WAX_RECIPES), 5)
        for recipe in bb.WAX_RECIPES:
            with self.subTest(preset=recipe.preset):
                row = [line for line in out.splitlines() if line.startswith(recipe.preset)][0]
                self.assertIn(recipe.ratio_label, row)

    def test_bare_reference_prints_every_table(self):
        out = self.assertOk(run_cli("reference"))
        for name in ("threads", "needles", "wax"):
            self.assertIn(name, out)

    def test_search_finds_thread_and_fitting_needles(self):
        out = self.assertOk(run_cli("reference", "--search", "18/3"))
        self.assertIn("18/3", out)
        thread_rows = [line for line in out.splitlines() if line.startswith("18/")]
        self.assertEqual(thread_rows, [line for line in thread_rows if line.startswith("18/3")])
        needles = bb.needles_for_thread("18/3")
        for needle in needles:
            self.assertIn(needle.name, out)

    def test_search_with_no_match_exits_zero_with_a_hint(self):
        result = run_cli("reference", "--search", "zzz")
        out = self.assertOk(result)
        self.assertIn("no reference rows match", out)
        for name in ("threads", "needles", "wax"):
            self.assertIn(name, out)

    def test_unknown_table_is_rejected(self):
        err = self.assertUsageError(run_cli("reference", "--show", "bogus"))
        self.assertIn("valid tables are threads, needles, wax", err)

    def test_imperial_reference_hides_the_metric_column(self):
        out = self.assertOk(run_cli("reference", "--show", "needles", "--units", "imperial"))
        self.assertNotIn("metric mm", out)
        self.assertIn("US size", out)
        self.assertIn("in", out)

    def test_metric_reference_hides_the_us_column(self):
        out = self.assertOk(run_cli("reference", "--show", "needles", "--units", "metric"))
        self.assertNotIn("US size", out)

    def test_breaking_strength_pounds_and_kilos_agree(self):
        for thread in bb.THREADS:
            with self.subTest(thread=thread.number):
                self.assertAlmostEqual(thread.breaking_kg, thread.breaking_lb * 0.4536, delta=0.06)


# ---------------------------------------------------------------------------
# F7 aligned text and --json
# ---------------------------------------------------------------------------


class TestUnitsAndFormatting(CLITestCase):
    def test_metric_hides_us_sizes(self):
        out = self.assertOk(run_cli("needle", "--thread", "18/3", "--units", "metric"))
        self.assertNotIn("US", out)
        self.assertIn("1.40 mm", out)

    def test_imperial_hides_metric_sizes(self):
        out = self.assertOk(run_cli("needle", "--thread", "18/3", "--units", "imperial"))
        self.assertIn("US 3", out)
        self.assertIn("in", out)
        self.assertNotIn(" mm", out)

    def test_both_units_are_the_default(self):
        out = self.assertOk(run_cli("needle", "--thread", "18/3"))
        self.assertIn("1.40 mm", out)
        self.assertIn("US 3", out)

    def test_unknown_units_are_rejected(self):
        err = self.assertUsageError(run_cli("tension", "--spi", "6", "--units", "furlongs"))
        self.assertIn("units must be metric, imperial or both", err)
        err = self.assertUsageError(run_cli("needle", "--thread", "18/3", "--units", "furlongs"))
        self.assertIn("units must be metric, imperial or both", err)

    def test_output_is_labelled_aligned_and_free_of_escapes(self):
        out = self.assertOk(run_cli("wax", "--parts", "4:1", "--batch", "80g"))
        self.assertNotIn("\x1b", out)
        labelled = [line for line in out.splitlines() if line.startswith("  ") and " " in line.strip()]
        self.assertGreaterEqual(len(labelled), 3)
        self.assertTrue(any(line.strip().startswith("beeswax") for line in out.splitlines()))

    def test_colour_is_opt_in_and_never_reaches_a_pipe(self):
        quoted = self.assertOk(run_cli("needle", "--thread", "18/3", "--color", "always"))
        self.assertIn("\x1b[", quoted)
        self.assertIn("primary", quoted)
        never = self.assertOk(run_cli("needle", "--thread", "18/3", "--color", "never"))
        self.assertNotIn("\x1b", never)
        piped = self.assertOk(run_cli("needle", "--thread", "18/3"))
        self.assertNotIn("\x1b", piped)

    def test_unknown_colour_choice_is_rejected(self):
        err = self.assertUsageError(run_cli("needle", "--thread", "18/3", "--color", "rainbow"))
        self.assertIn("--help", err)

    def test_no_escape_sequences_anywhere(self):
        for args in (
            ("needle", "--thread", "18/3"),
            ("tension", "--spi", "6"),
            ("wax", "--parts", "5:1"),
            ("reference", "--show", "threads"),
        ):
            with self.subTest(args=args):
                self.assertNotIn("\x1b", self.assertOk(run_cli(*args)))


class TestJsonOutput(CLITestCase):
    def test_wax_json_has_the_documented_keys(self):
        payload = json.loads(self.assertOk(run_cli("wax", "--parts", "4:1", "--batch", "50", "--json")))
        for key in ("ratio", "beeswax_grams", "rosin_grams", "beeswax_oz", "rosin_oz",
                    "beeswax_pct", "rosin_pct", "units"):
            self.assertIn(key, payload)
        self.assertEqual(payload["ratio"], "4:1")
        self.assertEqual(payload["beeswax_pct"], 80)
        self.assertEqual(payload["rosin_pct"], 20)
        self.assertEqual(payload["units"], "both")

    def test_needle_json_has_inputs_needle_alternate_rationale_and_assumptions(self):
        payload = json.loads(self.assertOk(run_cli("needle", "--thread", "18/3", "--json")))
        for key in ("inputs", "needle", "alternate", "rationale", "assumptions"):
            self.assertIn(key, payload)
        self.assertEqual(payload["inputs"]["thread"], "18/3")
        self.assertEqual(payload["needle"]["metric_mm"], 1.4)
        self.assertEqual(payload["needle"]["us_size"], "3")
        self.assertIn("18/3", payload["rationale"])
        self.assertEqual(payload["alternate"]["metric_mm"], 1.2)

    def test_tension_json_reports_the_verdict(self):
        payload = json.loads(self.assertOk(run_cli("tension", "--spi", "6", "--json")))
        self.assertEqual(payload["result"]["verdict"], "standard")
        self.assertAlmostEqual(payload["result"]["stitch_length_mm"], 4.23, places=2)
        self.assertAlmostEqual(payload["result"]["stitch_length_in"], 0.17, places=2)

    def test_json_output_is_a_single_object(self):
        out = self.assertOk(run_cli("reference", "--show", "wax", "--json"))
        payload = json.loads(out)
        self.assertEqual(payload["show"], "wax")
        self.assertIn("wax", payload["results"])
        self.assertEqual(len(payload["results"]["wax"]), len(bb.WAX_RECIPES))

    def test_bad_input_in_json_mode_writes_a_json_error(self):
        result = run_cli("tension", "--spi", "abc", "--json")
        self.assertNoTraceback(result)
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stderr)
        self.assertIn("error", payload)
        self.assertEqual(result.stdout, "")

    def test_json_error_on_an_unknown_command(self):
        result = run_cli("bogus", "--json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error", json.loads(result.stderr))


# ---------------------------------------------------------------------------
# F4 interactive wizard
# ---------------------------------------------------------------------------


class TestInteractiveWizard(CLITestCase):
    def test_wizard_matches_the_flag_driven_command(self):
        expected = self.assertOk(run_cli("needle", "--thread", "18/3", "--leather", "4oz"))
        transcript = self.assertOk(run_cli(stdin="1\n18/3\n4oz\nq\n"))
        self.assertIn(expected.strip(), transcript)
        self.assertIn("press Enter to run another calculation, q to quit", transcript)

    def test_wizard_reasks_after_an_invalid_answer(self):
        transcript = self.assertOk(run_cli(stdin="1\nbanana\n18/3\n4oz\nq\n"))
        self.assertIn("banana", transcript)
        self.assertIn("unknown thread number", transcript)
        self.assertIn("harness needle", transcript)

    def test_wizard_runs_the_wax_calculator(self):
        transcript = self.assertOk(run_cli(stdin="3\n5:1\n100g\nq\n"))
        self.assertIn("83.3 g", transcript)

    def test_wizard_runs_the_tension_calculator(self):
        transcript = self.assertOk(run_cli(stdin="2\n6\n\n\nq\n"))
        self.assertIn("4.23 mm", transcript)

    def test_wizard_exits_two_and_explains_itself_without_a_terminal(self):
        result = run_cli(stdin="")
        self.assertNoTraceback(result)
        self.assertEqual(result.returncode, 2)
        for name in ("needle", "tension", "wax"):
            self.assertIn(name, result.stdout)
        self.assertIn("--help", result.stdout)

    def test_missing_stdin_is_handled_without_a_traceback(self):
        saved = sys.stdin
        sys.stdin = None
        try:
            self.assertIsNone(bb._stdin_reader())
        finally:
            sys.stdin = saved

    def test_end_of_input_exits_cleanly(self):
        result = run_cli(stdin="1\n18/3\n4oz\n")
        self.assertNoTraceback(result)
        self.assertEqual(result.returncode, 0)

    def test_quit_choice_exits_zero(self):
        result = run_cli(stdin="q\n")
        self.assertNoTraceback(result)
        self.assertEqual(result.returncode, 0)


# ---------------------------------------------------------------------------
# CLI contract: help, exit codes, side effects
# ---------------------------------------------------------------------------


class TestCommandLineContract(CLITestCase):
    def test_help_lists_every_calculator(self):
        out = self.assertOk(run_cli("--help"))
        for name in ("needle", "tension", "wax", "reference"):
            self.assertIn(name, out)
        self.assertIn("--units", out)

    def test_subcommand_help(self):
        for name in ("needle", "tension", "wax", "reference"):
            with self.subTest(command=name):
                out = self.assertOk(run_cli(name, "--help"))
                self.assertIn("BeeswaxBind", out)

    def test_version(self):
        out = self.assertOk(run_cli("--version"))
        self.assertIn("beeswaxbind 1.0.0", out)

    def test_unknown_command_reports_and_exits_two(self):
        result = run_cli("bogus")
        err = self.assertUsageError(result)
        self.assertIn("unknown command: bogus", err)
        self.assertIn("--help", err)

    def test_unknown_flag_reports_and_exits_two(self):
        err = self.assertUsageError(run_cli("needle", "--threads", "18/3"))
        self.assertIn("--help", err)

    def test_results_go_to_stdout_and_errors_to_stderr(self):
        good = run_cli("tension", "--spi", "6")
        self.assertEqual(good.stderr, "")
        bad = run_cli("tension", "--spi", "0")
        self.assertEqual(bad.stdout, "")

    def test_identical_inputs_give_identical_output(self):
        first = self.assertOk(run_cli("needle", "--thread", "25/3", "--leather", "6oz"))
        second = self.assertOk(run_cli("needle", "--thread", "25/3", "--leather", "6oz"))
        self.assertEqual(first, second)

    def test_closed_stdout_is_handled_without_a_traceback(self):
        shell = shutil.which("bash")
        if shell is None:
            self.skipTest("bash is not available for this check")
        env = dict(os.environ, PY=sys.executable, ENTRY=str(ENTRY))
        result = subprocess.run(
            [shell, "-c", 'exec "$PY" "$ENTRY" needle --thread 18/3 1>&-'],
            capture_output=True, text=True, env=env, cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_nothing_is_written_to_disk(self):
        with tempfile.TemporaryDirectory() as workdir:
            for args in (
                ("needle", "--thread", "18/3"),
                ("tension", "--spi", "6"),
                ("wax", "--parts", "5:1"),
                ("reference", "--show", "wax"),
            ):
                self.assertOk(run_cli(*args, cwd=workdir))
            self.assertEqual(list(Path(workdir).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
