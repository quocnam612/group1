"""Majority voting must count omissions and must not favor an answer oracle."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ocr_vote import align_pairwise, edit_distance, star_alignment, vote_text


class CharacterVoteTests(unittest.TestCase):
    def setUp(self):
        self.order = ["qwen2.5-vl", "paddleocr", "got-ocr2"]
        self.ranks = {"vietnamese": self.order, "han": ["paddleocr", "qwen2.5-vl", "got-ocr2"]}

    def vote(self, values, alignment="star"):
        return vote_text(dict(zip(self.order, values)), self.order, self.ranks, alignment)

    def test_three_way_tie_can_choose_omission_from_the_best_engine(self):
        for alignment in ("star", "progressive"):
            self.assertEqual(self.vote(["đúng", "ađúng", "bđúng"], alignment), "đúng")

    def test_two_equal_votes_override_a_better_ranked_single_vote(self):
        self.assertEqual(self.vote(["nữ", "nu", "nu"]), "nu")
        self.assertEqual(self.vote(["ađúng", "đúng", "đúng"]), "đúng")
        self.assertEqual(self.vote(["đúng", "ađúng", "ađúng"]), "ađúng")

    def test_accent_tie_preserves_the_original_character_of_the_winner(self):
        self.assertEqual(self.vote(["thục", "thc", "thùc"]), "thục")

    def test_star_columns_reconstruct_every_input_including_repeated_han(self):
        texts = dict(zip(self.order, ["關關雎鳩", "關關雎鳩", "關雎鳩"]))
        columns = star_alignment(texts, self.order)
        for engine, text in texts.items():
            self.assertEqual("".join(c[engine] for c in columns if c.get(engine) is not None), text)
        self.assertEqual(vote_text(texts, self.order, self.ranks), "關關雎鳩")

    def test_empty_outputs_count_as_omissions(self):
        self.assertEqual(self.vote(["abc", "", ""]), "")
        self.assertEqual(self.vote(["", "", ""]), "")

    def test_cer_keeps_edits_between_long_shared_prefixes_and_suffixes(self):
        prefix, suffix = "Chương này "*40, " giữ đúng theo nguồn."*40
        self.assertEqual(edit_distance(prefix+"thục nữ"+suffix, prefix+"thực nư"+suffix), 2)
        self.assertEqual(edit_distance("abc", "ab"), 1)

    def test_literal_majority_keeps_the_models_original_diacritics(self):
        self.assertEqual(self.vote(["nữ", "nu", "nu"]), "nu")
        texts = dict(zip(self.order, ["thục nữ", "thc nu", "thùc nǚ"]))
        columns = star_alignment(texts, self.order)
        for engine, text in texts.items():
            self.assertEqual("".join(c[engine] for c in columns if c.get(engine) is not None), text)

    def test_script_routing_uses_literal_majority_of_at_least_three_engines(self):
        order = ["qwen2.5-vl", "tesseract", "paddleocr", "got-ocr2"]
        ranks = {"han": order, "vietnamese": order}
        voters = {"han": order, "vietnamese": order[:3]}
        texts = dict(zip(order, ["字nữ", "字nữ", "字nu", "字nu"]))
        self.assertEqual(vote_text(texts, order, ranks, voters_by_language=voters), "字nữ")
        texts = dict(zip(order, ["字nữ", "字nu", "字nu", "字nữ"]))
        self.assertEqual(vote_text(texts, order, ranks, voters_by_language=voters), "字nu")


if __name__ == "__main__":
    unittest.main()
