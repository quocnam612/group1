from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ocr_week2_pipeline import commands


class Week2PipelineTests(unittest.TestCase):
    def config(self):
        return {"seed": 42, "out_dir": "out", "ocr": {
            "sample_pdf": "chinh/sample.pdf",
            "engines": ["paddleocr", "got-ocr2", "qwen2.5-vl", "tesseract"],
            "evaluation_pages": "38-48", "vote_engines": ["paddleocr", "qwen2.5-vl", "tesseract"],
            "engine_options": {"qwen2.5-vl": {"profile": "balanced", "cpu_offload": True, "device": "cuda:0"}}}}

    def test_single_plan_runs_inference_then_voting_then_cer_without_any_baseline(self):
        plan = commands(self.config())
        self.assertEqual(len(plan), 7)
        self.assertTrue(plan[0][1].endswith("ocr_prepare.py"))
        self.assertIn("chinh/sample.pdf", plan[0])
        self.assertTrue(all("build_corpus" not in " ".join(c) for c in plan))
        qwen = plan[3]
        self.assertIn("--cpu-offload", qwen)
        self.assertEqual(qwen[qwen.index("--profile")+1], "balanced")
        self.assertTrue(plan[-2][1].endswith("ocr_vote.py"))
        self.assertTrue(plan[-1][1].endswith("ocr_week2_report.py"))
        self.assertEqual(plan[-2][-3:], ["paddleocr", "qwen2.5-vl", "tesseract"])

    def test_rejects_selecting_one_best_engine_disguised_as_voting(self):
        config = self.config()
        config["ocr"]["vote_engines"] = ["qwen2.5-vl"]
        with self.assertRaisesRegex(ValueError, "three"):
            commands(config)

    def test_scoring_only_does_not_run_models(self):
        self.assertEqual(len(commands(self.config(), skip_ocr=True)), 2)
        self.assertTrue(all("--overwrite" in c for c in commands(self.config(), overwrite=True)[1:5]))

    def test_rejects_a_script_with_only_one_voter_before_running_models(self):
        config = self.config()
        config["ocr"]["vote_vietnamese_engines"] = ["qwen2.5-vl"]
        with self.assertRaisesRegex(ValueError, "three"):
            commands(config)


if __name__ == "__main__":
    unittest.main()
