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

Để chạy lại và so với bản tham chiếu, dùng **`--format reference`** như các lệnh
bên dưới. Mỗi model xuất một JSON cho mỗi trang ở `out/ocr/week2/pages/<model>/`.
File chỉ chứa các mảng nội dung giống `gold/ocr/week2/`, không chứa số trang,
bbox hay cấu hình. Văn bản lấy trực tiếp từ OCR của model, giữ nguyên lỗi;
metadata và dữ liệu chạy tiếp lưu riêng tại `out/ocr/week2/runs/<model>.json`.

Chế độ `archive` cũ lưu **một JSON cho mỗi trang** tại `out/ocr/week2/pages/`.
Để dò nội dung của chế độ này, mở **[viewer.html](out/ocr/week2/viewer.html) bằng trình duyệt**:
ảnh và văn bản đặt cạnh nhau, chọn trang/tầng, tìm không dấu và bấm khung ảnh
để đối chiếu. Có thể chuyển giữa bản đã đối chiếu và OCR thô của từng công cụ.

Trong JSON, phần **`content` ở đầu file** là các mảng dòng để đọc nhanh,
không cần dò qua bbox và metadata. Mở [trang 38](out/ocr/week2/pages/page-0038.json),
[trang 40](out/ocr/week2/pages/page-0040.json) hoặc
[trang 44](out/ocr/week2/pages/page-0044.json).
Tiêu đề, thơ Hán, phiên âm, dịch và chú giải nằm trong cùng file, có nhãn riêng.

### Cấu trúc JSON chế độ archive

- `content`: các dòng văn bản theo từng tầng, đặt đầu file; `content_status` cho biết trạng thái.
- `source`: PDF, số trang, DPI, ảnh nguồn và SHA-256.
- `layers`: `tieu_de`, `han`, `phien_am`, `dich_sat`, `dich_tho`, `chu_thich`,
  `so_trang`, `can_kiem_tra`. Mỗi tầng có `text`, `status`, `regions`.
- `layers.<tầng>.regions[].ocr`: kết quả thô riêng của từng công cụ, gồm văn bản,
  cấu hình, phiên bản/revision, thời gian, bbox, điểm nhận diện và cờ cảnh báo.
- `fullpage_ocr`: các kết quả OCR toàn trang khi có; không trộn vào thơ Hán.
- `layout`: tọa độ dòng, khối bố cục và các cặp Hán–phiên âm đề xuất.

`content`/`text` là bản xem: ưu tiên bản sửa đã đối chiếu ảnh, rồi PaddleOCR đúng
ngôn ngữ, Qwen/GOT; **đây không phải lựa chọn theo CER**.
Các phiên bản OCR khác vẫn được giữ nguyên trong `ocr` để so sánh.
`text_source` cho biết `source_patch`, công cụ hoặc `layout_hint`.

Các trạng thái cần phân biệt:

| `status` | Ý nghĩa |
| --- | --- |
| `ocr_unreviewed` | Có OCR riêng trên crop, chưa kiểm tay/đo CER. |
| `source_checked` | Nội dung đã đối chiếu ảnh, có bản sửa riêng trong `patches/*.tsv`. |
| `mixed_sources` | Có cả nội dung đã đối chiếu và phần chưa kiểm tay. |
| `hint_only` | Mới có gợi ý từ bố cục/OCR cũ, chưa có OCR riêng trên crop. |
| `mixed_ocr_and_hints` | Tầng gồm cả vùng đã OCR riêng và vùng mới có gợi ý. |
| `not_present` | Không có vùng thuộc tầng này trên trang. |

Tiêu đề Hán nằm trong `layers.tieu_de.regions` với `layer: "tieu_de_han"`.
Không tính tiêu đề thành dòng thơ. Chữ Hán xen trong chú giải được giữ trong
`chu_thich`. Dịch nghĩa và dịch thơ không trộn với nhau.

Lượt chạy trước đã gom 11 trang PDF **38–48**, gồm 133 vùng và 32 cặp Hán–phiên âm đề xuất,
với 123 kết quả OCR crop: PaddleOCR trên 9 vùng thơ Hán và 3 tiêu đề Hán;
Qwen trên một vùng Hán, 31 tiêu đề Latin và đủ **79 vùng tiếng Việt** gồm
9 vùng phiên âm, 27 vùng dịch nghĩa, 17 vùng dịch thơ, 26 vùng chú giải.
Đã đối chiếu 34 crop tiêu đề với ảnh và toàn bộ 11 vùng tiếng Việt trang 40;
bản sửa nằm trong `patches/ocr_titles.tsv` và `patches/ocr_vietnamese_page40.tsv`.
Sau đó nhận thêm ảnh đầy đủ của PDF trang 38–48, đối chiếu nội dung các tầng và
cập nhật bản tham chiếu. `gold/ocr/week2/image_manifest.json` ghi thứ tự ảnh,
trang PDF và SHA-256 để truy nguyên tập ảnh; ảnh không được chép vào repo.
Các file toàn trang OCR cũ không còn trên ổ đĩa; bố cục và kết quả crop được giữ
nguyên. JSON archive cũ đã dọn khỏi `pages/`, viewer vẫn là bản xem lượt trước.
Ba thư mục model hiện giữ OCR thô theo format tham chiếu; voting là đầu ra riêng.

### Bản tham chiếu OCR

Bản tham chiếu chép tay nằm tại `gold/ocr/week2/page-0038.json` đến
`page-0048.json`, đối chiếu với 11 ảnh do người dùng cung cấp.
Mỗi file chỉ có các mảng dòng `tieu_de`, `han`, `phien_am`, `dich_sat`,
`dich_tho`, `chu_thich`, `can_kiem_tra` ở cấp ngoài cùng. Số trang lấy từ tên
file; metadata bố cục và cấu hình chạy được giữ ở kết quả OCR trong `out/`.
`can_kiem_tra` chứa nhiễu chưa phân loại và bị loại khỏi CER. Bản tham chiếu giữ
cách viết và lỗi in nhìn thấy trong sách; không lấy nội dung đã chuẩn hoá để
thay cho cách in nguồn. Khi chấm, so bản tham chiếu với OCR thô của từng công cụ.

### Voting và CER tuần 2

Chạy voting và dựng lại bảng CER trên cùng tập trang bằng:

```sh
python src/ocr_vote.py --pages 38-48
python src/ocr_week2_report.py --pages 38-48
```

Voting căn chỉnh ký tự bằng Levenshtein, chọn đa số và xử lý hòa theo CER thấp
nhất trên tập trang này. Đầu ra nằm ở `out/ocr/week2/pages/voting/`; cấu hình
và thứ tự ưu tiên được ghi ở `out/ocr/week2/vote_settings.json`. Vì tie-break
dùng chính tập đang chấm, CER là số liệu hiệu chỉnh, không phải holdout.
`comparison.md` tách riêng ký tự Hán và phần Việt, đồng thời có bảng theo tầng.

### Môi trường

Ba công cụ: **PaddleOCR 3.3.2**, **Qwen2.5-VL-7B-Instruct**, **GOT-OCR-2.0-hf**.
Máy hiện có RTX 4060 Laptop 8 GB; môi trường đã cài tại `.venv-ocr`.

```sh
source .venv-ocr/bin/activate
python src/ocr.py doctor
```

Trên máy mới, chạy `bash scripts/setup_ocr.sh cu128` trước. Script dùng Python
3.11, PyTorch CUDA 12.8 và cache `.cache/`; không đổi môi trường baseline.
`requirements-ocr.txt` cố định thư viện; `out/ocr/environment.txt` lưu phiên bản
đã cài. PaddleOCR chạy CPU. Qwen dùng NF4 4-bit và CPU offload; không chạy
Qwen và GOT đồng thời trên GPU 8 GB. Máy chỉ có CPU dùng setup `cpu`, nhưng
Qwen 7B cần nhiều RAM và chỉ chạy CPU khi thêm `--allow-cpu`.

### Chuẩn bị ảnh và bố cục

Các ảnh 38–48 và bố cục hiện đã có; lệnh giống cấu hình sẽ dùng lại kết quả.

```sh
python src/ocr.py render --pdf "chinh/Kinh Thi - Ta Quang Phát 1 (tr1-346).pdf" --pages 38-48 --dpi 300
python src/layout.py
```

`src/layout.py` đọc/ghi cùng thư mục `pages/`; ảnh crop nằm tại `layout/images/`.
Layout/OCR tự cập nhật [viewer.html](out/ocr/week2/viewer.html). Có thể dựng lại
bản xem mà không chạy model:

```sh
python src/review.py
```

Khi bắt đầu từ trang mới, chạy PaddleOCR toàn trang để lấy tọa độ dòng trước
khi chạy layout:

```sh
python src/ocr.py run --engine paddleocr --lang chinese_cht --device cpu --input out/ocr/week2/images
python src/layout.py --overwrite
```

Kết quả toàn trang được lưu trong `fullpage_ocr` của từng JSON. Các trang hiện
có vẫn dùng được tọa độ dòng đã lưu khi kết quả toàn trang cũ không còn.
Model bố cục [PP-DocLayout_plus-L](https://www.paddleocr.ai/main/en/version3.x/module_usage/layout_detection.html)
chỉ nhận loại khối, không tự phân biệt Hán/Việt. Script bổ sung luật theo tọa độ,
chữ OCR gợi ý và các tiêu đề. Quy tắc hiện dành cho bố cục ngang Kinh Thi.
Trang 44 có vùng tiêu đề khôi phục từ vị trí tiêu đề Việt, được gắn cờ cần kiểm tra.

### OCR từng vùng bằng ba công cụ

Chạy từ root project, trong môi trường `.venv-ocr`. Ảnh/crop 38–48 đã có;
không cần render hoặc chạy layout lại. `layout/regions.json` giữ cùng danh sách,
thứ tự và SHA-256 của **123 crop** cho cả ba công cụ, bỏ các vùng số trang.
Lệnh chỉ đọc ảnh crop và manifest bố cục, không đọc nội dung tham chiếu hoặc
bản sửa tay. PaddleOCR tự dùng `chinese_cht` cho Hán/tiêu đề Hán và `vi` cho
các vùng còn lại; tiêu đề Hán/Việt được gom vào `tieu_de` theo thứ tự đã lưu.

```sh
source .venv-ocr/bin/activate

python src/ocr.py run --format reference --engine paddleocr --device cpu --pages 38-48

python src/ocr.py run --format reference --engine got-ocr2 --device cuda:0 --pages 38-48 --max-new-tokens 2048

python src/ocr.py run --format reference --engine qwen2.5-vl --device cuda:0 --quantization 4bit --cpu-offload --pages 38-48 --max-new-tokens 2048
```

Chạy lần lượt. Kết quả ở `pages/paddleocr/page-XXXX.json`,
`pages/got-ocr2/page-XXXX.json`, `pages/qwen2.5-vl/page-XXXX.json`.
Mỗi trang được ghi khi OCR xong toàn bộ crop của trang đó; metadata được lưu
sau từng crop để tiếp tục khi bị ngắt. Chạy lại cùng lệnh sẽ tiếp tục từ cache;
thêm `--overwrite` để OCR lại từ đầu. Chế độ này xử lý toàn trang; dùng
`--pages 40` để thử một trang. Nếu có cảnh báo giới hạn token, tăng
`--max-new-tokens` và thêm `--overwrite`.

### Thử cấu hình cải thiện trên trang 38

Đã đối chiếu ảnh và sửa bản tham chiếu trang 38; thay đổi được ghi trong
`patches/ocr_reference_page38.tsv`. Thử nghiệm `--profile scan` riêng trang 38
được lưu tại `out/ocr/week2/scan_profile_probe.md`. CER trên toàn bộ tập trang
38–48 nằm tại `out/ocr/week2/comparison.md`.

`--profile scan` tách dòng ngang, phóng 2×, thêm viền trắng và tăng tương phản
để đọc scan. Qwen dùng prompt theo chữ Hán/Việt, `repetition_penalty=1.0` thay
cho mặc định checkpoint `1.05` để tránh bỏ chữ lặp; vẫn dùng NF4 và CPU offload.
Paddle dùng nhận diện trực tiếp từng dòng Việt thay cho chạy detector lần nữa.
GOT chỉ tách dòng Hán; vùng Việt dùng ảnh crop nguyên bản vì các phép thử tách
dòng Việt/chia patch cho kết quả kém hơn. Vùng `can_kiem_tra` là nhiễu chưa
phân loại, được bỏ khỏi lượt chạy profile và khỏi CER. Cấu hình này không đọc
bản tham chiếu, không sửa đầu ra theo từ điển hoặc theo câu thơ thuộc lòng.

Chạy lần lượt, chỉ trang 38; các trang khác được giữ nguyên:

```sh
python src/ocr.py run --format reference --profile scan --engine paddleocr --device cpu --pages 38 --overwrite
python src/ocr.py run --format reference --profile scan --engine got-ocr2 --device cuda:0 --pages 38 --max-new-tokens 512 --overwrite
python src/ocr.py run --format reference --profile scan --engine qwen2.5-vl --device cuda:0 --quantization 4bit --cpu-offload --pages 38 --max-new-tokens 512 --max-pixels 802816 --overwrite

python src/ocr_compare.py --pages 38
```

Các JSON vẫn có cùng format tham chiếu. Metadata ghi dấu cấu hình từng kết quả
để việc thử một trang không xóa cache các trang còn lại. Khi bị ngắt, bỏ
`--overwrite` khỏi đúng lệnh đang chạy để tiếp tục. Kết quả thử trên một trang
chưa đủ kết luận cấu hình tốt cho cả sách; Paddle Latin vẫn thiếu 90 ký tự Việt,
không thể khắc phục giới hạn bảng ký tự chỉ bằng tiền xử lý.

### Lệnh cho chế độ archive

Các lệnh dưới đây **đều ghi vào cùng `pages/page-XXXX.json`**, không tạo TXT hay
thư mục đầu ra riêng cho từng tầng/công cụ. Chạy lần lượt; thêm `--limit 1`
để thử một crop. Những kết quả đã có cùng ảnh/cấu hình được bỏ qua.

```sh
python src/ocr.py run --engine paddleocr --lang chinese_cht --device cpu --paddle-mode han-lines --input out/ocr/week2/layout/images/han
python src/ocr.py run --engine got-ocr2 --device cuda:0 --input out/ocr/week2/layout/images/han
python src/ocr.py run --engine qwen2.5-vl --device cuda:0 --quantization 4bit --cpu-offload --max-new-tokens 512 --input out/ocr/week2/layout/images/han
```

PaddleOCR dùng [TextRecognition](https://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html)
trực tiếp trên từng dòng ngang để tránh detector bỏ sót chữ. Đã nhận diện
42 dòng/168 chữ trên 9 crop; trang 40 hiện có 8 dòng/32 chữ. Đây là số lượng
OCR, không khẳng định từng chữ đều đúng. Dòng có điểm thấp được giữ và gắn cờ.

OCR tiêu đề Hán cũng ghi vào JSON của trang:

```sh
python src/ocr.py run --engine paddleocr --lang chinese_cht --device cpu --paddle-mode han-lines --input out/ocr/week2/layout/images/tieu_de_han
```

Tiêu đề Latin đã được OCR lại bằng Qwen và đối chiếu ảnh để sửa dấu thanh,
chữ số La Mã và khoảng trắng. Mọi sửa tay chỉ áp dụng cho bản xem, có SHA-256
crop trong `patches/ocr_titles.tsv`. Lệnh OCR tương ứng (dùng lại kết quả nếu có):

```sh
python src/ocr.py run --engine qwen2.5-vl --device cuda:0 --quantization 4bit --cpu-offload --max-new-tokens 128 --input out/ocr/week2/layout/images/tieu_de
python src/ocr.py run --engine qwen2.5-vl --device cuda:0 --quantization 4bit --cpu-offload --max-new-tokens 128 --input out/ocr/week2/layout/images/tieu_de_viet
```

Để áp dụng lại các bản sửa đã đối chiếu:

```sh
python src/pages.py --patches patches/ocr_titles.tsv
python src/review.py
```

**Đo CER bằng `regions[].ocr[<công cụ>].text` thô**, không dùng `content` hoặc
`text` đã sửa. Việc kiểm tra tiêu đề chưa thay thế bản tham chiếu đủ các trang.

Với phiên âm/dịch, đổi `images/han` thành `images/phien_am`, `images/dich_sat`
hoặc `images/dich_tho`. Model PaddleOCR Latin đang cache thiếu các chữ Việt như
`ạ`, `ậ`, `ự`, `ữ`, nên dù chọn `--lang vi` vẫn có thể rơi cả chữ/dấu; đây không
phải lỗi font hiển thị. Đã xác nhận bằng bảng ký tự trong `inference.yml` và
thử trên ảnh. Tham khảo [báo cáo lỗi PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR/issues/16339).
Kết quả PaddleOCR vẫn có thể dùng để so sánh, nhưng không được tự thêm ký tự
vào dictionary mà không có model tương ứng. CLI ghi cảnh báo và metadata về
độ phủ bảng ký tự; bản xem ưu tiên OCR khác có khả năng biểu diễn đầy đủ tiếng Việt.

Chạy lại cả bốn tầng tiếng Việt bằng Qwen (vẫn giữ chữ Hán xen trong chú giải):

```sh
python src/ocr.py run --engine qwen2.5-vl --device cuda:0 --quantization 4bit --cpu-offload --max-new-tokens 2048 --layers phien_am dich_sat dich_tho chu_thich
```

Thêm `--pages 40` để chỉ xử lý trang 40; bộ lọc trang/tầng không làm thay đổi
fingerprint nhận diện. Dùng cùng crop và bản tham chiếu khi so ba công cụ.
Nếu vẫn chạy PaddleOCR Việt để đo CER, dùng `--lang vi` và bỏ `--paddle-mode han-lines`.
Hai cấu hình PaddleOCR vẫn chỉ tính là một công cụ.

Qwen crop Hán dùng giới hạn 512 token; các tầng Việt dùng 2048 token.
Nếu `possibly_truncated` được gắn, kiểm tra crop hoặc tăng giới hạn và dùng
`--overwrite` để thay đúng kết quả của công cụ/vùng đó. Các công cụ khác vẫn
được giữ trong cùng trang. Không tự sửa đầu ra OCR để làm đẹp số liệu.
Khi thay kết quả, bản khác nội dung/cấu hình được giữ tại `ocr_history` trong
cùng JSON. Bản đối chiếu trang 40 được ghi riêng ở `patches/ocr_vietnamese_page40.tsv`;
OCR thô không bị sửa theo bản này.

### Thư mục đầu ra và việc còn lại

```text
out/
  README.md
  corpus.jsonl
  source_errors.tsv
  ocr/
    environment.txt
    week2/
      pages/
        paddleocr/    # JSON gọn, cùng format bản tham chiếu
        got-ocr2/
        qwen2.5-vl/
      runs/           # một JSON/model: cấu hình và cache OCR thô để chạy tiếp
      viewer.html     # bản xem của lượt archive trước
      images/         # ảnh trang + metadata nguồn; không commit
      layout/
        regions.json  # thứ tự và hash crop dùng chung cho ba model
        images/       # crop/preview; không commit
```

JSON theo trang là dữ liệu trung gian; `out/corpus.jsonl` cuối kỳ vẫn phải theo
schema chung của đề. Voting ký tự và CER đã chạy trên cùng 11 trang 38–48.
Trang 44 có cả phần đầu bài Cát đàm; các tầng được chấm theo đúng phạm vi nhìn
thấy trên ảnh. Căn chỉnh corpus cuối kỳ chưa được triển khai.

Hai VLM cố định revision trong `src/ocr.py`; model tải vào `.cache/ocr/` và
được dùng lại. CLI hiện chưa đọc `config.yaml`. Nếu CUDA không khả dụng trong
sandbox, chạy OCR ở terminal thường nhận GPU.

Tài liệu công cụ: [PaddleOCR](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html),
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
- **Tuần 2:** đã chạy ba công cụ OCR, đối chiếu bản tham chiếu với 11 ảnh trang
  PDF 38–48, sinh voting ký tự và bảng CER riêng Hán/Việt. CER voting là 12,30%
  cho Hán và 3,28% cho Việt. Voting tốt hơn từng công cụ ở CER Hán gộp, nhưng
  chưa tốt hơn Qwen ở tiếng Việt (0,89%). Riêng tầng câu Hán, PaddleOCR đạt
  5,95% so với voting 7,74%; cấu hình theo tầng chọn PaddleOCR cho `han` và
  Qwen2.5-VL cho các tầng tiếng Việt. Voting được giữ để đối chiếu.
  Căn chỉnh corpus và các cặp layout vẫn cần hoàn thiện.
- **Tuần 3–5:** hoàn thiện corpus chính, bộ gold, đánh giá và cải tiến căn chỉnh,
  rồi xử lý phần mở rộng. `out/corpus.jsonl`, `gold/gold.jsonl`,
  `eval/eval.py`, `out/source_errors.tsv` hiện còn là file khung.

| Chỉ số cuối kỳ | Hiện tại | Yêu cầu |
| --- | --- | --- |
| CER OCR theo Hán/Việt | Đã đo trên 11 trang; voting Hán 12,30%, Việt 3,28% | Voting thấp hơn từng công cụ; chưa đạt với tiếng Việt |
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
