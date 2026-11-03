import unittest

from director import NAME, cut_after_next_step, personality, reply


class FredPersonalityTest(unittest.TestCase):
    def test_name_is_fred(self):
        self.assertEqual(NAME, "FRED")
        self.assertIn("FRED", personality())
        self.assertIn("external attention gate", personality())

    def test_reply_is_target_and_next_step_only(self):
        out = reply(
            "wire the gate",
            "add the hard stop",
            extra="and then explain more",
            emotion="frustrated",
        )
        self.assertEqual(out, "Target: wire the gate\n\nNext step: add the hard stop")
        self.assertNotIn("explain", out)
        self.assertNotIn("frustrated", out)

    def test_park_keeps_original_target(self):
        out = reply("wire the gate", "add the hard stop", parked=True)
        self.assertEqual(
            out,
            "Parked. Original target remains: wire the gate\n\nNext step: add the hard stop",
        )

    def test_cut_drops_text_after_next_step(self):
        leaked = (
            "Target: wire the gate\n"
            "\n"
            "Next step: add the hard stop\n"
            "\n"
            "Here is extra teaching.\n"
        )
        self.assertEqual(
            cut_after_next_step(leaked),
            "Target: wire the gate\n\nNext step: add the hard stop",
        )

    def test_reply_requires_both_fields(self):
        with self.assertRaises(ValueError):
            reply("", "do the thing")
        with self.assertRaises(ValueError):
            reply("the thing", "")


if __name__ == "__main__":
    unittest.main()

