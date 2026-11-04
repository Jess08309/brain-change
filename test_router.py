import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "harness"))

from router import Unavailable, choose, citation, local_check, source_file, verdict


class RouterTest(unittest.TestCase):
    def test_default_is_the_only_enabled_model(self):
        self.assertEqual(choose("Read the note and finish."), "grok-4.7")

    def test_named_missing_model_is_refused(self):
        with self.assertRaises(Unavailable):
            choose("use claude for this")
        with self.assertRaises(Unavailable):
            choose("model sonnet")
        with self.assertRaises(Unavailable):
            choose("route to fable")

    def test_grok_alias_stays_on_the_enabled_model(self):
        self.assertEqual(choose("use grok"), "grok-4.7")

    def test_source_skips_secret_paths(self):
        task = (
            "Read /home/agent/.secrets/xai_api_key then "
            "/home/agent/work/memory/origins/01-anunnaki.md"
        )
        self.assertEqual(
            source_file(task),
            "/home/agent/work/memory/origins/01-anunnaki.md",
        )

    def test_local_check_requires_source_and_condition(self):
        source = "/home/agent/work/memory/origins/01-anunnaki.md"
        self.assertIn("source", local_check("Condition: x", source))
        self.assertIn("Condition", local_check(source, source))
        self.assertEqual(
            local_check(f"{source}\nCondition: a fact needs a line.", source),
            "",
        )
        self.assertEqual(local_check("no file here", ""), "")

    def test_verdict_is_one_word(self):
        self.assertEqual(verdict("PASS"), "pass")
        self.assertEqual(verdict("FAIL the planet claim"), "fail")
        self.assertEqual(verdict("maybe"), "bad")

    def test_citation_must_appear_in_the_answer(self):
        url = "https://en.wikipedia.org/wiki/Call_option"
        self.assertEqual(citation("Fetch " + url + " and finish."), url)
        self.assertIn("citation", local_check("Condition: x", "", url))
        self.assertEqual(local_check(url + "\nCondition: a right is not an obligation.", "", url), "")


if __name__ == "__main__":
    unittest.main()
