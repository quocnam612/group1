# OCR tuần 2 — CER trên trang PDF 38–48

Tập đánh giá gồm 11 trang: 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48.
Nguồn: `Kinh Thi - Ta Quang Phát 1 (tr1-346).pdf`.

## CER tách chữ Hán và tiếng Việt

| Kết quả | Hán | Việt | Gộp Hán + Việt |
| --- | ---: | ---: | ---: |
| paddleocr | 33.20% (81/244) | 15.21% (1278/8405) | 15.71% (1359/8649) |
| got-ocr2 | 45.49% (111/244) | 22.82% (1918/8405) | 23.46% (2029/8649) |
| qwen2.5-vl | 41.39% (101/244) | 0.89% (75/8405) | 2.03% (176/8649) |
| voting | 12.30% (30/244) | 3.28% (276/8405) | 3.54% (306/8649) |

## CER theo tầng nội dung

| Kết quả | tieu_de | han | phien_am | dich_sat | dich_tho | chu_thich |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| paddleocr | 14.81% (60/405) | 5.95% (10/168) | 10.77% (96/891) | 10.96% (145/1323) | 11.16% (135/1210) | 13.68% (974/7121) |
| got-ocr2 | 27.90% (113/405) | 32.74% (55/168) | 32.88% (293/891) | 18.37% (243/1323) | 37.60% (455/1210) | 19.34% (1377/7121) |
| qwen2.5-vl | 0.99% (4/405) | 51.79% (87/168) | 0.67% (6/891) | 0.53% (7/1323) | 2.64% (32/1210) | 0.77% (55/7121) |
| voting | 9.63% (39/405) | 7.74% (13/168) | 2.81% (25/891) | 1.44% (19/1323) | 4.30% (52/1210) | 2.44% (174/7121) |

CER là khoảng cách Levenshtein ký tự chia cho số ký tự tham chiếu. Dữ liệu được chuẩn hóa NFC; khoảng trắng bị bỏ khi tính CER tách Hán/Việt để không tính khác biệt xuống dòng.
Chữ Hán gồm ký tự CJK trong mọi tầng, kể cả tiêu đề và chú giải; phần Việt gồm các ký tự còn lại. `can_kiem_tra` bị loại khỏi voting và CER.
Voting căn chỉnh chuỗi ba công cụ bằng Levenshtein rồi chọn đa số ký tự. Khi hai công cụ chọn hai ký tự khác nhau, dùng công cụ có CER thấp hơn theo ngôn ngữ trên chính tập trang này; vì vậy đây là số liệu hiệu chỉnh, không phải holdout độc lập.

