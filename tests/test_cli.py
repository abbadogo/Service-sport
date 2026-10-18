import contextlib
import io
import unittest

from service.__main__ import main


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def test_rejects_zero_and_negative_minutes(self):
        for bad in ("0", "-3"):
            code, _, err = run("--minutes", bad)
            self.assertEqual(code, 2)
            self.assertIn("duration", err)

    def test_non_numeric_minutes_is_an_argparse_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            main(["--minutes", "abc"])
        self.assertEqual(ctx.exception.code, 2)

    def test_over_cap_is_clamped_and_reported(self):
        code, out, _ = run("--minutes", "99", "--max-sim-seconds", "5")
        self.assertEqual(code, 0)
        self.assertIn("clamped", out)
        self.assertIn("ABORTED", out)

    def test_bad_safety_limit_is_reported_not_raised(self):
        code, _, err = run("--max-sim-seconds", "0")
        self.assertEqual(code, 2)
        self.assertIn("max_sim_seconds", err)


if __name__ == "__main__":
    unittest.main()
