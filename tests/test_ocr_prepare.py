"""Frozen crop regeneration must preserve the pixels used in OCR evaluation."""
from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ocr_prepare import prepare


class PrepareOCRTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.layout = self.root / "layout/regions.json"
        self.layout.parent.mkdir()
        self.pdf = self.root / "original.pdf"
        self.pdf.write_bytes(b"unmodified original PDF")
        self.image = self.root / "images/page-0038.png"
        self.crop = self.root / "layout/images/han/page-0038-r001.png"
        image = Image.new("RGB", (50, 70), "white")
        ImageDraw.Draw(image).rectangle((10, 20, 30, 40), fill="black")
        from io import BytesIO
        raw = BytesIO()
        image.save(raw, format="PNG")
        self.image_bytes = raw.getvalue()
        raw = BytesIO()
        image.crop((8, 18, 33, 43)).save(raw, format="PNG")
        self.crop_bytes = raw.getvalue()
        digest = lambda data: hashlib.sha256(data).hexdigest()
        self.manifest = {"schema_version": 2, "assets_dir": ".",
                         "source": {"pdf_sha256": digest(self.pdf.read_bytes()), "dpi": 300},
                         "pages": [{"page": 38, "file": "page-0038.json", "image": "../images/page-0038.png",
                                    "image_size": [50, 70], "image_sha256": digest(self.image_bytes),
                                    "regions": [{"id": "r001", "layer": "han", "bbox": [8, 18, 33, 43],
                                                 "crop": "images/han/page-0038-r001.png",
                                                 "image_sha256": digest(self.crop_bytes)}]}]}
        self.layout.write_text(json.dumps(self.manifest))

    def run_prepare(self, **kwargs):
        with redirect_stdout(StringIO()):
            return prepare(self.layout, self.pdf, 300, [38], **kwargs)

    def test_cold_start_renders_original_page_and_restores_exact_crop(self):
        def render(command, check):
            self.assertTrue(check)
            self.assertEqual(command[:7], ["pdftoppm", "-f", "38", "-l", "38", "-r", "300"])
            self.assertEqual(command[-2], str(self.pdf))
            Path(command[-1]).with_suffix(".png").write_bytes(self.image_bytes)
        with patch("ocr_prepare.subprocess.run", render):
            self.assertEqual(self.run_prepare(), 2)
        self.assertEqual(self.image.read_bytes(), self.image_bytes)
        self.assertEqual(self.crop.read_bytes(), self.crop_bytes)
        with patch("ocr_prepare.subprocess.run", side_effect=AssertionError("Unexpected render")):
            self.assertEqual(self.run_prepare(), 0)

    def test_existing_page_can_restore_missing_crop_without_original_pdf(self):
        self.image.parent.mkdir()
        self.image.write_bytes(self.image_bytes)
        self.pdf.unlink()
        self.assertEqual(self.run_prepare(), 1)
        self.assertEqual(self.crop.read_bytes(), self.crop_bytes)

    def test_changed_pdf_is_rejected_before_rendering(self):
        self.pdf.write_bytes(b"different PDF")
        with patch("ocr_prepare.subprocess.run") as render, self.assertRaisesRegex(ValueError, "differs"):
            self.run_prepare()
        render.assert_not_called()
        self.assertFalse(self.image.exists())

    def test_changed_crop_is_rejected_without_overwriting_it(self):
        self.image.parent.mkdir()
        self.image.write_bytes(self.image_bytes)
        self.crop.parent.mkdir(parents=True)
        self.crop.write_bytes(b"different pixels")
        with self.assertRaisesRegex(ValueError, "differs"):
            self.run_prepare()
        self.assertEqual(self.crop.read_bytes(), b"different pixels")


if __name__ == "__main__":
    unittest.main()
