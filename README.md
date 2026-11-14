# group1

Báo cáo tiến độ môn Xử lý ngôn ngữ tự nhiên (NLP), tổ chức nội dung theo tuần.

## Build báo cáo

Cần cài TeX Live hoặc MiKTeX, có `latexmk`, `pdflatex` và các gói LaTeX
được dùng trong `latex/hcmus-report-template.sty` (bao gồm `vietnam` để gõ tiếng Việt).

Chạy tại thư mục gốc project:

```sh
latexmk
```

Kết quả nằm ở **`report.pdf` tại thư mục gốc**. Các file biên dịch trung gian
nằm trong `build/latex/`; `report.synctex.gz` nằm cạnh PDF để hỗ trợ đồng bộ
giữa mã nguồn và trình xem PDF.

Với VS Code và LaTeX Workshop, mở project này rồi build `latex/report.tex`
bằng recipe **Build NLP report**. Cấu hình dùng chung `.latexmkrc`.

## Điền nội dung

- `latex/report.tex`: tên đề tài, nhóm, giảng viên và ngày nộp.
- `latex/content/title.tex`, `member.tex`: bố cục bìa và bảng thành viên.
- `latex/content/week1.tex`: baseline và kết quả kiểm tra mẫu của 4 sách.
- `latex/content/week2.tex`: kế hoạch OCR và bảng CER chờ cập nhật số liệu.
- Thêm file nội dung cho tuần tiếp theo rồi khai báo `\input` trong
  `latex/report.tex`. Các file khung nội dung, phụ lục và tham khảo cũ vẫn
  được giữ để dùng khi cần, hiện chưa đưa vào bản báo cáo tiến độ.

Logo, căn lề, giãn dòng, header/footer và định dạng mã nguồn được giữ trong
`latex/img/` và `latex/hcmus-report-template.sty`.
