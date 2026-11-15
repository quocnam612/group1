"""Prevent dropped rows and glyph clipping in horizontal Han recognition."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from han_lines import ink_bands, split_han_lines


class HanLineTests(unittest.TestCase):
    def test_small_internal_gap_does_not_split_a_glyph(self):
        counts = [0]*4 + [20]*10 + [0]*2 + [20]*10 + [0]*12 + [20]*20
        self.assertEqual(ink_bands(counts, 3, 3, 6), [(4, 26), (38, 58)])

    def test_isolated_speck_is_not_a_text_row(self):
        counts = [0]*3 + [4] + [0]*12 + [20]*20 + [0]*5
        self.assertEqual(ink_bands(counts, 3, 3, 6), [(16, 36)])

    def test_rows_retain_all_ink_and_stay_separate(self):
        from PIL import Image, ImageDraw
        image = Image.new("L", (320, 800), 255)
        draw = ImageDraw.Draw(image)
        for row in range(8):
            for col in range(4):
                draw.rectangle([10+col*75, 20+row*90, 65+col*75, 75+row*90], fill=0)
        boxes = split_han_lines(image)
        self.assertEqual(len(boxes), 8)
        for row, (left, top, right, bottom) in enumerate(boxes):
            self.assertLessEqual(left, 10)
            self.assertGreater(right, 290)
            self.assertLessEqual(top, 20+row*90)
            self.assertGreater(bottom, 75+row*90)
            if row:
                self.assertGreaterEqual(top, boxes[row-1][3])

    def test_blank_image_is_rejected(self):
        from PIL import Image
        with self.assertRaisesRegex(ValueError, "No horizontal Han rows"):
            split_han_lines(Image.new("L", (320, 800), 255))


if __name__ == "__main__":
    unittest.main()
