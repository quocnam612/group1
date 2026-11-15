"""Per-page storage must retain every OCR variant and layout without TXT files."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import csv
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pages import (apply_review_patches, checksum, get_layout, get_ocr, migrate, ocr_key, put_layout,
                   put_ocr, read_page, refresh_text, save_json)


class PageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "images/page-0038.png"
        self.source.parent.mkdir()
        self.source.write_bytes(b"source pixels")
        self.assets = self.root / "layout"
        self.crop = self.assets / "images/han/page-0038-r002.png"
        self.crop.parent.mkdir(parents=True)
        self.crop.write_bytes(b"Han pixels")
        self.directory = self.root / "pages"
        self.layout = {"image": str(self.source), "fingerprint": {"image_sha256": checksum(self.source)},
                       "regions": [{"id": "r002", "layer": "han", "section": "main", "bbox": [0, 0, 10, 10],
                                    "line_ids": ["l001"], "crop": "images/han/page-0038-r002.png",
                                    "ocr_hint": "甲", "flags": [], "status": "needs_review"}],
                       "lines": [], "pairs": [], "outgoing_section": "main"}

    def record(self, engine="paddleocr", text="甲乙"):
        return {"image": str(self.crop), "image_sha256": checksum(self.crop), "engine": engine,
                "settings": {"lang": "chinese_cht" if engine == "paddleocr" else None},
                "text": text, "seconds": .1, "raw": {"untouched": True}}

    def test_layout_and_engines_share_one_page_without_losing_variants(self):
        put_layout(self.directory, self.layout, self.assets)
        paddle, qwen = self.record(), self.record("qwen2.5-vl", "甲")
        put_ocr(self.directory, self.crop, paddle)
        put_ocr(self.directory, self.crop, qwen)
        page = read_page(self.directory / "page-0038.json")
        self.assertEqual(get_layout(page), self.layout)
        self.assertEqual(page["layers"]["han"]["text"], "甲乙")
        self.assertEqual(page["layers"]["han"]["status"], "ocr_unreviewed")
        for record in (paddle, qwen):
            self.assertEqual(get_ocr(self.directory, self.crop, ocr_key(record)), record)
        self.assertEqual([p.name for p in self.directory.iterdir()], ["page-0038.json"])
        put_layout(self.directory, self.layout, self.assets)
        self.assertEqual(get_ocr(self.directory, self.crop, ocr_key(paddle)), paddle)

    def test_hint_only_text_is_not_marked_as_recognized(self):
        put_layout(self.directory, self.layout, self.assets)
        layer = read_page(self.directory / "page-0038.json")["layers"]["han"]
        self.assertEqual(layer["text"], "甲")
        self.assertEqual(layer["status"], "hint_only")

    def patch_file(self, text, image_hash=None):
        path = self.root / "corrections.tsv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["page", "region_id", "image_sha256", "text", "note"], delimiter="\t")
            writer.writeheader()
            writer.writerow({"page": 38, "region_id": "r002", "image_sha256": image_hash or checksum(self.crop),
                             "text": text, "note": "test source review"})
        return path

    def test_review_patch_changes_readable_text_but_preserves_raw_ocr(self):
        put_layout(self.directory, self.layout, self.assets)
        raw = self.record()
        put_ocr(self.directory, self.crop, raw)
        patch_file = self.patch_file("校正\n字")
        apply_review_patches(self.directory, patch_file)
        path = self.directory / "page-0038.json"
        page = read_page(path)
        self.assertEqual(page["content"]["han"], ["校正", "字"])
        self.assertEqual(page["layers"]["han"]["status"], "source_checked")
        self.assertEqual(get_ocr(self.directory, self.crop, ocr_key(raw)), raw)
        self.assertLess(path.read_text().index('"content"'), path.read_text().index('"source"'))
        apply_review_patches(self.directory, patch_file)
        put_layout(self.directory, self.layout, self.assets)
        self.assertEqual(read_page(path)["content"]["han"], ["校正", "字"])
        self.assertEqual(get_layout(read_page(path)), self.layout)

    def test_review_patch_refuses_a_different_crop(self):
        put_layout(self.directory, self.layout, self.assets)
        path = self.directory / "page-0038.json"
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "source image changed"):
            apply_review_patches(self.directory, self.patch_file("new", "0"*64))
        self.assertEqual(path.read_bytes(), before)

    def test_viewer_embeds_text_safely_without_a_fetch_dependency(self):
        from review import build_review
        import json,re
        put_layout(self.directory, self.layout, self.assets)
        text = '</script><script>alert("unsafe")</script>'
        put_ocr(self.directory, self.crop, self.record(text=text))
        path = build_review(self.directory)
        source = path.read_text()
        payload = re.search(r'<script id="page-data" type="application/json">(.*?)</script>', source, re.S)[1]
        self.assertNotIn("</script>", payload)
        self.assertEqual(json.loads(payload)[0]["regions"][0]["text"], text)
        self.assertNotIn("fetch(", source)

    def test_ocr_cli_merges_engines_and_does_not_create_txt(self):
        import ocr
        fake_runner = lambda args: lambda path: ("甲乙", {"test_only": True})
        for engine in ("paddleocr", "got-ocr2"):
            argv = ["ocr.py", "run", "--engine", engine, "--input", str(self.source),
                    "--output", str(self.directory), "--device", "cpu"]
            with patch.object(sys, "argv", argv), patch.object(ocr, "paddle_runner", fake_runner), \
                    patch.object(ocr, "vlm_runner", fake_runner), redirect_stdout(StringIO()):
                ocr.main()
        page = read_page(self.directory / "page-0038.json")
        self.assertEqual(set(page["fullpage_ocr"]), {"paddleocr:chinese_cht", "got-ocr2"})
        self.assertEqual([p.name for p in self.directory.iterdir()], ["page-0038.json"])

    def test_crop_without_registered_layout_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "No page layout"):
            put_ocr(self.directory, self.crop, self.record())

    def test_concurrent_engines_do_not_overwrite_each_other(self):
        put_layout(self.directory, self.layout, self.assets)
        records = [self.record("qwen2.5-vl"), self.record("got-ocr2")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(put_ocr, self.directory, self.crop, record) for record in records]
            for future in futures:
                future.result()
        for record in records:
            self.assertEqual(get_ocr(self.directory, self.crop, ocr_key(record)), record)

    def test_overwrite_archives_previous_configuration(self):
        put_layout(self.directory, self.layout, self.assets)
        original = self.record("qwen2.5-vl", "old")
        put_ocr(self.directory, self.crop, original)
        changed = self.record("qwen2.5-vl", "new")
        changed["settings"]["max_new_tokens"] = 2048
        put_ocr(self.directory, self.crop, changed, overwrite=True)
        put_ocr(self.directory, self.crop, changed, overwrite=True)
        page = read_page(self.directory / "page-0038.json")
        self.assertEqual(page["ocr_history"]["r002"]["qwen2.5-vl"], [original])
        self.assertEqual(get_ocr(self.directory, self.crop, "qwen2.5-vl"), changed)

    def test_vietnamese_display_avoids_a_model_with_incomplete_charset(self):
        self.layout["regions"][0]["layer"] = "phien_am"
        put_layout(self.directory, self.layout, self.assets)
        limited = self.record(text="hnh")
        limited["settings"]["lang"] = "vi"
        limited["vietnamese_charset_complete"] = False
        put_ocr(self.directory, self.crop, limited)
        qwen = self.record("qwen2.5-vl", "hạnh")
        put_ocr(self.directory, self.crop, qwen)
        page = read_page(self.directory / "page-0038.json")
        self.assertEqual(page["layers"]["phien_am"]["text"], "hạnh")
        self.assertEqual(get_ocr(self.directory, self.crop, "paddleocr:vi"), limited)

    def test_cli_selects_registered_layer_and_page_without_polluting_settings(self):
        import ocr
        put_layout(self.directory, self.layout, self.assets)
        seen = []
        def fake(args):
            def recognize(path):
                seen.append(path)
                return "甲乙", {}
            return recognize
        argv = ["ocr.py", "run", "--engine", "paddleocr", "--layers", "han", "--pages", "38",
                "--output", str(self.directory), "--device", "cpu"]
        with patch.object(sys, "argv", argv), patch.object(ocr, "paddle_runner", fake), redirect_stdout(StringIO()):
            ocr.main()
        self.assertEqual(seen, [self.crop])
        record = get_ocr(self.directory, self.crop, "paddleocr:chinese_cht")
        self.assertNotIn("layers", record["settings"])
        self.assertNotIn("pages", record["settings"])

    def test_charset_audit_checks_precomposed_vietnamese_letters(self):
        from ocr import missing_vietnamese_characters
        missing = missing_vietnamese_characters(set("abcạ"))
        self.assertNotIn("ạ", missing)
        self.assertTrue(set("ậựữấ") <= set(missing))
        self.assertNotIn("ạ", missing_vietnamese_characters({"a", "\u0323"}))

    def test_changed_image_is_flagged_and_old_ocr_remains_available(self):
        put_layout(self.directory, self.layout, self.assets)
        record = self.record()
        put_ocr(self.directory, self.crop, record)
        self.crop.write_bytes(b"changed crop pixels")
        page = read_page(self.directory / "page-0038.json")
        refresh_text(page)
        region = page["layers"]["han"]["regions"][0]
        self.assertIn(ocr_key(record), region["stale_ocr"])
        self.assertEqual(region["text_source"], "layout_hint")
        self.assertEqual(region["ocr"][ocr_key(record)], record)

    def legacy(self, edited_txt=False):
        path = self.assets / "page-0038.json"
        save_json(path, self.layout)
        record_path = self.root / "results/han/paddleocr/page-0038-r002.json"
        record = self.record()
        save_json(record_path, record)
        record_path.with_suffix(".txt").write_text("edited" if edited_txt else record["text"]+"\n", encoding="utf-8")
        return path, record_path, record

    def test_migration_is_lossless_before_removing_legacy_files(self):
        layout, record_path, record = self.legacy()
        result = migrate(self.root, clean_legacy=True)
        self.assertEqual((result["pages"], result["ocr_records"], result["removed"]), (1, 1, 3))
        self.assertFalse(layout.exists())
        self.assertFalse(record_path.exists())
        self.assertFalse(record_path.with_suffix(".txt").exists())
        self.assertEqual(get_layout(read_page(self.directory / "page-0038.json")), self.layout)
        self.assertEqual(get_ocr(self.directory, self.crop, ocr_key(record)), record)
        self.assertEqual(migrate(self.root, clean_legacy=True)["removed"], 0)

    def test_migration_does_not_delete_hand_edited_text(self):
        layout, record_path, _record = self.legacy(edited_txt=True)
        with self.assertRaisesRegex(ValueError, "TXT differs"):
            migrate(self.root, clean_legacy=True)
        self.assertTrue(layout.exists())
        self.assertTrue(record_path.exists())
        self.assertFalse(self.directory.exists())


if __name__ == "__main__":
    unittest.main()
