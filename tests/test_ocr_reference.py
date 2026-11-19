"""Benchmark exports must contain each engine's raw text, never hints or patches."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import ocr
from ocr_reference import FIELDS, compatible_native_record, write_crop_manifest
from pages import LAYERS


class ReferenceOCRTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.assets = self.root / "layout"
        self.output = self.root / "pages"
        self.manifest = self.assets / "regions.json"
        layers = {key: {"regions": []} for key in LAYERS}
        self.crops = []
        for id_, layer in (("r010", "tieu_de_viet"), ("r002", "han"), ("r011", "tieu_de_han"), ("r003", "phien_am")):
            relative = f"images/{layer}/page-0038-{id_}.png"
            crop = self.assets / relative
            crop.parent.mkdir(parents=True, exist_ok=True)
            crop.write_bytes(layer.encode())
            self.crops.append(crop)
            group = "tieu_de" if layer.startswith("tieu_de") else layer
            layers[group]["regions"].append({"id": id_, "layer": layer, "crop": relative,
                                              "ocr_hint": "DO NOT EXPORT HINT", "text": "DO NOT EXPORT PATCH"})
        archive = self.root / "archive/page-0038.json"
        archive.parent.mkdir()
        archive.write_text(json.dumps({"schema_version": 1, "page": 38, "layers": layers,
                                       "layout": {"region_order": ["r010", "r002", "r011", "r003"]}}))
        write_crop_manifest([archive], self.assets, self.manifest)

    def command(self, engine="qwen2.5-vl", *extra, factory=None):
        argv = ["ocr.py", "run", "--engine", engine, "--format", "reference", "--layout", str(self.manifest),
                "--output", str(self.output), "--device", "cpu", "--pages", "38", *extra]
        factory = factory or (lambda args: lambda path: ("原文\nDấu Việt: thục nữ, mỵ.", {"test_only": True}))
        with patch.object(sys, "argv", argv), patch.object(ocr, "paddle_runner", factory), \
                patch.object(ocr, "vlm_runner", factory), redirect_stdout(StringIO()):
            ocr.main()

    def test_export_is_reference_shaped_and_never_uses_reviewed_text(self):
        self.command()
        result = json.loads((self.output / "qwen2.5-vl/page-0038.json").read_text())
        self.assertEqual(tuple(result), FIELDS)
        self.assertEqual(result["han"], ["原文", "Dấu Việt: thục nữ, mỵ."])
        self.assertNotIn("DO NOT EXPORT", json.dumps(result))
        self.assertNotIn("page", result)
        self.assertNotIn("so_trang", result)
        self.assertEqual(list(self.root.glob("runs/*.json")), [self.root / "runs/qwen2.5-vl.json"])

    def test_crop_order_from_layout_is_preserved_for_combined_titles(self):
        self.command(factory=lambda args: lambda path: (path.stem, {}))
        result = json.loads((self.output / "qwen2.5-vl/page-0038.json").read_text())
        self.assertEqual(result["tieu_de"], ["page-0038-r010", "page-0038-r011"])

    def test_paddle_automatically_uses_han_and_vietnamese_recognizers(self):
        modes = []
        def factory(args):
            modes.append((args.lang, args.paddle_mode))
            return lambda path: ("raw", {})
        self.command("paddleocr", factory=factory)
        self.assertCountEqual(modes, [("vi", "page"), ("chinese_cht", "han-lines")])

    def test_resume_rebuilds_from_cached_raw_ocr_without_loading_models(self):
        self.command("got-ocr2")
        target = self.output / "got-ocr2/page-0038.json"
        target.write_text('{"han": ["manually changed result"]}')
        self.manifest.write_text(self.manifest.read_text()+"\n")
        self.command("got-ocr2", factory=lambda args: self.fail("Cached run loaded a model"))
        self.assertEqual(json.loads(target.read_text())["han"], ["原文", "Dấu Việt: thục nữ, mỵ."])
        import hashlib
        metadata = json.loads((self.root / "runs/got-ocr2.json").read_text())
        self.assertEqual(metadata["layout_manifest_sha256"], hashlib.sha256(self.manifest.read_bytes()).hexdigest())

    def test_changed_crop_fails_before_loading_any_model(self):
        self.crops[0].write_bytes(b"different image")
        with self.assertRaisesRegex(SystemExit, "1"):
            self.command(factory=lambda args: self.fail("Changed crop loaded a model"))
        self.assertFalse(self.output.exists())

    def test_settings_change_requires_explicit_overwrite(self):
        self.command()
        with self.assertRaisesRegex(SystemExit, "1"):
            self.command("qwen2.5-vl", "--max-new-tokens", "2048")
        self.command("qwen2.5-vl", "--max-new-tokens", "2048", "--overwrite")
        metadata = json.loads((self.root / "runs/qwen2.5-vl.json").read_text())
        self.assertEqual(metadata["settings"]["max_new_tokens"], 2048)

    def test_calibration_of_one_page_retains_other_pages_cached_records(self):
        self.command()
        path = self.root / "runs/qwen2.5-vl.json"
        metadata = json.loads(path.read_text())
        metadata["records"]["page-0039.json:r001"] = {"text": "other page", "image_sha256": "0"*64}
        path.write_text(json.dumps(metadata))
        self.command("qwen2.5-vl", "--max-new-tokens", "512", "--overwrite")
        metadata = json.loads(path.read_text())
        self.assertEqual(metadata["records"]["page-0039.json:r001"]["text"], "other page")
        self.assertTrue(metadata["settings_history"])

    def test_native_cache_rejects_changed_pixels_resolution_prompt_and_revision(self):
        from argparse import Namespace
        settings = {"engine": "qwen2.5-vl", "device": "cuda:0", "seed": 42, "quantization": "4bit",
                    "max_pixels": 401408, "model": "Qwen/test", "revision": "a"*40, "cpu_offload": True}
        args = Namespace(**settings, max_new_tokens=512)
        record = {"image_sha256": "b"*64, "prompt": ocr.PROMPT, "model": args.model,
                  "revision": args.revision, "generated_tokens": 120, "text": "raw unchanged"}
        self.assertTrue(compatible_native_record(settings, record, args, "b"*64))
        self.assertFalse(compatible_native_record(settings, record, args, "c"*64))
        self.assertFalse(compatible_native_record(settings | {"max_pixels": 802816}, record, args, "b"*64))
        self.assertFalse(compatible_native_record(settings, record | {"prompt": "reviewed reference"}, args, "b"*64))
        self.assertFalse(compatible_native_record(settings, record | {"revision": "c"*40}, args, "b"*64))
        self.assertFalse(compatible_native_record(settings, record | {"generated_tokens": 512}, args, "b"*64))


if __name__ == "__main__":
    unittest.main()
