# Metric contract — G04 — T11

| Mục | Khai báo |
|---|---|
| Người thực hiện | Nguyễn Mạnh Đức |
| Track | T11 — Post-label Error Review Prioritizer |
| Primary metric | Error Recall@B |
| Chiều tốt | Cao hơn tốt hơn |
| Đơn vị đánh giá | Nhãn có sẵn (`ann_id`) hoặc ảnh có thể thiếu nhãn (`img:<image_id>`) |
| Công thức | Số mục lỗi thật trong top-B / tổng số mục lỗi thật thuộc tập đánh giá |
| Ghép với đáp án | Theo item_id, sử dụng evaluator chuẩn của repo |
| Candidate pool | Toàn bộ ann_id trong annotations.csv và một mục img:<image_id> cho mỗi ảnh trong images.csv |
| Kiểm tra pool | Baseline và PoC đều có 260 mục, cùng tập ID, không trùng ID |
| Budget đánh giá chính thức | B = max(10, 10% N), theo cách tính của evaluator trên tập đánh giá |
| Budget review phát triển | 10 mục thuộc dev; không đồng nhất với budget đánh giá heldout |
| Seed | 42 cho cả baseline và PoC |
| Baseline | Điểm ngẫu nhiên từ src.examples.random_baseline |
| PoC | Độ lệch khung, khác lớp, nghi trùng và nghi thiếu nhãn |
| Eval split | heldout; không dùng nhãn heldout để điều chỉnh thuật toán |
| Slices dự kiến | Mục cấp nhãn và mục cấp ảnh; phân tích thêm theo loại lỗi khi có GT |
| Chỉ số phụ | Precision@B, độ bao phủ loại lỗi; chỉ tính khi có nhãn đánh giá phù hợp |
| Độ bất định | Chưa tính CI do chưa có GT; nếu bổ sung bootstrap, lấy mẫu theo ảnh để giữ các mục cùng ảnh đi cùng nhau |
| Thời điểm chốt | Sau phát triển và review trên dev, trước khi có kết quả đánh giá heldout |

## Quy tắc chấm điểm hiện tại

- Chọn dự đoán có IoU cao nhất trong cùng ảnh.
- Điểm nghi ngờ ban đầu: 1 - IoU.
- Không có dự đoán chồng lên nhãn: điểm 1.0.
- Nếu dự đoán khớp khác lớp: điểm ít nhất 0.9.
- Hai nhãn cùng ảnh, cùng lớp có IoU >= 0.85: đánh dấu nghi trùng.
- Dự đoán có conf >= 0.7 và IoU lớn nhất với các nhãn < 0.3:
  nghi thiếu nhãn; điểm = conf × (1 - IoU).
- Điểm nghi thiếu nhãn của ảnh là điểm lớn nhất trong các dự đoán đủ điều kiện.
- Các ngưỡng trên là lựa chọn ban đầu, chưa chứng minh tối ưu.

## Review và chỉnh sửa

- Đã review 10 mục dev: 9 giữ nguyên, 1 sửa khung.
- Có thêm 4 chỉnh sửa từ review bổ sung trên dev.
- Tổng cộng: 3 nhãn mới và 2 khung được sửa.
- Review bổ sung không được tính vào số lỗi tìm được trong top-10.
- Đây là quyết định kiểm tra trực quan, chưa được đối chiếu với GT ẩn.
- Ranking dùng để đánh giá giữ điểm trước khi sửa nhãn.

## Trạng thái đánh giá

Chưa có fixtures/t11_label_errors/gt/gt_errors.csv.

Error Recall@B và Precision@B chính thức: CHƯA ĐÁNH GIÁ.
Không thay giá trị chưa biết bằng 0 và không dùng model_predictions.csv làm GT.

Chưa kết luận PoC tốt hơn baseline.
Quyết định hiện tại: HOLD — HELDOUT_EVALUATION_PENDING.

## Hạn chế đã quan sát

Nhiều mục có điểm 1.0 là nhãn phù hợp nhưng mô hình bỏ sót.
Đối tượng bị cả nhãn và mô hình bỏ sót không được phát hiện bằng
quy tắc đối chiếu hiện tại; ví dụ xe máy trong ảnh lbl_26.

Thời gian chạy baseline và PoC bao gồm các công việc khác nhau:
baseline tạo contact sheet, còn PoC áp dụng review và ghi audit.
Không diễn giải chênh lệch này thành tốc độ riêng của thuật toán.