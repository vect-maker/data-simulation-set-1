"""Unit tests for CLI interfaces."""

import unittest
from data_sim.cli import build_parser as build_unified_parser
from antojitos_sim.cli import main as antojitos_main
from volcan_sim.cli import main as volcan_main
from movigo_sim.cli import main as movigo_main


class TestCLIInterfaces(unittest.TestCase):
    """Test CLI argument parsers."""

    def test_unified_parser(self):
        parser = build_unified_parser()
        args = parser.parse_args(["generate", "--case", "antojitos", "--days", "5"])
        self.assertEqual(args.command, "generate")
        self.assertEqual(args.case, "antojitos")
        self.assertEqual(args.days, 5)

        args_l = parser.parse_args(["load", "--case", "all"])
        self.assertEqual(args_l.command, "load")
        self.assertEqual(args_l.case, "all")

        args_w = parser.parse_args(["weather", "--case", "all"])
        self.assertEqual(args_w.command, "weather")
        self.assertEqual(args_w.case, "all")

        args_i = parser.parse_args(["inspect", "--case", "volcan"])
        self.assertEqual(args_i.command, "inspect")
        self.assertEqual(args_i.case, "volcan")


if __name__ == "__main__":
    unittest.main()
