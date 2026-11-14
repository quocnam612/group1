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

### Các bước tiếp theo

1. **Kiểm tra môi trường:** kích hoạt `.venv-ocr`, sau đó chạy `doctor`;
   kiểm tra đủ thư viện và `CUDA available: True` trước khi chạy hai VLM.
2. **Mẫu đã chọn:** trang PDF 38–48 của Kinh Thi, gồm 11 trang;
   chép bản tham chiếu đúng theo ảnh, tách Hán và Việt,
   giữ riêng phiên âm, dịch nghĩa, dịch thơ và chú giải.
3. **Thử từng công cụ trên một ảnh:** thêm `--limit 1` vào các lệnh OCR bên
   dưới, kiểm tra file TXT/JSON rồi mới chạy đủ mẫu. Chạy các công cụ lần lượt.
4. **Đánh giá tuần 2:** dùng cùng ảnh/crop và bản tham chiếu cho cả ba công cụ,
   sau đó thực hiện voting và đo CER riêng Hán/Việt. Voting và CER chưa được
   triển khai trong `src/ocr.py`.

Chạy các lệnh tại root project. Bộ công cụ gồm **PaddleOCR 3.3.2**, **Qwen2.5-VL-7B-Instruct**
và **GOT-OCR-2.0-hf**. Baseline cũ trong `tutorials/` được giữ riêng.

### Môi trường

Máy hiện có RTX 4060 Laptop 8 GB. Dùng Python 3.11 trong `.venv-ocr`, PyTorch
CUDA 12.8 cho hai VLM; PaddleOCR dùng CPU. Qwen mặc định lượng tử hóa NF4 4-bit
và giới hạn số pixel để giảm VRAM. Lệnh bên dưới thêm CPU offload để chừa VRAM
trên GPU 8 GB đang dùng cho màn hình. Không chạy Qwen và GOT đồng thời trên GPU này.

```sh
bash scripts/setup_ocr.sh cu128
source .venv-ocr/bin/activate
python src/ocr.py doctor
```

Script cần `uv` đã được cài; nó giữ Python và cache trong `.cache/`, không đổi
môi trường baseline. `requirements-ocr.txt` cố định các thư viện chính;
`out/ocr/environment.txt` ghi toàn bộ phiên bản sau khi cài. Trên máy chỉ có CPU,
dùng `bash scripts/setup_ocr.sh cpu`; Qwen 7B CPU cần rất nhiều RAM và không được
tự chạy mặc định. `doctor` kiểm tra thư viện/CUDA, không xác nhận độ chính xác OCR.

### Ảnh đầu vào

Mẫu OCR hiện chọn trang PDF **38–48**, gồm **11 trang**, render ở 300 DPI:

```sh
python src/ocr.py render --pdf "chinh/Kinh Thi - Ta Quang Phát 1 (tr1-346).pdf" --pages 38-48 --dpi 300 --output out/ocr/week2/images
```

Ảnh nằm trong `out/ocr/week2/images/`; các JSON cạnh ảnh ghi PDF nguồn,
SHA-256, trang PDF và DPI. Thư mục riêng này giữ đúng phạm vi đã chọn;
`pages.json` liệt kê 11 trang. Các trang đã render cùng cấu hình được giữ lại.

Để tách vùng Hán/Việt cho đánh giá, có thể cắt theo tọa độ tương đối 0–1.
Ví dụ sau cắt khối Hán ở trang 38; cần xem lại ảnh crop trước khi dùng làm mẫu:

```sh
python src/ocr.py crop --input out/ocr/week2/images/page-0038.png --box 0.10 0.23 0.34 0.405 --output out/ocr/week2/images/crops/page-0038-han.png
```

Dùng **cùng ảnh/crop và bản tham chiếu** cho cả ba công cụ. Không sửa văn bản
OCR bằng tay trước khi đo CER. Trang 44 có cả đầu bài thứ hai; giữ phạm vi
đánh giá thống nhất với bản chép tay.

### Chạy ba công cụ

#### PaddleOCR — hai cấu hình ngôn ngữ của cùng một công cụ

```sh
python src/ocr.py run --engine paddleocr --lang chinese_cht --device cpu --input out/ocr/week2/images --output out/ocr/week2/paddleocr/han
python src/ocr.py run --engine paddleocr --lang vi --device cpu --input out/ocr/week2/images --output out/ocr/week2/paddleocr/viet
```

`chinese_cht` cho chữ Hán phồn thể, `vi` cho tiếng Việt. Khi đo CER theo vùng,
thay `--input` bằng thư mục crop phù hợp. Hai cấu hình này không được tính là
hai công cụ độc lập; script giữ đầu ra riêng, không tự ghép hai bản nhận dạng.

#### GOT-OCR2

```sh
python src/ocr.py run --engine got-ocr2 --device cuda:0 --input out/ocr/week2/images --output out/ocr/week2/got-ocr2
```

#### Qwen2.5-VL 7B — 4-bit cho GPU 8 GB

```sh
python src/ocr.py run --engine qwen2.5-vl --device cuda:0 --quantization 4bit --cpu-offload --input out/ocr/week2/images --output out/ocr/week2/qwen2.5-vl
```

`--cpu-offload` giữ trọng số embedding và lớp đầu ra trong RAM, chuyển lên GPU
khi cần; chậm hơn nhưng giảm VRAM thường trực. Tùy chọn này chỉ dùng với Qwen
4-bit CUDA. Cấu hình chỉ nạp GPU đã gặp lỗi hết VRAM trên máy hiện tại.
Chạy lại dùng model đã cache, không cần xóa cache hoặc tải lại trọng số.

Thêm `--limit 1` để thử một ảnh trước. Mặc định tối đa 4.096 token đầu ra.
JSON gắn `possibly_truncated` nếu chạm giới hạn; khi đó cần xem lại, cắt vùng
hoặc tăng `--max-new-tokens`. Qwen mặc định `--max-pixels 401408`; tăng độ phân
giải làm tăng VRAM, vì vậy crop các khối chữ nhỏ thường phù hợp hơn cho GPU 8 GB.

### Đầu ra, model và chạy tiếp

```text
out/
  corpus.jsonl                 # đầu ra corpus cuối cùng
  source_errors.tsv            # lỗi trong sách nguồn
  ocr/
    environment.txt            # phiên bản thư viện đã cài
    week2/
      images/                  # ảnh 38–48, crop và metadata; không commit
      paddleocr/han/            # kết quả TXT/JSON
      paddleocr/viet/
      got-ocr2/                # tạo khi chạy công cụ tương ứng
      qwen2.5-vl/
```

- Mỗi ảnh có `.txt` và `.json`, gồm SHA-256 ảnh, công cụ, cấu hình, thời gian.
  Paddle giữ thêm kết quả gốc (vùng chữ/độ tin cậy); VLM ghi model và commit
  thực tế đã dùng. Hai model mặc định được cố định commit trong `src/ocr.py`.
  Qwen chỉ được yêu cầu chép nguyên văn, không dịch/sửa lỗi.
- Lần chạy đầu tải model từ nhà cung cấp vào `.cache/ocr/`. Qwen 7B tải trọng
  số lớn dù nạp 4-bit; cần mạng và đủ dung lượng đĩa. Commit đã ghi có thể
  truyền lại bằng `--revision <SHA>` cho lần tái lập.
- Lần chạy tiếp bỏ qua kết quả đã có cùng ảnh và tham số. Khi đổi tham số,
  dùng thư mục đầu ra mới hoặc `--overwrite`. Các file ảnh/crop không đưa lên Git.
- Các lệnh ở đây nhận tham số CLI, **chưa đọc `config.yaml`**. Chúng xuất OCR
  thô, chưa thực hiện tách tầng, voting hoặc tính CER.
- Nếu `doctor` báo CUDA không khả dụng trong sandbox nhưng `nvidia-smi` ngoài
  sandbox nhận GPU, chạy lệnh OCR trong terminal thường của máy.

API tham khảo: [PaddleOCR](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html),
[Qwen2.5-VL](https://huggingface.co/docs/transformers/v4.57.1/model_doc/qwen2_5_vl),
[GOT-OCR2](https://huggingface.co/docs/transformers/v4.57.1/model_doc/got_ocr2),
[bitsandbytes](https://huggingface.co/docs/transformers/v4.57.1/quantization/bitsandbytes).

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

Theo mục 7 của hướng dẫn, Git giữ mã nguồn và đầu ra: TXT/JSON OCR,
corpus, gold, file đánh giá, patches và `report.pdf`. `.gitignore` loại PDF
nguồn, ảnh OCR/crop, môi trường, cache, trọng số model, log và các file khóa/
thông tin đăng nhập thông dụng. Không ignore toàn bộ `out/` hoặc `gold/`.
