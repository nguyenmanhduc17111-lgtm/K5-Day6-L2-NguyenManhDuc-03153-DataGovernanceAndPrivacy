## 04 · Baseline vs PoC

Nguồn số liệu: reports/dev_summary.json.
Nội dung phần này được sinh bằng python -m tools.summarize_t11.

| Nội dung | Baseline | PoC |
|---|---|---|
| Phương pháp | Điểm ngẫu nhiên | Quy tắc đối chiếu nhãn và dự đoán |
| Seed | 42 | 42 |
| Số ứng viên toàn bộ dữ liệu | 260 | 260 |
| Commit của lần chạy | e454767 | e454767 |
| Error Recall@B trên heldout | Chưa đánh giá | Chưa đánh giá |
| Precision@B trên heldout | Chưa đánh giá | Chưa đánh giá |
| Thời gian toàn bộ lần chạy (giây) | 0.2665 | 1.0437 |
| Thời gian quy đổi / 100 ứng viên (giây) | 0.102500 | 0.401423 |

Hai file ranking có cùng tập ứng viên và không trùng ID.
Đánh giá chính thức cần lọc cùng split heldout và dùng cùng budget
theo evaluator. Chưa có GT nên chưa tính được chênh lệch chất lượng.

Thời gian trên là một lần chạy, không phải trung bình benchmark.
Số quy đổi được hiển thị đến 6 chữ số thập phân và tính theo ứng viên,
không phải số ảnh. Baseline và PoC thực hiện các công việc phụ khác nhau,
nên không dùng bảng này để kết luận tốc độ riêng của thuật toán.

### Kết quả review phát triển của PoC

- Đã review 10/10 mục trong hàng đợi dev.
- Giữ nguyên: 9 mục.
- Sửa trong hàng đợi: 1 mục.
- Review bổ sung có 4 yêu cầu chỉnh sửa.
- Tổng thay đổi trên bản nhãn: thêm 3,
  sửa 2, xóa 0.

Đây là kết quả kiểm tra trực quan trên dev, không phải metric chính thức
trên heldout. Các chỉnh sửa bổ sung không tính vào kết quả top-10.
Chưa có review tương đương cho baseline để so sánh chất lượng thủ công.

Kết luận hiện tại: chưa đủ bằng chứng khẳng định PoC tốt hơn baseline.
