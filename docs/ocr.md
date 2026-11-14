# Chạy OCR tuần 2

Chạy các lệnh tại root project. Bộ công cụ gồm **PaddleOCR 3.3.2**, **Qwen2.5-VL-7B-Instruct**
và **GOT-OCR-2.0-hf**. Baseline cũ trong `tutorials/` được giữ riêng.

## Môi trường

Máy hiện có RTX 4060 Laptop 8 GB. Dùng Python 3.11 trong `.venv-ocr`, PyTorch
CUDA 12.8 cho hai VLM; PaddleOCR dùng CPU. Qwen mặc định lượng tử hóa NF4 4-bit
và giới hạn số pixel để giảm VRAM. Không chạy Qwen và GOT đồng thời trên GPU này.

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

Nếu đang dùng tiến trình nền `group1-ocr-setup` sau lần VS Code bị OOM,
không chạy thêm installer song song. Tiến trình này giới hạn RAM 2,5 GB,
CPU một nhân và chỉ tải/cài từng gói. Theo dõi bằng:

```sh
systemctl --user status group1-ocr-setup.service --no-pager
tail -f out/ocr/setup.log
```

## Ảnh đầu vào

Render 7 trang Quan thư đã khảo sát ở 300 DPI:

```sh
python src/ocr.py render --pdf "chinh/Kinh Thi - Ta Quang Phát 1 (tr1-346).pdf" --pages 38-44
```

Ảnh nằm trong `out/ocr/images/`; các JSON cạnh ảnh ghi PDF nguồn, SHA-256,
trang PDF và DPI. Khi chọn thêm 3 trang, chạy lại `render --pages ...`; các
trang đã render cùng cấu hình được giữ lại. `pages.json` tổng hợp ảnh hiện có.

Để tách vùng Hán/Việt cho đánh giá, có thể cắt theo tọa độ tương đối 0–1.
Ví dụ sau cắt khối Hán ở trang 38; cần xem lại ảnh crop trước khi dùng làm mẫu:

```sh
python src/ocr.py crop --input out/ocr/images/page-0038.png --box 0.10 0.23 0.34 0.405 --output out/ocr/images/crops/page-0038-han.png
```

Dùng **cùng ảnh/crop và bản tham chiếu** cho cả ba công cụ. Không sửa văn bản
OCR bằng tay trước khi đo CER. Trang 44 có cả đầu bài thứ hai; giữ phạm vi
đánh giá thống nhất với bản chép tay.

## Chạy ba công cụ

### PaddleOCR — hai cấu hình ngôn ngữ của cùng một công cụ

```sh
python src/ocr.py run --engine paddleocr --lang chinese_cht --device cpu --input out/ocr/images --output out/ocr/paddleocr/han
python src/ocr.py run --engine paddleocr --lang vi --device cpu --input out/ocr/images --output out/ocr/paddleocr/viet
```

`chinese_cht` cho chữ Hán phồn thể, `vi` cho tiếng Việt. Khi đo CER theo vùng,
thay `--input` bằng thư mục crop phù hợp. Hai cấu hình này không được tính là
hai công cụ độc lập; script giữ đầu ra riêng, không tự ghép hai bản nhận dạng.

### GOT-OCR2

```sh
python src/ocr.py run --engine got-ocr2 --device cuda:0 --input out/ocr/images --output out/ocr/got-ocr2
```

### Qwen2.5-VL 7B — 4-bit cho GPU 8 GB

```sh
python src/ocr.py run --engine qwen2.5-vl --device cuda:0 --quantization 4bit --input out/ocr/images --output out/ocr/qwen2.5-vl
```

Thêm `--limit 1` để thử một ảnh trước. Mặc định tối đa 4.096 token đầu ra.
JSON gắn `possibly_truncated` nếu chạm giới hạn; khi đó cần xem lại, cắt vùng
hoặc tăng `--max-new-tokens`. Qwen mặc định `--max-pixels 401408`; tăng độ phân
giải làm tăng VRAM, vì vậy crop các khối chữ nhỏ thường phù hợp hơn cho GPU 8 GB.

## Đầu ra, model và chạy tiếp

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
