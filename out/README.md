# Đầu ra theo trang

Lượt chạy mới dùng `python src/ocr.py run --format reference --engine <model>`.
Mỗi file có cùng các mảng nội dung với `gold/ocr/week2/`, không chứa số trang
hay metadata. Đầu ra OCR thô nằm ở:

- `ocr/week2/pages/paddleocr/page-XXXX.json`
- `ocr/week2/pages/got-ocr2/page-XXXX.json`
- `ocr/week2/pages/qwen2.5-vl/page-XXXX.json`

`ocr/week2/runs/<model>.json` giữ cấu hình và cache để chạy tiếp;
`ocr/week2/layout/regions.json` giữ thứ tự và hash của 123 crop dùng chung.
Các JSON mới chỉ được tạo khi chạy model. Lệnh đầy đủ nằm trong README ở root.

[comparison.md](ocr/week2/comparison.md) ghi CER trước/sau khi thử cấu hình
`--profile scan` trên trang 38 và các giới hạn của bản tham chiếu.

Phần dưới mô tả chế độ archive trước đây. Các file `pages/page-XXXX.json`
đã được dọn; viewer hiện còn là bản xem của lượt chạy trước.

**Mở [viewer.html](ocr/week2/viewer.html) bằng trình duyệt để dò dễ hơn:**
chọn trang/tầng, tìm chữ không dấu, bấm khung ảnh để xem đúng đoạn và so OCR thô.

Mỗi trang vẫn có **một JSON chứa toàn bộ các tầng và kết quả của từng công cụ**:

- [Trang 38](ocr/week2/pages/page-0038.json)
- [Trang 40](ocr/week2/pages/page-0040.json)
- [Trang 44](ocr/week2/pages/page-0044.json)

Trong JSON, **`content` ở đầu file** chứa các dòng của từng tầng để đọc nhanh.
`layers` có `tieu_de`, `han`, `phien_am`, `dich_sat`, `dich_tho`, `chu_thich`;
`regions[].ocr`
để xem nguyên bản từng công cụ/cấu hình. Tiêu đề Hán có `layer: "tieu_de_han"`
trong `layers.tieu_de.regions`, không trộn vào câu thơ.

`hint_only` là gợi ý từ bố cục/OCR cũ, chưa phải kết quả OCR riêng trên crop.
`ocr_unreviewed` là OCR chưa kiểm tay/đo CER; `mixed_ocr_and_hints` có cả hai.
`source_checked` là bản đã đối chiếu ảnh và lưu sửa trong `patches/*.tsv`.
Bản xem ưu tiên nội dung đã đối chiếu, chưa phải voting; OCR thô vẫn giữ riêng.

`ocr/week2/pages/` có 11 JSON cho trang PDF 38–48 và 123 kết quả OCR crop.
Đã OCR lại đủ 79 vùng tiếng Việt bằng Qwen. Đã đối chiếu 34 tiêu đề và 11 vùng
tiếng Việt trang 40 với ảnh; các vùng còn lại vẫn cần kiểm tay.
Các bản sửa tiếng Việt trang 40 ở `patches/ocr_vietnamese_page40.tsv`; bản OCR cũ
được giữ trong `ocr` hoặc `ocr_history` để đo CER, không thay bằng bản sửa.
Kết quả toàn trang mới sẽ nằm trong `fullpage_ocr`.
Ảnh nguồn ở `images/`, crop ở `layout/images/`; ảnh không commit.

`corpus.jsonl` và `source_errors.tsv` vẫn là file khung theo yêu cầu đề.
Đo CER trên OCR thô, không dùng bản hiển thị đã sửa.
Lệnh chạy nằm trong [README ở root](../README.md).
