"""Geometry and layer regressions independent of Paddle/model downloads."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from layout import assign_region_ids, make_regions, recover_han_titles, refine


def line(text, bbox):
    return {"text": text, "bbox": bbox, "score": .95}


class LayoutTests(unittest.TestCase):
    def test_missing_han_title_is_recovered_without_inventing_text(self):
        from PIL import Image, ImageDraw
        image = Image.new("RGB", (500, 400), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle([35, 20, 54, 44], fill="black")
        draw.rectangle([65, 20, 84, 44], fill="black")
        lines, _, _ = refine([
            line("Cát đàm. (Chu nam 2)", [150, 20, 400, 45]),
            line("1. Cát chi đàm hề,", [150, 70, 400, 95]),
            line("維葉萋萋", [10, 120, 110, 145]),
            line("2. Di vu trung cốc.", [150, 122, 400, 147]),
        ], [], "main")
        recovered = recover_han_titles(image, lines)
        titles = [l for l in recovered if l["layer"] == "tieu_de_han"]
        self.assertEqual(len(titles), 1)
        self.assertEqual(titles[0]["bbox"], [35, 20, 85, 45])
        self.assertEqual(titles[0]["text"], "")
        self.assertEqual(recovered[0]["layer"], "tieu_de_viet")

    def test_adding_a_title_does_not_rename_existing_han_crop(self):
        old = [{"id": "r006", "layer": "han", "line_ids": ["l015", "l017"]}]
        regions = [{"layer": "tieu_de_han", "line_ids": ["l031"]},
                   {"layer": "han", "line_ids": ["l015", "l017"]}]
        assign_region_ids(regions, "page-0044", old)
        self.assertEqual(regions[1]["id"], "r006")
        self.assertEqual(regions[1]["crop"], "images/han/page-0044-r006.png")
        self.assertEqual(len({r["id"] for r in regions}), 2)

    def test_numbered_verse_with_comma_is_not_a_heading(self):
        lines, pairs, _ = refine([
            line("關關雎鳩", [10, 20, 110, 45]),
            line("14, Quan quan thư cưu.", [150, 22, 400, 47]),
        ], [], "main")
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["source_index_hint"], 14)
        self.assertEqual([l["layer"] for l in lines], ["han", "phien_am"])

    def test_vertical_fragment_cannot_form_a_sentence_pair(self):
        lines, pairs, _ = refine([
            line("参左窈", [10, 20, 30, 200]),
            line("5. Sâm si hạnh thái,", [150, 22, 400, 47]),
        ], [], "main")
        self.assertFalse(pairs)
        self.assertIn("fragmented_han_detection", next(l for l in lines if l["script"] == "han")["flags"])

    def test_mixed_commentary_remains_intact(self):
        text = "關關 quan quan, tiếng chim trống chim mái"
        lines, pairs, section = refine([line(text, [10, 20, 400, 45])], [], "chu_thich")
        self.assertEqual(lines[0]["text"], text)
        self.assertEqual(lines[0]["layer"], "chu_thich")
        self.assertEqual(lines[0]["script"], "mixed")
        self.assertEqual(section, "chu_thich")
        self.assertFalse(pairs)

    def test_missing_han_row_extends_column_crop_and_is_flagged(self):
        lines, _, _ = refine([
            line("1. Cát chi đàm hề,", [150, 20, 400, 45]),
            line("維葉萋萋", [10, 70, 110, 95]),
            line("2. Di vu trung cốc.", [150, 72, 400, 97]),
        ], [], "main")
        regions = make_regions(lines, (500, 500), 8)
        han = next(r for r in regions if r["layer"] == "han")
        self.assertLess(han["bbox"][1], 20)
        self.assertIn("han_bounds_from_parallel_viet_needs_review", han["flags"])

    def test_crop_overlapping_phonetic_text_is_not_exported_as_han(self):
        lines, _, _ = refine([
            line("關關雎鳩", [10, 20, 220, 45]),
            line("1. Quan quan thư cưu.", [150, 22, 400, 47]),
        ], [], "main")
        regions = make_regions(lines, (500, 500), 8)
        self.assertFalse(any(r["layer"] == "han" for r in regions))
        flagged = next(r for r in regions if "han_crop_overlaps_viet" in r["flags"])
        self.assertEqual(flagged["layer"], "can_kiem_tra")
        self.assertEqual(flagged["proposed_layer"], "han")


if __name__ == "__main__":
    unittest.main()
