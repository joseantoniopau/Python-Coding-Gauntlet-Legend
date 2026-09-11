"""The sandbox is the only part of this program that runs untrusted code."""
from base import GameTest  # noqa: E402
import unittest


class TestSandbox(GameTest):
    def test_network_is_blocked(self):
        from gauntlet import sandbox
        check = sandbox.self_check()
        self.assertTrue(check["network_blocked"],
                        "player code must not be able to reach the network")

    def test_infinite_loop_is_stopped(self):
        from gauntlet import sandbox
        check = sandbox.self_check()
        self.assertTrue(check["timeout_enforced"])

    def test_syntax_error_reports_player_line_numbers(self):
        from gauntlet import sandbox
        report = sandbox.run_tests("def f(:\n    pass\n",
                                   {"kind": "function", "name": "f"}, [])
        self.assertEqual(report.phase, "syntax")
        self.assertEqual(report.error["type"], "SyntaxError")
        self.assertEqual(report.error["line"], 1)

    def test_stdout_is_captured_separately_from_results(self):
        from gauntlet import sandbox
        report = sandbox.run_tests(
            "print('hello from the player')\ndef f():\n    return 1\n",
            {"kind": "function", "name": "f"},
            [{"name": "t", "args": [], "expected": 1, "hidden": False}])
        self.assertIn("hello from the player", report.stdout)
        self.assertTrue(report.all_passed)

    def test_exception_is_classified_not_crashed_on(self):
        from gauntlet import sandbox
        report = sandbox.run_tests(
            "def f(x):\n    return x[99]\n",
            {"kind": "function", "name": "f"},
            [{"name": "t", "args": [[1, 2]], "expected": 1, "hidden": False}])
        self.assertEqual(report.tests[0].status, "exception")
        self.assertIn("IndexError", report.tests[0].message)

    def test_writes_into_the_real_home_directory_are_refused(self):
        """HOME is redirected into the scratch dir for the child, so this checks
        the seatbelt against the user's ACTUAL home path."""
        from pathlib import Path
        from gauntlet import sandbox
        target = str(Path.home() / "gauntlet-sandbox-escape-check")
        report = sandbox.run_tests(
            "def f():\n"
            "    try:\n"
            f"        open({target!r}, 'w').write('x')\n"
            "        return 'WROTE'\n"
            "    except Exception:\n"
            "        return 'REFUSED'\n",
            {"kind": "function", "name": "f"},
            [{"name": "t", "args": [], "expected": "REFUSED", "hidden": False}])
        self.assertFalse(Path(target).exists(), "player code escaped into $HOME")
        if report.hardened:
            self.assertTrue(report.all_passed,
                            "the seatbelt must refuse writes into the real home")

    def test_home_is_redirected_away_from_the_users_files(self):
        from pathlib import Path
        from gauntlet import sandbox
        report = sandbox.run_tests(
            "import os\n"
            "def f():\n    return os.path.expanduser('~')\n",
            {"kind": "function", "name": "f"},
            [{"name": "t", "args": [], "expected": str(Path.home()),
              "hidden": False}])
        self.assertEqual(report.tests[0].status, "fail",
                         "the child must not see the real home directory")

    def test_per_test_timeout_does_not_kill_the_batch(self):
        from gauntlet import sandbox
        report = sandbox.run_tests(
            "def f(n):\n"
            "    if n == 0:\n"
            "        while True:\n            pass\n"
            "    return n\n",
            {"kind": "function", "name": "f"},
            [{"name": "slow", "args": [0], "expected": 0, "timeout_ms": 400,
              "hidden": False},
             {"name": "fast", "args": [5], "expected": 5, "hidden": False}])
        self.assertEqual(report.tests[0].status, "timeout")
        self.assertEqual(report.tests[1].status, "pass")

    def test_class_ops_entry_replays_an_operation_trace(self):
        from gauntlet import sandbox
        report = sandbox.run_tests(
            "class Counter:\n"
            "    def __init__(self):\n        self.n = 0\n"
            "    def inc(self):\n        self.n += 1\n        return self.n\n",
            {"kind": "class_ops", "name": "Counter"},
            [{"name": "t", "ops": ["__init__", "inc", "inc"],
              "args": [[], [], []], "expected": [None, 1, 2], "hidden": False}])
        self.assertTrue(report.all_passed)


if __name__ == "__main__":
    unittest.main()
