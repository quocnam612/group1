from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ocr_compare import edit_distance, normalized


class CERTests(unittest.TestCase):
    def test_true_edit_distance_counts_insertions_deletions_and_substitutions(self):
        self.assertEqual(edit_distance("kitten", "sitting"), 3)
        self.assertEqual(edit_distance("", "字"), 1)
        self.assertEqual(edit_distance("關關雎鳩", "關雎鳩"), 1)

    def test_unicode_and_wrapping_are_normalized_but_accents_are_not_removed(self):
        self.assertEqual(normalized(["nu\u031b\u0303"], "phien_am"), "nữ")
        self.assertEqual(normalized(["關 關", "雎鳩"], "han"), "關關雎鳩")
        self.assertEqual(normalized(["thục", "nữ"], "phien_am"), "thục nữ")
        self.assertEqual(edit_distance(normalized(["nữ"], "phien_am"), normalized(["nu"], "phien_am")), 1)


if __name__ == "__main__":
    unittest.main()
