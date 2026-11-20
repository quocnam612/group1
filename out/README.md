# Đầu ra OCR và đánh giá

Kết quả hiện tại trên 11 trang PDF 38–48:

- **Voting Hán: 8,61% (21/244)**.
- **Voting Việt: 0,80% (67/8.405)**.
- **CER gộp: 1,02%**, thấp hơn từng công cụ đơn lẻ trên mẫu hiệu chỉnh.

Xem [bảng CER](ocr/week2/comparison.md), [biên bản thử cấu hình](ocr/week2/scan_profile_probe.md)
và [cấu hình voting](ocr/week2/vote_settings.json).

Mỗi trang là một JSON gọn trong `ocr/week2/pages/<model>/`; các thư mục gồm
`paddleocr`, `got-ocr2`, `qwen2.5-vl`, `tesseract`, `voting`. Bản tham chiếu
ở `gold/ocr/week2/`. Metadata/cache OCR thô nằm trong `ocr/week2/runs/`.

Voting Hán dùng bốn công cụ; voting Việt dùng PaddleOCR, Qwen và Tesseract.
Mỗi vị trí lấy đa số, kể cả lựa chọn bỏ ký tự; hòa theo CER thấp hơn.
Lựa chọn tập công cụ và thứ tự hòa được hiệu chỉnh trên chính 11 trang này.

Chạy lại bằng `python src/ocr_week2_pipeline.py` trong `.venv-ocr`.
Lệnh đọc `config.yaml`; thêm `--skip-ocr` để chỉ tính lại voting/CER.
`viewer.html` cũ thuộc chế độ archive và chưa phản ánh các JSON mới.

Tuần 3: `corpus.jsonl` đã có **4.494 cặp từ đủ bốn sách phần chính**.
Bốn OCR đều hoàn tất 346 trang Kinh Thi; ba sách text hoàn tất 683 trang.
Thống kê và các cờ cần kiểm tra ở [report.md](report.md); đánh giá trên gold ở Tuần 4.
`layers/<book>.jsonl` giữ dữ liệu tầng theo trang, mỗi sách một file.
Ảnh, OCR thô, metadata và checkpoint mới nằm trong `.cache/corpus-v1/`.
`source_errors.tsv` dành cho lỗi sách gốc đã xác nhận.
Ảnh/crop và model cache được gitignore. Hướng dẫn chi tiết ở [README root](../README.md).
