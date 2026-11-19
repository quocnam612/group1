# Đối chiếu cấu hình OCR — trang PDF 38

Ngày kiểm tra: 2026-11-15. Đã thử ba model thật trên cùng ảnh trang 38. Các lần thử lưu tại `/tmp/group1-ocr-scan-probe/`; kết quả OCR chính ở `out/ocr/week2/pages/` chưa bị ghi đè.

Bản tham chiếu trang 38 ban đầu là bản sao OCR Qwen: phần dịch thơ mất dấu, phiên âm có `Yếu điệu thực nữ`, chú giải có `閩閩`/`雁鳩`. Đã đối chiếu ảnh scan để sửa; chi tiết từng thay đổi và SHA-256 ảnh nằm ở `patches/ocr_reference_page38.tsv`. Giữ các cách in `州`, `dầy`, `nhàn.thục`. Các trang 39–48 vẫn là bản nháp, chưa được coi là gold đã kiểm.

## CER tổng trên 6 mục nội dung

| Model | CER trước | CER cấu hình scan |
| --- | ---: | ---: |
| paddleocr | 10.77% (77/715) | 10.63% (76/715) |
| got-ocr2 | 21.68% (155/715) | 21.40% (153/715) |
| qwen2.5-vl | 4.90% (35/715) | 2.10% (15/715) |

CER tổng cộng số lỗi của từng mục rồi chia tổng 715 ký tự tham chiếu. Kết quả một trang dùng để chỉnh cấu hình; chưa chứng minh chất lượng trên cả sách.

## Chi tiết trước khi đổi cấu hình

| Model | tieu_de | han | phien_am | dich_sat | dich_tho | chu_thich |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| paddleocr | 11.76% (10/85) | 0.00% (0/16) | 10.98% (9/82) | 11.02% (14/127) | 10.32% (13/126) | 11.11% (31/279) |
| got-ocr2 | 28.24% (24/85) | 31.25% (5/16) | 36.59% (30/82) | 12.60% (16/127) | 38.10% (48/126) | 11.47% (32/279) |
| qwen2.5-vl | 2.35% (2/85) | 18.75% (3/16) | 2.44% (2/82) | 0.00% (0/127) | 19.05% (24/126) | 1.43% (4/279) |

CER = số phép chèn/xóa/thay tối thiểu / số ký tự tham chiếu; thấp hơn là tốt hơn.
Chuẩn hóa NFC, gộp khoảng trắng/xuống dòng; riêng `han` bỏ khoảng trắng. Giữ nguyên dấu, chữ hoa và dấu câu.
`can_kiem_tra` chứa nhiễu chưa phân loại, được bỏ khỏi bảng. Chữ Hán xen trong chú giải vẫn thuộc `chu_thich`.
Số liệu chỉ phản ánh bản tham chiếu đang có; các trang chưa kiểm ảnh không phải gold đã xác nhận.


## Chi tiết cấu hình scan

| Model | tieu_de | han | phien_am | dich_sat | dich_tho | chu_thich |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| paddleocr | 14.12% (12/85) | 0.00% (0/16) | 9.76% (8/82) | 10.24% (13/127) | 9.52% (12/126) | 11.11% (31/279) |
| got-ocr2 | 27.06% (23/85) | 25.00% (4/16) | 36.59% (30/82) | 12.60% (16/127) | 38.10% (48/126) | 11.47% (32/279) |
| qwen2.5-vl | 1.18% (1/85) | 6.25% (1/16) | 3.66% (3/82) | 0.79% (1/127) | 3.17% (4/126) | 1.79% (5/279) |

CER = số phép chèn/xóa/thay tối thiểu / số ký tự tham chiếu; thấp hơn là tốt hơn.
Chuẩn hóa NFC, gộp khoảng trắng/xuống dòng; riêng `han` bỏ khoảng trắng. Giữ nguyên dấu, chữ hoa và dấu câu.
`can_kiem_tra` chứa nhiễu chưa phân loại, được bỏ khỏi bảng. Chữ Hán xen trong chú giải vẫn thuộc `chu_thich`.
Số liệu chỉ phản ánh bản tham chiếu đang có; các trang chưa kiểm ảnh không phải gold đã xác nhận.


## Cấu hình được giữ

- Qwen: tách dòng theo hình ảnh, phóng 2×, thêm viền 16 px, autocontrast; prompt Hán/Việt riêng, greedy và `repetition_penalty=1.0`. Checkpoint cache có mặc định 1.05; bỏ mức phạt này giúp giữ chữ lặp. NF4 4-bit, CPU offload, tối đa 802816 pixel và 512 token mỗi dòng. Vẫn sai `州` thành `洲` và một số dấu Việt; một số mục riêng lẻ kém hơn trước, dù tổng giảm rõ.

- Paddle: giữ bộ Hán, dùng nhận diện trực tiếp từng dòng Việt thay cho detector. Cải thiện nhỏ; model Latin trong cache thiếu 90 ký tự Việt, không thể phục hồi bằng tăng độ phân giải hoặc sửa dictionary riêng lẻ.

- GOT: chỉ tách dòng Hán, giữ nguyên crop Việt và chế độ plain OCR. Hai biến thể tách dòng Việt/chia patch đã thử và bị loại vì tăng lỗi. Cấu hình cuối không dùng chia patch, chạy được trên GPU 8 GB. Cải thiện nhỏ, tiếng Việt vẫn yếu.

- Không đưa văn bản tham chiếu vào prompt hoặc suy luận; không sửa văn bản OCR sau khi model trả về. Phần nhiễu `can_kiem_tra` được bỏ khỏi cấu hình thử và phép đo. Sửa cấu hình một trang giữ nguyên cache của trang khác.

## Đối chiếu toàn bộ 11 bản tham chiếu hiện có (cấu hình cũ)

Các giá trị dưới đây chỉ là khoảng cách tới bản nháp đang lưu. Nhiều phần bản nháp xuất phát từ Qwen, nên độ khớp cao không chứng minh độ chính xác so với ảnh. Chỉ trang 38 đã kiểm thêm trong lần chỉnh cấu hình này; trang 40 có các vùng đã kiểm từ trước.

| Model | tieu_de | han | phien_am | dich_sat | dich_tho | chu_thich |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| paddleocr | 14.81% (60/405) | 0.00% (0/168) | 10.77% (96/891) | 11.26% (149/1323) | 11.32% (137/1210) | 13.66% (970/7103) |
| got-ocr2 | 27.90% (113/405) | 30.36% (51/168) | 32.88% (293/891) | 18.67% (247/1323) | 37.52% (454/1210) | 19.63% (1394/7103) |
| qwen2.5-vl | 0.99% (4/405) | 55.95% (94/168) | 0.67% (6/891) | 0.15% (2/1323) | 1.98% (24/1210) | 0.06% (4/7103) |

CER = số phép chèn/xóa/thay tối thiểu / số ký tự tham chiếu; thấp hơn là tốt hơn.
Chuẩn hóa NFC, gộp khoảng trắng/xuống dòng; riêng `han` bỏ khoảng trắng. Giữ nguyên dấu, chữ hoa và dấu câu.
`can_kiem_tra` chứa nhiễu chưa phân loại, được bỏ khỏi bảng. Chữ Hán xen trong chú giải vẫn thuộc `chu_thich`.
Số liệu chỉ phản ánh bản tham chiếu đang có; các trang chưa kiểm ảnh không phải gold đã xác nhận.


## Chạy lại và đánh giá

Các lệnh chạy riêng trang 38 với `--profile scan --overwrite` nằm trong README ở root. Sau khi chạy ba model, dùng `python src/ocr_compare.py --pages 38` để đo lại JSON chính. Bỏ `--overwrite` khi tiếp tục một lượt chạy bị ngắt.

Nguồn cấu hình: [Qwen2.5-VL / độ phân giải ảnh](https://huggingface.co/docs/transformers/v4.57.1/en/model_doc/qwen2_5_vl), [GOT-OCR2 / các chế độ suy luận](https://huggingface.co/stepfun-ai/GOT-OCR-2.0-hf), [PaddleOCR / lỗi bảng ký tự Latin](https://github.com/PaddlePaddle/PaddleOCR/issues/16339).
