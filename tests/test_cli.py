import unittest
from playlister_lib.cli import parse_args

class TestCLI(unittest.TestCase):
    def test_diff_command(self):
        args = parse_args(["diff", "sheet.csv"])
        self.assertEqual(args.command, "diff")
        self.assertEqual(args.csv_file, "sheet.csv")
        self.assertIsNone(args.key_dir)
        self.assertFalse(args.no_store_key)

    def test_push_command(self):
        args = parse_args(["push", "sheet.csv", "--auto-approve", "--remove-dupes", "--key-dir", "/tmp/k", "--no-store-key"])
        self.assertEqual(args.command, "push")
        self.assertEqual(args.csv_file, "sheet.csv")
        self.assertTrue(args.auto_approve)
        self.assertTrue(args.remove_dupes)
        self.assertEqual(args.key_dir, "/tmp/k")
        self.assertTrue(args.no_store_key)

    def test_check_command(self):
        args = parse_args(["check", "sheet.csv"])
        self.assertEqual(args.command, "check")
        self.assertEqual(args.csv_file, "sheet.csv")

    def test_print_command(self):
        args = parse_args(["print", "sheet.csv"])
        self.assertEqual(args.command, "print")
        self.assertEqual(args.csv_file, "sheet.csv")

    def test_dump_command(self):
        args = parse_args(["dump", "my_playlist"])
        self.assertEqual(args.command, "dump")
        self.assertEqual(args.playlist_or_album, "my_playlist")

    def test_test_keys_command(self):
        args = parse_args(["test-keys", "--local"])
        self.assertEqual(args.command, "test-keys")
        self.assertTrue(args.local)

    def test_clear_keys_command(self):
        args = parse_args(["clear-keys"])
        self.assertEqual(args.command, "clear-keys")

    def test_clear_cache_command(self):
        args = parse_args(["clear-cache"])
        self.assertEqual(args.command, "clear-cache")

    def test_clear_all_command(self):
        args = parse_args(["clear-all"])
        self.assertEqual(args.command, "clear-all")

    def test_missing_subcommand(self):
        with self.assertRaises(SystemExit):
            parse_args([])

    def test_invalid_subcommand(self):
        with self.assertRaises(SystemExit):
            parse_args(["invalid-subcmd"])

    def test_strict_flag(self):
        args = parse_args(["diff", "sheet.csv", "--strict"])
        self.assertTrue(args.strict)
        
        args_no_strict = parse_args(["diff", "sheet.csv"])
        self.assertFalse(getattr(args_no_strict, "strict", False))

if __name__ == "__main__":
    unittest.main()
