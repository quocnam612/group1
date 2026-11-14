# group1

Template báo cáo môn Xử lý ngôn ngữ tự nhiên (NLP).

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
- `latex/content/I-GioiThieu.tex` đến `V-KetLuan.tex`: khung nội dung NLP;
  thay các đoạn gợi ý màu xám bằng nội dung thực tế.
- `latex/content/phuluc.tex`: phụ lục.
- `latex/ref/ref.bib`: thêm nguồn tham khảo; khi bắt đầu dùng `\cite{...}`,
  thay phần placeholder trong `latex/ref/ref.tex` bằng các lệnh BibTeX đã
  ghi chú ở đó (bỏ cả tiêu đề thủ công vì BibTeX tự tạo tiêu đề).

Logo, căn lề, giãn dòng, header/footer và định dạng mã nguồn được giữ trong
`latex/img/` và `latex/hcmus-report-template.sty`.
