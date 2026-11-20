"""Corpus regressions: completeness, honest sentence labels and source fidelity."""
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from corpus.align import gale_church
from corpus.normalize import han_body, han_len, is_han, norm_han, norm_viet
from corpus.output import align_segments, book_stats, mark_duplicates, validate
from corpus.scan import restore_line_breaks
from corpus.segments import Segment, Unit, scan_segments, column_unit, viet_units, is_chapter_title
from build_corpus import assemble


class CorpusTests(unittest.TestCase):
    def book(self):
        return {"file": "chinh/test.pdf", "book": "Kinh Thi (Quyển I)", "type": "scan", "page_offset": 330}

    def test_normalization_retains_real_repetitions_and_extended_han(self):
        self.assertEqual(norm_han("關關⿓龍，𠀀"), "關關龍，𠀀")
        self.assertTrue(is_han("𠀀"))
        self.assertFalse(is_han("fi"))

    def test_unmapped_pua_is_visible_in_all_planes(self):
        self.assertEqual(norm_han("甲\ue001\U000f0001\U00100001"), "甲〓〓〓")
        self.assertEqual(norm_viet("Vie\u0323\u0302t  Nam"), "Việt Nam")

    def test_gale_church_consumes_every_unit_exactly_once(self):
        hu = ["天地玄黃", "宇宙洪荒", "日月盈昃"]
        vu = ["Trời đất", "Huyền vàng", "Vũ trụ rộng lớn", "Mặt trời mặt trăng"]
        links = gale_church(hu, vu, ratio=1., variance=2.)
        self.assertEqual([i for l in links for i in range(l.han_start,l.han_end)], list(range(len(hu))))
        self.assertEqual([i for l in links for i in range(l.viet_start,l.viet_end)], list(range(len(vu))))
        self.assertTrue(all(math.isfinite(l.cost) for l in links))

    def test_gale_church_supports_one_to_many(self):
        links = gale_church(["天地玄黃"], ["Trời đất", "Huyền vàng"], ratio=1., variance=1.)
        self.assertEqual([(l.han_end-l.han_start,l.viet_end-l.viet_start) for l in links], [(1,2)])

    def test_null_alignment_is_not_silently_dropped(self):
        links = gale_church([], ["Dòng dịch không có nguyên văn"])
        self.assertEqual((links[0].han_end,links[0].viet_end),(0,1))
        segment = Segment("empty", [], ["Dòng dịch không có nguyên văn"], [7])
        rows, _ = align_segments([segment], self.book(), 1, "gale_church")
        self.assertIn("viet_only", rows[0]["flags"])

    def test_printed_verse_indices_prevent_length_based_shifts(self):
        links = gale_church(["天地玄黃","宇宙洪荒"], ["Lời dịch dài "*20,"Vũ trụ."],
                            ratio=2.,variance=1.,anchors=[(0,0),(1,1)])
        for link in links:
            for h,v in [(0,0),(1,1)]:
                self.assertEqual(link.han_start<=h<link.han_end,link.viet_start<=v<link.viet_end)

    def test_partial_translation_keeps_missing_verse_as_unmatched(self):
        links = gale_church(["天地玄黃","宇宙洪荒","日月盈昃"],["Trời đất.","Mặt trăng."],
                            ratio=1.,variance=2.,anchors=[(0,0),(2,1)],unmatched_han=[1])
        self.assertTrue(any(l.han_start==1 and l.han_end==2 and l.viet_start==l.viet_end for l in links))

    def test_missing_readings_use_flagged_placeholders(self):
        unit = column_unit({"chars": [("天",0),("地",1)], "readings": [("thiên",0)]}, 7)
        self.assertEqual(unit.readings,["〓","〓"])
        self.assertIn("reading_mismatch",unit.flags)

    def test_source_page_offset_and_original_reading_are_preserved(self):
        segment = Segment("x",[Unit("天地",["thiên","địa"],"Thiên Địa",[7])],["Trời đất."],[7],verse=True)
        rows,_ = align_segments([segment],self.book(),1,"gale_church")
        self.assertEqual(rows[0]["pages"],[337])
        self.assertEqual(rows[0]["phien_am"],"thiên địa")
        self.assertEqual(rows[0]["phien_am_goc"],"Thiên Địa")
        validate(rows)

    def test_long_unpunctuated_paragraph_is_not_labelled_as_one_sentence(self):
        unit = Unit("天地玄黃"*20,["〓"]*80,"",[7])
        rows,_ = align_segments([Segment("p",[unit],["Một câu.","Hai câu.","Ba câu."],[7])],self.book(),1,"gale_church")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["level"],"paragraph")
        self.assertEqual(rows[0]["align"],"1-3")

    def test_two_translation_types_do_not_double_count_han_coverage(self):
        hu=[Unit("天地",["thiên","địa"],"Thiên Địa",[7])]
        segments=[Segment("s",hu,["Trời đất."],[7],kind,True) for kind in ["dich_sat","dich_tho"]]
        rows,_=align_segments(segments,self.book(),1,"gale_church")
        stats=book_stats(self.book(),segments,rows,1,1,[])
        self.assertEqual(stats["source_han"],2)
        self.assertEqual(stats["retained_han"],2)
        self.assertEqual({r["viet_type"] for r in rows},{"dich_sat","dich_tho"})

    def test_commentary_and_cross_page_translation_are_not_mixed_into_poem(self):
        pages=[{"pdf_page":38,"blocks":[
            {"layer":"han","text":"關關雎鳩\n在河之洲"},
            {"layer":"phien_am","text":"1. Quan quan thư cưu.\n2. Tại hà chi châu."},
            {"layer":"dich_sat","text":"1. Đôi chim kêu."}]},
            {"pdf_page":39,"blocks":[{"layer":"dich_sat","text":"2. Trên cồn sông."},
             {"layer":"dich_tho","text":"Đôi chim cùng tiếng gọi nhau."},
             {"layer":"chu_thich","text":"天地 là lời chú giải."}]}]
        segments,_=scan_segments(pages)
        self.assertEqual(len(segments),2)
        self.assertEqual(segments[0].viet,["Đôi chim kêu.","Trên cồn sông."])
        self.assertNotIn("天地","".join(u.text for s in segments for u in s.han))

    def test_projection_preserves_voted_characters(self):
        text="Quan quan thu cuu. Tai ha chi chau."
        restored=restore_line_breaks(text,"Quan quan thư cưu.\nTại hà chi châu.")
        self.assertEqual(" ".join(restored.split()),text)
        self.assertIn("\n",restored)

    def test_exact_duplicates_are_flagged_and_retained(self):
        s=Segment("s",[Unit("天地",["thiên","địa"],"",[7])],["Trời đất."],[7],verse=True)
        rows,_=align_segments([s],self.book(),1,"gale_church")
        extra=dict(rows[0],id="other",extra={})
        mark_duplicates(rows+[extra])
        self.assertIn("duplicate",extra["flags"])

    def test_partial_assembly_cannot_claim_complete_main_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"test.pdf").write_bytes(b"source identity only; no pages extracted yet")
            (root/"config.yaml").write_text("group: 1\n")
            book={"file":"test.pdf","book":"Vi Chánh","type":"text_vertical", "slug":"vi-chanh",
                  "total_pages":3,"page_offset":0}
            config={"group":1,"data_dir":str(root),"_config_path":str(root/"config.yaml"),"corpus":{}}
            rows,stats=assemble(config,[book],root/"cache",root/"out")
            self.assertEqual(rows,[])
            self.assertFalse(stats[0]["complete"])
            self.assertIn("chưa đủ phần chính",(root/"out/report.md").read_text())

    def test_chapter_title_with_name_is_separate_from_body(self):
        self.assertTrue(is_chapter_title("第四篇為政"))
        self.assertFalse(is_chapter_title("孔子曰凡為天下國家者有九經焉"))

    def test_sentence_provenance_retains_only_its_own_pages(self):
        text,pages=viet_units(["Trời đất.","Một câu cắt", "qua trang."],False,[6,6,7])
        self.assertEqual(text,["Trời đất.","Một câu cắt qua trang."])
        self.assertEqual(pages,[[6],[6,7]])

    def test_unrecognized_symbols_in_han_are_visible_instead_of_deleted(self):
        self.assertEqual(han_body("關A雎鳩",preserve_unknown=True),"關〓雎鳩")

    def test_commentary_page_does_not_expand_poem_page_provenance(self):
        segments,_=scan_segments([
            {"pdf_page":38,"blocks":[{"layer":"han","text":"關關雎鳩"},
             {"layer":"phien_am","text":"1. Quan quan thư cưu."},
             {"layer":"dich_sat","text":"1. Đôi chim kêu."}]},
            {"pdf_page":39,"blocks":[{"layer":"chu_thich","text":"Chú giải tiếp theo."}]}])
        self.assertEqual(segments[0].pages,[38])


if __name__ == "__main__":
    unittest.main()
