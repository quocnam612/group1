# Corpus v1 — Tuần 3

Trạng thái: **đủ phần chính**.

Tổng 4,494 cặp; 4,321 cặp cấp câu.

| Sách | Trang đã xử lý/tổng | Cặp | Chữ Hán nguồn | Chữ Hán được giữ | Độ phủ | Hán cấp câu | Trạng thái |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Kinh Thi (Quyển I) | 346/346 | 2505 | 5067 | 5067 | 100.00% | 97.22% | Đủ trang |
| Vi Chánh | 330/330 | 190 | 10289 | 10289 | 100.00% | 23.69% | Đủ trang |
| Đạo Đức Kinh | 231/231 | 1090 | 5272 | 5272 | 100.00% | 100.00% | Đủ trang |
| Tăng Quảng Hiền Văn | 122/122 | 709 | 3825 | 3825 | 100.00% | 100.00% | Đủ trang |

Độ phủ tính trên nguyên văn đã trích xuất, sau khi loại bìa/mục lục được ghi nhận; chưa phải kiểm tay toàn bộ PDF.
Một đoạn Hán có cả dịch sát và dịch thơ chỉ được đếm một lần khi tính độ phủ. Không dùng số cặp làm tỉ lệ chữ Hán cấp câu.

## Cần kiểm tra

| Cờ | Số cặp |
| --- | ---: |
| ocr_disagreement | 2505 |
| reading_mismatch | 626 |
| low_ocr_confidence | 453 |
| unpaired_viet | 350 |
| han_bounds_from_parallel_viet_needs_review | 297 |
| fragmented_han_detection | 194 |
| unassigned_layout | 132 |
| duplicate | 99 |
| unpaired_han | 66 |
| length_ratio | 52 |
| han_only | 27 |
| viet_only | 20 |
| mixed_script_keep_intact | 9 |
| ocr_truncated | 8 |

`score` là exp(-chi phí Gale–Church/số đơn vị), chỉ là điểm theo độ dài, không phải precision hoặc xác suất đã hiệu chuẩn.
Âm không lấy được được ghi `〓` và gắn `reading_mismatch`; không điền âm đoán. Bản âm nguồn ở `phien_am_goc`.
Không tự gán nghi vấn OCR thành lỗi sách gốc trong `source_errors.tsv`.
Bộ gold căn chỉnh, precision/recall và cải tiến thuộc Tuần 4; bộ gold OCR Tuần 2 được giữ nguyên.

Cấu hình chạy: `.cache/corpus-v1/run.json`.
