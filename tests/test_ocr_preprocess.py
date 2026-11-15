"""Keep diacritics, tight neighboring lines and unmodified source scans."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ocr_preprocess import prepare_scan_lines, qwen_scan_prompt, scan_line_boxes


class ScanPreprocessTests(unittest.TestCase):
    def test_close_rows_remain_separate_and_accent_dots_stay_with_their_row(self):
        from PIL import Image, ImageDraw
        image = Image.new("L", (300, 160), 255)
        draw = ImageDraw.Draw(image)
        for top in (10, 40, 70, 100, 130):
            draw.rectangle([20, top, 200, top+22], fill=0)
            draw.rectangle([30, top-3, 33, top-2], fill=0)
        boxes = scan_line_boxes(image)
        self.assertEqual(len(boxes), 5)
        for i, box in enumerate(boxes):
            self.assertLessEqual(box[1], 7+i*30)
            if i:
                self.assertGreaterEqual(box[1], boxes[i-1][3])

    def test_preprocessing_writes_only_cache_and_retains_title_as_one_image(self):
        from PIL import Image, ImageDraw
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "tieu_de/page-0038-r001.png"
            path.parent.mkdir()
            image = Image.new("RGB", (200, 80), "white")
            ImageDraw.Draw(image).rectangle([10, 10, 150, 50], fill="black")
            image.save(path)
            original = path.read_bytes()
            parts = prepare_scan_lines(path, Path(temp) / "cache")
            self.assertEqual(len(parts), 1)
            self.assertEqual(path.read_bytes(), original)
            with Image.open(parts[0][0]) as processed:
                self.assertEqual(processed.size, (432, 192))

    def test_han_prompt_preserves_repetitions_and_vietnamese_prompt_keeps_diacritics(self):
        self.assertIn("repetitions", qwen_scan_prompt("han"))
        self.assertIn("diacritics", qwen_scan_prompt("phien_am"))
        self.assertNotIn("關關", qwen_scan_prompt("han"))


if __name__ == "__main__":
    unittest.main()
