import tempfile
import unittest
from pathlib import Path

from laptop.surface import blocked, handle


class LaptopSurfaceTest(unittest.TestCase):
    def test_refuses_trading_secrets_and_orders(self):
        self.assertIn("trading", blocked("open the kalshi file"))
        self.assertIn("secret", blocked("read the .env"))
        self.assertIn("orders", blocked("cancel the order"))
        self.assertIn("root", blocked("ssh root and restart it"))

    def test_empty_instruction_names_the_missing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = handle("", root)
            self.assertTrue(out.startswith("Target: laptop surface"))
            self.assertIn("Next step:", out)
            self.assertIn("not on this machine", out)
            self.assertFalse((root / ".secrets").exists())

    def test_files_one_task_and_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = handle("Check the local index.", root)
            self.assertEqual(
                out,
                "Target: laptop surface\n\nNext step: task filed. The model key is not on this machine, so the call stops here.",
            )
            filed = list((root / "local" / "inbox").glob("*.md"))
            self.assertEqual(len(filed), 1)
            self.assertIn("Check the local index.", filed[0].read_text(encoding="utf-8"))

    def test_a_present_key_is_not_read_and_not_called(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = root / ".secrets"
            secret.mkdir()
            key = secret / "xai_api_key"
            key.write_text("not-a-real-key\n", encoding="utf-8")
            out = handle("Say the next step only.", root)
            self.assertIn("not wired", out)
            self.assertNotIn("not-a-real-key", out)
            self.assertEqual(key.read_text(encoding="utf-8"), "not-a-real-key\n")


if __name__ == "__main__":
    unittest.main()
