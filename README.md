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
triển khai lại thuật toán demo. `src/ocr.py` bổ sung công cụ render, cắt vùng
và chạy OCR độc lập; chưa có pipeline corpus hoàn chỉnh. Đầu ra demo chưa đủ
schema cuối cùng; cần bổ sung các trường theo mục 8 của hướng dẫn.

## Cài đặt và chạy OCR tuần 2

Mẫu gồm **11 trang PDF 38–48 của Kinh Thi**, render ở 300 DPI. Bản tham chiếu
được đối chiếu với ảnh và lưu tại `gold/ocr/week2/`; nguồn ảnh có manifest và
SHA-256. Các phép thử cấu hình dùng cùng bộ tham chiếu đã chốt.

### Chạy pipeline bằng một lệnh

Môi trường hiện có `.venv-ocr`. Trên máy mới, dùng `bash scripts/setup_ocr.sh cu128`
để chuẩn bị Python 3.11/PyTorch CUDA. Tesseract được cài cục bộ trên Arch Linux
x86_64 bằng `python3 scripts/setup_tesseract.py`; model và thư viện nằm trong
`.cache/ocr/tesseract/`. Script cố định phiên bản, kiểm SHA-256 gói và lưu
revision của `tessdata_best`.

```sh
source .venv-ocr/bin/activate
python src/ocr_week2_pipeline.py
```

Lệnh đọc phần `ocr` của `config.yaml`, khôi phục ảnh/crop còn thiếu từ PDF gốc,
chạy lần lượt các công cụ, voting rồi xuất bảng CER. Trên máy mới, đặt PDF
được cấp vào đường dẫn `ocr.sample_pdf`; ảnh không cần đưa lên git.
`layout/regions.json` giữ tọa độ crop, kích thước, DPI và SHA-256 để kiểm tra
đúng mẫu đã chấm (bản render hiện dùng Poppler 26.10.0; Pillow cố định trong
requirements). Các kết quả cùng ảnh/cấu hình được dùng lại từ cache; thêm
`--overwrite` để suy luận lại toàn bộ. Khi bị ngắt, chạy lại cùng lệnh để tiếp tục.

```sh
# Xem các lệnh sẽ chạy
python src/ocr_week2_pipeline.py --dry-run

# Chỉ dựng lại voting và CER từ OCR thô hiện có
python src/ocr_week2_pipeline.py --skip-ocr
```

### Cấu hình đã chọn

| Công cụ | Thiết bị | Cấu hình |
| --- | --- | --- |
| PaddleOCR 3.3.2 | CPU | Bộ Hán nhận trực tiếp từng dòng; vùng Việt dùng pipeline gốc `vi` |
| GOT-OCR2 | CUDA | `scan`: tách dòng Hán, giữ nguyên khối Việt; tối đa 2.048 token |
| Qwen2.5-VL-7B | CUDA, NF4 4-bit | `balanced`: tách dòng Hán, giữ nguyên khối Việt; CPU offload; 512 token, 401.408 pixel |
| Tesseract 5.5.4 | CPU | `balanced`: `chi_tra` cho Hán; `vie` cho Việt; `vie+chi_tra` cho chú giải |

Seed là 42. Revision hai VLM được cố định trong `src/ocr.py`; Tesseract dùng
`tessdata_best` commit `e12c65a915945e4c28e237a9b52bc4a8f39a0cec`.
Các model có sẵn chạy suy luận. Phiên bản thư viện ở `requirements-ocr.txt`
và metadata từng lượt chạy nằm trong `out/ocr/week2/runs/`.

Tiền xử lý Hán gồm cắt dòng bằng hình ảnh, phóng gấp đôi, thêm viền 16 pixel
và autocontrast. Qwen dùng `repetition_penalty=1.0` khi đọc dòng Hán để giữ
chữ lặp; phần Việt giữ ảnh khối và prompt gốc. Tesseract dùng PSM 7 cho dòng
Hán, PSM 6 cho khối Việt. Tham khảo [hướng dẫn chất lượng Tesseract](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)
và [model có sẵn tessdata_best](https://github.com/tesseract-ocr/tessdata_best).

Thử tách mọi dòng Việt làm CER Việt của Paddle tăng từ 15,21% lên 21,37%,
nên giữ cấu hình Paddle gốc. Tesseract giữ khối Việt đạt 3,70%, tốt hơn
11,87% của biến thể tách dòng. Các phép thử và lý do lựa chọn được ghi trong
`out/ocr/week2/scan_profile_probe.md`.

### Voting theo đúng yêu cầu hướng dẫn

Căn chỉnh ký tự bằng **Levenshtein với chi phí đơn vị**. Mỗi công cụ được
căn với cùng chuỗi trục của công cụ có CER tốt hơn để giảm lệch tích lũy
(`star` alignment). Ký tự trống là một phiếu bỏ ký tự. Ở mỗi vị trí lấy
ký tự có nhiều phiếu nhất; hòa thì theo công cụ có CER thấp hơn.

- **Hán:** cả 4 công cụ bỏ phiếu.
- **Việt:** PaddleOCR, Qwen và Tesseract bỏ phiếu; GOT có CER Việt cao nhất
  nên được giữ để so sánh thay vì tham gia phiếu Việt.

Mỗi hệ chữ đều có ít nhất **3 công cụ**. Việc chọn hệ chữ dựa vào Unicode
của chuỗi OCR trục. Đầu vào suy luận gồm ảnh và cấu hình; tham chiếu dùng để
đo CER và xếp thứ tự khi hòa. Các tập công cụ được cố định cho cả 11 trang.
Cấu hình và hash đầu vào được ghi trong `out/ocr/week2/vote_settings.json`.

### Kết quả đã tính lại trên 11 trang

| Kết quả | CER Hán | CER Việt | CER gộp |
| --- | ---: | ---: | ---: |
| PaddleOCR | 33,20% | 15,21% | 15,71% |
| GOT-OCR2 | 39,75% | 22,82% | 23,30% |
| Qwen2.5-VL | 9,02% | 0,89% | 1,12% |
| Tesseract | 41,80% | 3,70% | 4,78% |
| **Voting** | **8,61%** | **0,80%** | **1,02%** |

Voting có **21/244 lỗi Hán** và **67/8.405 lỗi Việt**, thấp hơn từng công cụ
đơn lẻ trên mẫu. Trước hiệu chỉnh, voting là 12,30% Hán và 3,28% Việt;
CER gộp giảm từ 3,54% xuống 1,02%. Riêng tầng Hán nguyên văn, voting đạt
3,57% (6/168). Một số tầng riêng vẫn có thể kém Qwen, như phiên âm và chú giải.

CER dùng NFC; khi chấm theo hệ chữ bỏ khoảng trắng, giữ chữ hoa, dấu câu và
dấu thanh. Hán gồm mọi ký tự CJK trong tiêu đề, nguyên văn và chú giải;
Việt gồm các ký tự còn lại. `can_kiem_tra` được loại khỏi CER. Bảng chi tiết
nằm ở `out/ocr/week2/comparison.md`.

Thứ tự hòa và lựa chọn cấu hình được hiệu chỉnh trên chính tập 11 trang;
đây là kết quả trên mẫu hiệu chỉnh, chưa phải đánh giá độc lập cho cả sách.

### Bản tham chiếu và đầu ra

Mỗi file `page-XXXX.json` có các mảng `tieu_de`, `han`, `phien_am`, `dich_sat`,
`dich_tho`, `chu_thich`, `can_kiem_tra`. Số trang lấy từ tên file; metadata chạy
được lưu riêng. Bản tham chiếu giữ cách in nguồn; sửa tay ghi trong `patches/*.tsv`.

```text
gold/ocr/week2/page-XXXX.json           # bản tham chiếu
out/ocr/week2/
  pages/{paddleocr,got-ocr2,qwen2.5-vl,tesseract,voting}/page-XXXX.json
  runs/<model>.json                    # cấu hình, OCR thô và cache
  comparison.md                       # CER theo hệ chữ và từng tầng
  vote_settings.json                  # phương pháp, công cụ, hash đầu vào
  scan_profile_probe.md               # biên bản thử cấu hình
  layout/regions.json                 # tọa độ, thứ tự, nguồn và hash crop
  images/                             # ảnh trang, được gitignore
  layout/images/                      # ảnh crop, được gitignore
```

`viewer.html` cũ thuộc chế độ archive và chưa phản ánh đầu ra mới theo model.
JSON trong `pages/<model>/` là OCR thô dùng để đánh giá. CLI giữ `--format reference`
cho lệnh chạy riêng; `--profile balanced` chọn cấu hình giữ khối Việt.
Qwen có thể dùng `--native-cache <run.json>` để tái dùng OCR khối Việt nếu
model, revision, ảnh, prompt, seed, độ phân giải và chế độ suy luận tương đương;
nguồn cache được lưu ở từng record. Cấu hình Hán mới vẫn chạy trên ảnh.

Với mẫu mới, chuẩn bị ảnh và bố cục trước khi chạy OCR theo tầng:

```sh
python src/ocr.py render --pdf "chinh/Kinh Thi - Ta Quang Phát 1 (tr1-346).pdf" --pages 38-48 --dpi 300
python src/ocr.py run --engine paddleocr --lang chinese_cht --device cpu --input out/ocr/week2/images
python src/layout.py
```

`src/layout.py` dùng PP-DocLayout cộng luật cho bố cục ngang Kinh Thi, xuất
crop và `regions.json`. Corpus/căn chỉnh câu cuối kỳ tiếp tục triển khai ở
Tuần 3–5; `out/corpus.jsonl` giữ schema chung của đề.

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
- **Tuần 2:** hoàn thành đầu ra OCR trên 11 trang PDF 38–48: tham chiếu,
  bốn công cụ có sẵn, voting đa số (4 phiếu Hán/3 phiếu Việt) và CER riêng.
  Voting đạt **8,61% Hán, 0,80% Việt**, thấp hơn từng công cụ trên mẫu.
  Cấu hình đã chốt trong `config.yaml`; `src/ocr_week2_pipeline.py` đọc và chạy
  toàn bộ bước khôi phục ảnh/crop–OCR–voting–CER. Các số liệu là kết quả trên mẫu hiệu chỉnh.
- **Tuần 3–5:** hoàn thiện corpus chính, bộ gold, đánh giá và cải tiến căn chỉnh,
  rồi xử lý phần mở rộng. `out/corpus.jsonl`, `gold/gold.jsonl`,
  `eval/eval.py`, `out/source_errors.tsv` hiện còn là file khung.

| Chỉ số cuối kỳ | Hiện tại | Yêu cầu |
| --- | --- | --- |
| CER OCR theo Hán/Việt | Voting Hán 8,61%, Việt 0,80% trên 11 trang | Đã thấp hơn từng công cụ trên mẫu hiệu chỉnh |
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
- `report.pdf`: báo cáo Tuần 1 và kết quả OCR/voting/CER Tuần 2 đã cập nhật.

Giữ chữ Hán phồn thể; chuẩn hóa bộ thủ và xử lý PUA theo hướng dẫn,
NFC cho tiếng Việt và phiên âm. Giữ riêng dịch nghĩa (`dich_sat`), dịch thơ
(`dich_tho`), chú giải; gắn cờ cặp nghi ngờ. Không sửa PDF gốc hoặc commit
PDF/ảnh OCR. Ghi seed, phiên bản thư viện và revision mô hình khi triển khai;
chỉ dùng mô hình có sẵn để suy luận, không huấn luyện/fine-tune.

Theo mục 7 của hướng dẫn, Git giữ mã nguồn và đầu ra: TXT/JSON OCR,
corpus, gold, file đánh giá, patches và `report.pdf`. `.gitignore` loại PDF
nguồn, ảnh OCR/crop, môi trường, cache, trọng số model, log và các file khóa/
thông tin đăng nhập thông dụng. Không ignore toàn bộ `out/` hoặc `gold/`.
