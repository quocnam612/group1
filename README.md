# Nhóm 1 — Corpus song ngữ Hán–Việt

Môn **Nhập môn xử lý ngôn ngữ tự nhiên**. Mục tiêu: xây pipeline từ PDF đến
các cặp chữ Hán, phiên âm Hán Việt và bản dịch Việt theo hướng dẫn CV18.

| MSSV | Thành viên | Mã lớp | Nhiệm vụ |
| --- | --- | --- | --- |
| 24120098 | Nguyễn Quốc Nam | 24_25 | Viết báo cáo, triển khai mô hình OCR |
| 23120378 | Nguyễn An Trí | 24_25 | Viết báo cáo |

## Dữ liệu và cấu hình

`manifest.json` ghi loại PDF, phần được giao và `page_offset`.
`config.yaml` khai báo đủ 4 file chính và 3 file mở rộng, cùng các tham số dự kiến.

| Phần | Sách / file | Trang PDF được giao | Cách xử lý |
| --- | --- | --- | --- |
| Chính | Kinh Thi, Quyển I | 1–346 | OCR; tách Hán, phiên âm, dịch nghĩa, dịch thơ và chú giải |
| Chính | Vi Chánh | 1–330 | Lớp text in dọc; cần cải thiện căn chỉnh cấp câu |
| Chính | Đạo Đức Kinh | 1–231 | Lớp text in dọc |
| Chính | Tăng Quảng Hiền Văn | 1–122 | Lớp text in dọc |
| Mở rộng | Long Thư — Hán + phiên âm | 1–226 | Lớp text in ngang; căn chỉnh với bản dịch Việt |
| Mở rộng | LongThuTinhDo — bản dịch Việt | 1–155 | Font hỏng bảng mã; cần OCR |
| Mở rộng | Long Thư — bản khắc gỗ | 1–148 | Đối chiếu, đánh giá OCR chữ Hán |

Các đường dẫn trong config tính từ root project. Trường `pages` của đầu ra
dùng trang PDF cộng `page_offset`; số trang in trên sách được ghi riêng nếu cần.
`source: text` gồm cả in dọc và in ngang; loại chi tiết nằm trong manifest.

## Môi trường và cách chạy baseline

Cần Python ≥ 3.9, Poppler (`pdftoppm`, `pdftotext`) và `pdfplumber`.
Python 3.11 được khuyến nghị khi chuẩn bị thêm các thư viện OCR.

```sh
# Cài Poppler: Ubuntu/Debian dùng sudo apt install poppler-utils;
# macOS dùng brew install poppler; Arch Linux dùng sudo pacman -S poppler.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pdfplumber==0.11.10
```

Trên PowerShell, kích hoạt môi trường bằng `.venv\Scripts\Activate.ps1`.

Baseline đã chạy và được giữ tại `tutorials/han_viet_corpus_demo/out/`.
Mã demo được cấp riêng trong `tutorials/han_viet_corpus_demo/`; PDF gốc nằm
ở `chinh/`, `mo_rong/`. Các thư mục này đang bị Git bỏ qua, nên cần bổ sung
từ bộ tài liệu được giao khi dùng một bản clone mới.

Các lệnh dưới đây dành cho khi cần chạy lại, thực hiện tại root project;
đầu ra mới được tách khỏi baseline đã lưu:

```sh
# Thử 20 trang đầu của mỗi sách text_vertical
python tutorials/han_viet_corpus_demo/build_corpus.py --group . --pages 1-20 --out out/demo_preview

# Chạy đủ 3 sách text_vertical
python tutorials/han_viet_corpus_demo/build_corpus.py --group . --out out/demo_rerun

# Kiểm tra thứ tự chữ và các tầng ở một khoảng trang
python tutorials/han_viet_corpus_demo/debug_stream.py "chinh/Vi Chánh (tr1-330).pdf" 4 9
```

Mở `tutorials/han_viet_corpus_demo/out/viewer.html` bằng trình duyệt để xem
baseline đã lưu. Mỗi lần chạy tạo `corpus.jsonl`, `char_readings.tsv`,
`report.md`, `viewer.html` trong thư mục được chỉ định bằng `--out`.

Demo **chỉ đọc manifest**, chưa đọc `config.yaml`, chưa có OCR và không xử lý
file `text_horizontal`/`text_broken`. Các tham số OCR, chấm câu, embedding
và seed trong config dành cho pipeline nhóm sẽ triển khai trong `src/`.

## Phương pháp và phần kế thừa

Baseline dùng nguyên mã demo được cấp trong tài liệu CV18:

- `hvcorpus/extract_vertical.py`: trích xuất tọa độ, gom cột và tách tầng.
- `hvcorpus/normalize.py`: chuẩn hóa ký tự Hán, tiếng Việt và phiên âm.
- `hvcorpus/align.py`: gom đoạn, nối qua trang, Gale–Church và mốc âm Hán Việt.
- `build_corpus.py`, `viewer.py`: gắn cờ, thống kê và hiển thị kết quả.

Nhóm đã chạy baseline, kiểm tra mẫu và ghi nhận sai lệch; chưa tuyên bố tự
triển khai lại thuật toán demo. `src/` hiện chưa có pipeline riêng. Đầu ra demo
chưa đủ schema cuối cùng; cần bổ sung các trường theo mục 8 của hướng dẫn.

## Kết quả và tiến độ

| Sách | Số cặp | Cấp câu | Cấp đoạn |
| --- | ---: | ---: | ---: |
| Vi Chánh | 217 | 115 | 102 |
| Đạo Đức Kinh | 1.200 | 1.193 | 7 |
| Tăng Quảng Hiền Văn | 709 | 709 | 0 |
| **Tổng** | **2.126** | **2.017** | **109** |

Có 1.886 cặp không gắn cờ (khoảng 89%); đây không phải precision căn chỉnh.
Số liệu lấy từ `tutorials/han_viet_corpus_demo/out/report.md`.

- **Tuần 1:** ghi nhận 24 trang của 4 sách chính; chi tiết ở
  `tutorials/reports/week1_page_review.md` và `report.pdf`.
  Trang 7 Đạo Đức Kinh chỉ đối chiếu một phần; trang 44 Kinh Thi chỉ lấy
  phần thuộc bài Quan thư.
- **Tuần 2:** chuẩn bị 10 trang tham chiếu; chạy ít nhất 3 công cụ OCR và voting;
  đo CER riêng Hán/Việt. Chưa có số liệu OCR/CER.
- **Tuần 3–5:** hoàn thiện corpus chính, bộ gold, đánh giá và cải tiến căn chỉnh,
  rồi xử lý phần mở rộng. `out/corpus.jsonl`, `gold/gold.jsonl`,
  `eval/eval.py`, `out/source_errors.tsv` hiện còn là file khung.

| Chỉ số cuối kỳ | Hiện tại | Yêu cầu |
| --- | --- | --- |
| CER từng công cụ và voting, riêng Hán/Việt | Chưa đo | Voting thấp hơn từng công cụ đơn lẻ |
| Precision / recall căn chỉnh | Chưa đo trên gold | ≥90% / ≥80% |
| Độ phủ chữ Hán | Chưa đo | ≥85% phần được giao |
| Tỉ lệ cấp câu | 2.017/2.126 cặp, khoảng 94,9% trong demo | Cần đánh giá thêm theo tỉ lệ chữ Hán từng sách |
| Gold / độ đồng thuận | Chưa gán | ≥100 cặp/người; 30 cặp chung, Cohen's κ ≥0,8 |

Điều kiện cấp câu theo chữ Hán: sách thơ ≥95%; Vi Chánh tăng ít nhất
30 điểm phần trăm so với baseline. Không dùng tỉ lệ số cặp trong bảng trên
để thay cho tỉ lệ chữ Hán.

## Đầu ra và quy ước

- `out/corpus.jsonl`: corpus theo schema chung; trường bổ sung đặt trong `extra`.
- `gold/gold.jsonl`: cặp gán tay cùng schema, thêm `annotator`.
- `eval/eval.py`: đánh giá precision/recall khi triển khai.
- `out/source_errors.tsv`: lỗi trong sách nguồn; sửa tay lưu riêng vào `patches/*.tsv`.
- `report.pdf`: báo cáo tiến độ, gồm Tuần 1 và kế hoạch Tuần 2.

Giữ chữ Hán phồn thể; chuẩn hóa bộ thủ và xử lý PUA theo hướng dẫn,
NFC cho tiếng Việt và phiên âm. Giữ riêng dịch nghĩa (`dich_sat`), dịch thơ
(`dich_tho`), chú giải; gắn cờ cặp nghi ngờ. Không sửa PDF gốc hoặc commit
PDF/ảnh OCR. Ghi seed, phiên bản thư viện và revision mô hình khi triển khai;
chỉ dùng mô hình có sẵn để suy luận, không huấn luyện/fine-tune.

## Build báo cáo

Cần TeX Live hoặc MiKTeX với `latexmk`, `pdflatex` và các gói trong
`latex/hcmus-report-template.sty` (bao gồm `vietnam`), `tabularx`, `booktabs`.
Chạy tại root:

```sh
latexmk
```

PDF xuất tại **`report.pdf`**; file tạm nằm trong `build/latex/`.
VS Code/LaTeX Workshop dùng recipe **Build NLP report**. Nguồn theo tuần ở
`latex/content/week1.tex`, `week2.tex`; thông tin bìa và ngày tự động ở
`latex/report.tex`, thành viên ở `latex/content/member.tex`.
Nguồn LaTeX và cấu hình build hiện được giữ ngoài Git theo `.gitignore`.
