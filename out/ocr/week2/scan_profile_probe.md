# Hiệu chỉnh pipeline OCR Tuần 2 — 20/11/2026

Đánh giá trên cùng 11 trang PDF 38–48. Tham chiếu được giữ nguyên; SHA-256 trước/sau được đối chiếu. Mô hình chỉ suy luận trên ảnh, bản tham chiếu dùng để tính CER và xác định thứ tự khi hòa.

| Phương án voting | Hán | Việt | Gộp |
| --- | ---: | ---: | ---: |
| Trước hiệu chỉnh | 12.30% (30/244) | 3.28% (276/8405) | 3.54% (306/8649) |
| Sau hiệu chỉnh | 8.61% (21/244) | 0.80% (67/8405) | 1.02% (88/8649) |

## Quyết định cấu hình

- Paddle: đã thử `scan` trên cả 11 trang. CER Việt 21,37% cao hơn cấu hình gốc 15,21%; giữ cấu hình gốc và tái sinh JSON từ cache OCR thô đã cố định.

- GOT: đã chạy lại cả 11 trang với tách dòng Hán và giữ khối Việt. CER Hán giảm từ 45,49% xuống 39,75%; CER Việt giữ 22,82%.

- Qwen: thử tách mọi dòng trên các trang 38–40, sau đó chuyển sang `balanced`: chỉ tách dòng Hán, giữ khối Việt. Đã chạy lại 12 crop Hán/tiêu đề Hán; 110 crop còn lại tái dùng từ cache khi model, revision, ảnh, prompt, seed, độ phân giải và decoder tương đương. Tất cả output cũ có ít hơn 512 token và không bị cắt. Nguồn cache được ghi ở từng record. CER Hán 9,02%, Việt 0,89%.

- Tesseract: mục 7 hướng dẫn cho phép công cụ thứ tư. Đã chạy hai cấu hình trên cả 11 trang. PSM 7 từng dòng Việt đạt CER 11,87%; PSM 6 giữ khối Việt, dùng từ điển giải mã gốc đạt 3,70%. Dùng `chi_tra` cho Hán, `vie` cho Việt và `vie+chi_tra` cho chú giải; phiên bản 5.5.4 và model tessdata_best được cố định commit/SHA-256.

## Voting được chọn

Căn chỉnh star bằng Levenshtein chi phí đơn vị. Mỗi recognizer được căn với cùng chuỗi trục để giảm lệch tích lũy. Một dấu trống là phiếu bỏ ký tự; trường hợp A/B/trống hòa cả ba và được xử lý theo CER, thay vì ép chọn A hoặc B như code cũ.

Hán bỏ phiếu bằng PaddleOCR, GOT, Qwen, Tesseract. Việt bỏ phiếu bằng PaddleOCR, Qwen, Tesseract vì GOT có CER Việt cao nhất. Mỗi hệ chữ có ít nhất ba công cụ, mỗi công cụ một phiếu; ký tự đa số vẫn thắng dù trái với Qwen. Khi hòa mới dùng thứ tự CER. Các tập công cụ được cố định trên toàn bộ mẫu.

Thử voting cùng cả bốn công cụ cho mọi vị trí đạt 21 lỗi Hán và 84 lỗi Việt. Tổ hợp theo hệ chữ giữ 21 lỗi Hán và giảm lỗi Việt xuống 67, thấp hơn Qwen (22 lỗi Hán, 75 lỗi Việt). Phân loại hệ chữ dựa trên Unicode của OCR trục, không dùng ký tự đáp án để chọn phiếu.

## Kết quả cuối

# OCR tuần 2 — CER trên trang PDF 38–48

Tập đánh giá gồm 11 trang: 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48.
Nguồn: `Kinh Thi - Ta Quang Phát 1 (tr1-346).pdf`.

## CER tách chữ Hán và tiếng Việt

| Kết quả | Hán | Việt | Gộp Hán + Việt |
| --- | ---: | ---: | ---: |
| paddleocr | 33.20% (81/244) | 15.21% (1278/8405) | 15.71% (1359/8649) |
| got-ocr2 | 39.75% (97/244) | 22.82% (1918/8405) | 23.30% (2015/8649) |
| qwen2.5-vl | 9.02% (22/244) | 0.89% (75/8405) | 1.12% (97/8649) |
| tesseract | 41.80% (102/244) | 3.70% (311/8405) | 4.78% (413/8649) |
| voting | 8.61% (21/244) | 0.80% (67/8405) | 1.02% (88/8649) |

## CER theo tầng nội dung

| Kết quả | tieu_de | han | phien_am | dich_sat | dich_tho | chu_thich |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| paddleocr | 14.81% (60/405) | 5.95% (10/168) | 10.77% (96/891) | 10.96% (145/1323) | 11.16% (135/1210) | 13.68% (974/7121) |
| got-ocr2 | 27.16% (110/405) | 25.60% (43/168) | 32.88% (293/891) | 18.37% (243/1323) | 37.60% (455/1210) | 19.34% (1377/7121) |
| qwen2.5-vl | 0.99% (4/405) | 4.76% (8/168) | 0.67% (6/891) | 0.53% (7/1323) | 2.64% (32/1210) | 0.77% (55/7121) |
| tesseract | 6.42% (26/405) | 33.33% (56/168) | 3.82% (34/891) | 0.45% (6/1323) | 5.21% (63/1210) | 2.86% (204/7121) |
| voting | 0.49% (2/405) | 3.57% (6/168) | 0.90% (8/891) | 0.15% (2/1323) | 1.98% (24/1210) | 0.81% (58/7121) |

CER là khoảng cách Levenshtein ký tự chia cho số ký tự tham chiếu. Dữ liệu được chuẩn hóa NFC; khoảng trắng bị bỏ khi tính CER tách Hán/Việt để không tính khác biệt xuống dòng.
Chữ Hán gồm ký tự CJK trong mọi tầng, kể cả tiêu đề và chú giải; phần Việt gồm các ký tự còn lại. `can_kiem_tra` bị loại khỏi voting và CER.
Voting căn chỉnh chuỗi các công cụ bằng Levenshtein rồi chọn đa số ký tự, kể cả lựa chọn bỏ ký tự. Khi hòa, dùng công cụ có CER thấp hơn theo ngôn ngữ trên chính tập trang này; vì vậy đây là số liệu hiệu chỉnh, không phải holdout độc lập.


Đạt yêu cầu CER voting thấp hơn từng công cụ đơn lẻ trên mẫu hiệu chỉnh: 21 < min(81, 97, 22, 102) ở Hán; 67 < min(1278, 1918, 75, 311) ở Việt. Một số tầng riêng vẫn kém Qwen. Thứ tự hòa và chọn cấu hình dùng chính mẫu đang chấm; đây chưa phải kết quả holdout hay bảo đảm độ chính xác cho cả sách.

## Tái lập

Chạy `python src/ocr_week2_pipeline.py` trong `.venv-ocr`. Lệnh đọc `config.yaml`, kiểm cache/ảnh/cấu hình, voting và tính lại CER. Thêm `--overwrite` để suy luận lại toàn bộ; thêm `--skip-ocr` để chỉ chạy voting và CER. Bản trước hiệu chỉnh và các biến thể bị loại được lưu trong `.cache/ocr/baselines/week2-20261120/` và `.cache/ocr/experiments/`.

Nguồn: hướng dẫn CV18 mục Tuần 2, mục 7 và chỉ số CER; [Tesseract ImproveQuality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html), [tessdata_best](https://github.com/tesseract-ocr/tessdata_best).
