import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import splash_launcher


class QuranSequenceTests(unittest.TestCase):
    def test_curated_sequence_is_exact(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"APPDATA": folder}):
            expected = splash_launcher.INTRO_PASSAGES
            actual = []
            for _ in expected:
                passage = splash_launcher.select_ayat()
                actual.append((int(passage["sura"]), int(passage["aya_start"]),
                               int(passage["aya_end"])))
            self.assertEqual(actual, expected)

    def test_all_ayat_remain_bundled(self):
        records = json.loads(Path("assets/quran_ayat.json").read_text(encoding="utf-8"))
        self.assertEqual(len(records), 6236)


if __name__ == "__main__":
    unittest.main()
