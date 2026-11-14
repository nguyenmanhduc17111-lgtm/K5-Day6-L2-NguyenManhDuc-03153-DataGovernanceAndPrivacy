# Group Report - G04 - T11

## 00 · Header

| Mục | Giá trị |
|---|---|
| Group ID | G04 |
| Challenge | T11 — Post-label Error Review Prioritizer |
| Thành viên | Nguyễn Mạnh Đức — 03153 |
| Vai trò | Tích hợp, thuật toán, kiểm thử, review và báo cáo |
| Git URL | https://github.com/nguyenmanhduc17111-lgtm/K5-Day6-L2-NguyenManhDuc-03153-DataGovernanceAndPrivacy |
| Tag demo-180m | Chưa tạo |
| Tag final-24h | Chưa tạo |
| Deadline | Theo thông báo của giảng viên; lịch repo có mốc hoàn thiện +24h |

## 01 · Problem statement

Dữ liệu gán nhãn có thể chứa lỗi sai lớp, lệch khung, trùng khung
hoặc thiếu đối tượng. Kiểm tra thủ công toàn bộ dữ liệu tốn thời gian.
Mục tiêu của bài là xếp hạng các mục đáng nghi để người review tìm
được nhiều lỗi trong ngân sách kiểm tra giới hạn.

Người chịu ảnh hưởng là người gán nhãn, người kiểm tra chất lượng
và nhóm sử dụng dữ liệu để huấn luyện mô hình.

Đầu vào gồm ảnh, nhãn hiện tại, dự đoán mô phỏng và manifest.
Pipeline kiểm tra nguồn dữ liệu, tính điểm nghi ngờ, chọn hàng đợi
review trên dev, đọc quyết định của người review và xuất kết quả.

Đầu ra chính:
- ranking.csv: điểm nghi ngờ cho nhãn và mục cấp ảnh.
- review_queue.csv: danh sách ưu tiên kiểm tra.
- annotations_reviewed.csv: bản nhãn sau chỉnh sửa.
- audit_log.jsonl: người review, lý do và thay đổi trước/sau.
- decision.json: quyết định và người chịu trách nhiệm.

Dự đoán mô phỏng chỉ là nguồn tham khảo, không được coi là đáp án.
Người review kiểm tra đối tượng nhìn thấy trong ảnh trước khi giữ
hoặc sửa nhãn. Các chỉnh sửa phát triển chỉ áp dụng trên tập dev.

Quyết định hiện tại là HOLD với reason_code
HELDOUT_EVALUATION_PENDING: đã hoàn thành hàng đợi review dev,
nhưng chưa có kết quả đánh giá heldout để kết luận chất lượng.

Pipeline hiện chưa triển khai điều kiện chuyển sang GO hoặc REWORK.
Không coi việc chương trình chạy thành công là bằng chứng dữ liệu
đã sẵn sàng phát hành.
## 02 · Data & provenance

Nguồn số liệu: reports/data_inventory.json, được tạo bằng:
python -m tools.inventory_t11

| Split | Số ảnh | Số nhãn hiện có | Số ứng viên |
|---|---:|---:|---:|
| dev | 38 | 145 | 183 |
| heldout | 17 | 60 | 77 |
| Tổng | 55 | 205 | 260 |

Một ứng viên là một nhãn hiện có (ann_id) hoặc một mục cấp ảnh
(img:<image_id>) để đánh giá khả năng thiếu nhãn.

Nguồn theo manifest:
synthetic:tools/make_fixtures.py (seed 42).

Giấy phép theo manifest:
CC0-1.0 (synthetic, generated for AI20K Day06).

Dữ liệu dùng trong bài là dữ liệu mô phỏng có sẵn tại
fixtures/t11_label_errors/. Không sử dụng dữ liệu thật bổ sung.

Các file đầu vào:
- images.csv: image_id, đường dẫn ảnh, kích thước và split.
- annotations.csv: ann_id, image_id, class, x, y, w, h.
- model_predictions.csv: image_id, class, x, y, w, h, conf.
- manifest.csv: thông tin nguồn, giấy phép và SHA256.

Giữ nguyên phân chia theo ảnh trong images.csv. Các nhãn và mục
cấp ảnh thuộc cùng một ảnh được gán cùng split. Seed chạy là 42.

Pipeline kiểm tra manifest trước khi xử lý, với strict_provenance=true.
Bộ test kiểm tra fixture đã chạy thành công. Lỗi chuyển LF sang CRLF
trên Windows đã được khắc phục bằng cách chỉ khôi phục các file có
SHA256 sau chuẩn hóa khớp manifest. File .gitattributes được bổ sung
quy tắc fixtures/** -text để Git giữ nguyên byte của fixture.

Dữ liệu gốc không bị sửa nhãn trực tiếp. Các yêu cầu chỉnh sửa được
lưu tại reports/dev_label_edits.json; bản nhãn đã sửa được sinh tại
out/poc/annotations_reviewed.csv.

Ground truth ẩn không có trong repo học viên. model_predictions.csv
không phải ground truth. Review và chỉnh sửa phát triển chỉ dùng dev;
chưa đánh giá chất lượng chính thức trên heldout.

## 03 · Research & design

### Thiết kế hiện tại

Pipeline dùng các quy tắc đơn giản, chạy trên CPU và có thể giải thích
lý do một mục được ưu tiên review.

Luồng xử lý:

Input + manifest
→ kiểm tra SHA256
→ đọc nhãn và dự đoán
→ tính điểm nghi ngờ
→ xuất ranking cho toàn bộ ứng viên
→ chọn top-10 dev để review
→ đọc quyết định và áp dụng yêu cầu chỉnh sửa
→ xuất nhãn đã sửa, audit và quyết định HOLD.

Hàm bbox_iou tự tính tỷ lệ diện tích giao trên diện tích hợp
của hai khung. Với từng nhãn, chương trình tìm dự đoán có IoU
cao nhất trong cùng ảnh rồi kiểm tra mức lệch khung và khác lớp.

Các cặp nhãn cùng ảnh, cùng lớp có độ chồng lấp cao được đánh dấu
nghi trùng. Dự đoán có độ tin cậy đủ cao nhưng không khớp nhãn nào
được dùng để tạo điểm nghi thiếu nhãn ở cấp ảnh.

Các ngưỡng cụ thể được ghi tại reports/metric_contract.md.
Ngưỡng confidence hiện chỉ được dùng trong quy tắc nghi thiếu nhãn;
chưa được dùng để lọc dự đoán khi đối chiếu từng nhãn hiện có.

### Công cụ và thành phần

- pandas: đọc, xử lý và xuất bảng dữ liệu.
- Pillow: tạo ảnh so sánh và ảnh phóng to để review.
- Hạ tầng repo: manifest, offline guard, GT guard, review queue,
  audit log và decision.
- Không huấn luyện hoặc tải mô hình trong pipeline.
- Dự đoán được đọc từ file mô phỏng có sẵn.
- Chưa tích hợp Cleanlab hoặc mô hình thứ hai.

### Cơ sở tham khảo

Tài liệu torchvision.ops.box_iou được dùng để đối chiếu khái niệm
IoU và cách biểu diễn khung. Code hiện tại tự cài hàm IoU,
không gọi torchvision.

Tài liệu cleanlab.object_detection.filter.find_label_issues
được tham khảo cho hướng phát hiện và ưu tiên các ảnh có nhãn
đáng nghi. Đây là hướng cải tiến, chưa phải thành phần đã triển khai.

Các tài liệu được kiểm tra khi hoàn thiện báo cáo.
Liên kết và ngày truy cập được ghi tại mục References.

### Đánh đổi và hạn chế thiết kế

Ưu điểm là ít phụ thuộc, chạy offline và có lý do review rõ ràng.
Tuy nhiên, chất lượng xếp hạng phụ thuộc vào dự đoán mô phỏng.

Quy tắc cho điểm 1.0 khi không có dự đoán khớp dễ ưu tiên nhầm
nhãn đúng mà mô hình bỏ sót. Đối tượng bị cả nhãn và mô hình bỏ sót
cũng không được phát hiện bằng quy tắc đối chiếu hiện tại.

Việc ghép khung hiện thực hiện độc lập cho từng nhãn, chưa có ràng buộc
ghép một-một. Vì vậy, nhiều nhãn có thể cùng khớp một dự đoán.

Người review quyết định dựa trên ảnh. Chỉnh sửa được lưu riêng,
giữ dữ liệu gốc và ghi lịch sử trước/sau để có thể kiểm tra lại.

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

## 05 · Evaluation protocol

Protocol chi tiết được lưu tại reports/metric_contract.md.

### Đánh giá xếp hạng

Primary metric là Error Recall@B, càng cao càng tốt:

Error Recall@B =
số mục lỗi thật trong top-B / tổng số mục lỗi thật thuộc tập đánh giá.

Một mục là ann_id hoặc img:<image_id>. Ghép kết quả với GT theo item_id.
Budget chính thức dùng B = max(10, 10% N), theo cách tính của evaluator.

Baseline và PoC phải được đánh giá trên cùng tập ứng viên heldout,
cùng budget và seed 42. Không dùng nhãn heldout để chọn ngưỡng.
Các ngưỡng hiện tại được ghi trong metric_contract.md trước khi
có kết quả đánh giá heldout.

Ranking được tạo từ dữ liệu nhãn gốc. Các quyết định review không
được dùng để hạ điểm nghi ngờ rồi báo đó là cải thiện chất lượng ranking.

### Đánh giá chỉnh sửa nhãn

Bản gốc và bản đã sửa được lưu riêng để đối chiếu.
Script tools.summarize_t11 đếm nhãn thêm, sửa và xóa bằng cách so
annotations.csv với annotations_reviewed.csv.

Số thay đổi không đồng nghĩa với số lỗi được sửa đúng theo GT.
Độ chính xác của các chỉnh sửa hiện được kiểm tra bằng mắt trên dev;
chưa có metric chất lượng nhãn trước/sau đối chiếu với GT sạch.

### Lệnh đánh giá khi có overlay của giảng viên

Các lệnh dưới đây chưa chạy thành công trong repo hiện tại vì thiếu GT:

```powershell
python -m src.evaluate --track t11 --gt fixtures/t11_label_errors/gt/gt_errors.csv --pred out/baseline/ranking.csv --run-name baseline --out reports/metrics_baseline.json

python -m src.evaluate --track t11 --gt fixtures/t11_label_errors/gt/gt_errors.csv --pred out/poc/ranking.csv --run-name poc --out reports/metrics_poc.json

python -m src.compare reports/metrics_baseline.json reports/metrics_poc.json --out reports/table1_baseline_vs_poc.md
```

Các file metric chính thức phải do evaluator sinh, không tự điền
giá trị hoặc dùng dự đoán mô phỏng thay cho GT.

### Giới hạn diễn giải

Hàng đợi review dev là tập được chọn có chủ đích, không phải mẫu
ngẫu nhiên đại diện cho toàn bộ dữ liệu. Không suy rộng kết quả
review này thành tỷ lệ lỗi chung hoặc chất lượng trên heldout.

Chưa tính confidence interval do chưa có đánh giá GT.
Nếu bổ sung bootstrap, sẽ lấy mẫu theo ảnh để giữ các mục trong
cùng ảnh đi cùng nhau.

Sau khi có kết quả heldout, báo cả kết quả không cải thiện hoặc kém
baseline; không đổi ngưỡng dựa trên kết quả này rồi báo lại như
một phép đánh giá độc lập.

## 06 · Result slices

Nguồn số lượng: reports/data_inventory.json và reports/dev_summary.json.
Các chỉ số chưa đánh giá là giá trị chưa biết, không phải 0.

| Slice heldout | Số ứng viên | Baseline Error Recall@B | PoC Error Recall@B |
|---|---:|---|---|
| Nhãn hiện có | 60 | Chưa đánh giá | Chưa đánh giá |
| Mục cấp ảnh để tìm thiếu nhãn | 17 | Chưa đánh giá | Chưa đánh giá |

Chưa có GT nên chưa tính được kết quả theo slice.
Budget và mẫu số phải được khai báo khi thực hiện đánh giá từng slice.

### Failure case 1: mô hình bỏ sót gây báo động nhầm

Trong ảnh lbl_00, ann_003 bao quanh người đi bộ và được reviewer
đánh giá là phù hợp. Mô hình không có dự đoán tương ứng, khiến
thuật toán cho điểm nghi ngờ 1.0.

Nguyên nhân: quy tắc không phân biệt được nhãn sai với trường hợp
mô hình bỏ sót. Quyết định review là approve, giữ nguyên nhãn.

Minh chứng: reports/review_evidence/inspect_lbl_00.png.

### Failure case 2: cả nhãn và mô hình cùng bỏ sót

Trong ảnh lbl_26, xe máy giữa đường chưa có nhãn và cũng không
có dự đoán tương ứng. Quy tắc đối chiếu không phát hiện được
chính đối tượng này.

Người review phát hiện xe máy khi xem ảnh và bổ sung nhãn.
Ảnh lbl_26 vẫn có tín hiệu nghi thiếu nhãn từ dự đoán khác;
không được coi đó là bằng chứng thuật toán đã tìm ra xe máy.

Minh chứng:
- reports/review_evidence/inspect_lbl_26.png
- reports/review_evidence/proposed_lbl26_motorbike.png

### Trường hợp sửa khung trong hàng đợi

ann_123 trong lbl_30 có khung lệch lên trên và sang trái,
chưa bao hết xe máy và bánh xe. Người review sửa vị trí và kích thước.

Minh chứng: reports/review_evidence/proposed_ann_123.png.

### Tổng hợp chỉnh sửa

| Ảnh / nhãn | Thao tác | Khung mới (x, y, w, h), pixel | Phạm vi |
|---|---|---|---|
| lbl_14 / review_lbl_14_sign_01 | Thêm sign | 293.77, 46.99, 17.13, 13.9 | Bổ sung dev |
| lbl_26 / review_lbl_26_motorbike_01 | Thêm motorbike | 153, 78, 12, 16 | Bổ sung dev |
| lbl_26 / ann_104 | Sửa khung sign | 260, 40, 20, 20 | Bổ sung dev |
| lbl_30 / ann_123 | Sửa khung motorbike | 241, 131, 26, 44 | Hàng đợi dev |
| lbl_43 / review_lbl_43_sign_01 | Thêm sign | 12, 16, 20, 20 | Bổ sung dev |

Tọa độ lấy từ reports/dev_label_edits.json.
Script xác nhận có 3 nhãn thêm, 2 nhãn sửa và không có nhãn bị xóa.

Đây là các chỉnh sửa đã được kiểm tra trực quan bởi một reviewer,
chưa được xác minh bằng GT ẩn. Không khẳng định bản nhãn đầu ra
đã hết mọi lỗi.

## 07 · Human & decision

### Quy trình review

Pipeline lọc ứng viên thuộc dev và chọn tối đa 10 mục có điểm
nghi ngờ cao nhất. Khi bằng điểm, helper giữ thứ tự ổn định.

- Hàng đợi sinh ra: out/poc/review_queue.csv.
- Quyết định đã lưu: reports/review_queue_reviewed.csv.
- Minh chứng: reports/review_evidence/.
- Yêu cầu chỉnh sửa: reports/dev_label_edits.json.

Trong workflow này:
- approve: giữ nhãn hiện tại vì reviewer thấy phù hợp.
- edit: sửa nhãn theo nội dung đã được reviewer xác nhận.
- skip: chưa giải quyết mục đó.
- escalate: chuyển kiểm tra thêm.

approve không có nghĩa dự đoán của mô hình là đúng.
Quyết định dựa trên đối tượng nhìn thấy trong ảnh.

### Áp dụng chỉnh sửa và audit

Với edit trong hàng đợi, override_value chứa JSON của nhãn mới.
Pipeline kiểm tra nội dung này khớp với yêu cầu sửa, người review
và đường dẫn minh chứng.

src/dev_review.py hỗ trợ add và edit. Trước khi xuất kết quả,
chương trình kiểm tra:
- Reviewer, lý do và file minh chứng.
- ID không bị lặp trong các yêu cầu.
- Ảnh thuộc tập dev.
- Lớp hợp lệ.
- Tọa độ hữu hạn, kích thước dương và khung nằm trong ảnh.
- Với edit, nhãn phải tồn tại và thuộc đúng ảnh.

Bản đã sửa được lưu tại out/poc/annotations_reviewed.csv.
Dữ liệu gốc được giữ nguyên.

Audit nằm tại out/poc/audit_log.jsonl, gồm người thực hiện,
thời gian, thao tác, lý do, minh chứng và dữ liệu trước/sau.
review_scope phân biệt chỉnh sửa trong hàng đợi với review bổ sung.

Mỗi lần chạy dựng lại bản đã sửa từ dữ liệu gốc nên không thêm
lặp nhãn vào bảng đầu ra. Audit được ghi nối tiếp qua các lần chạy;
không đếm số dòng audit như số lỗi duy nhất đã sửa.

### Quyết định

Trạng thái hiện tại: HOLD.
Reason code: HELDOUT_EVALUATION_PENDING.
Owner: Nguyễn Mạnh Đức.

Hàng đợi dev đã được giải quyết, nhưng chưa có đánh giá heldout
để kết luận chất lượng và cho phép phát hành dữ liệu.

Nếu còn mục chưa giải quyết, pipeline dùng REVIEW_INCOMPLETE.
Nếu có mục cần chuyển kiểm tra thêm, dùng REVIEW_ESCALATED.

Chưa triển khai nhánh GO hoặc REWORK.
Việc chạy thành công không được coi là chứng nhận chất lượng dữ liệu.

## 08 · Reproduce & tests

### Môi trường thực tế

- Python: 3.14.7.
- Pytest: 9.2.0.
- OS: Windows-11-10.0.26200-SP0.
- Processor: AMD64 Family 23 Model 104 Stepping 1, AuthenticAMD.
- Commit trong metadata của các lần chạy đã báo cáo: e454767.
- Seed: 42.
- Pipeline chạy offline.

README gốc khuyến nghị Python 3.11–3.13. Môi trường thực tế trên
đã chạy qua bộ test; chưa kiểm chứng lại trên các phiên bản
Python được khuyến nghị.

### Lệnh tái lập

Chạy trong PowerShell tại thư mục gốc repo.
Nếu chưa có môi trường:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Bước cài thư viện có thể cần mạng hoặc wheelhouse.
Sau khi cài xong, chạy:

```powershell
python -m src.main --track t11 --pipeline src.examples.random_baseline --output out/baseline --run-name baseline --offline --seed 42

python -m src.main --track t11 --output out/poc --run-name poc --offline --seed 42

python -m tools.inventory_t11
python -m tools.summarize_t11
python -m pytest -v
```

Lệnh evaluate chính thức và điều kiện cần GT được ghi ở mục 05.

Khi thư mục đầu ra chưa có file review riêng, pipeline đọc bản
reports/review_queue_reviewed.csv. Các yêu cầu sửa và ảnh minh chứng
phải được lưu cùng repo.

Đã chạy thành công vào thư mục out/reproduce_check trong cùng
checkout và môi trường. Chưa kiểm chứng trên máy sạch hoặc clone mới.

### Kết quả kiểm thử

Log kiểm thử đã quan sát:

49 passed, 39 skipped, 0 failed in 15.10s.

Hai test riêng trong tests/test_t11_pipeline.py đều đạt:
1. Nhãn khác lớp được ưu tiên hơn nhãn khớp với dự đoán.
2. Khi không có dự đoán, chương trình vẫn xuất kết quả hợp lệ,
   không có điểm NaN và đánh dấu cần review.

Các test skipped không được tính là đã đạt. Repo học viên thiếu
GT cần cho nhiều test; chưa thống kê từng lý do skip trong báo cáo.

Hai test riêng chưa bao phủ toàn bộ chức năng add/edit và mọi
trường hợp dữ liệu lỗi.

### Các lỗi môi trường đã xử lý

- Git trên Windows chuyển LF sang CRLF làm sai checksum fixture.
  Chỉ khôi phục những file mà SHA256 sau chuẩn hóa khớp manifest.
- Bổ sung fixtures/** -text vào .gitattributes để giữ nguyên byte.
- Pipeline từ chối track ngoài T11 bằng NotImplementedError;
  test CLI gọi T02 nhận đúng mã thoát 3.
- Khắc phục lỗi mã hóa tiếng Việt trong một yêu cầu review.
  Bản ghi audit mới đã có tên và lý do đúng; lịch sử cũ được giữ lại.

## 09 · Limitations & ethics

### Hạn chế

- Chưa có GT ẩn nên chưa tính được Error Recall@B, Precision@B,
  CI hoặc chất lượng nhãn trước/sau.
- Chưa đủ bằng chứng kết luận PoC tốt hơn baseline.
- Dự đoán mô phỏng có thể bỏ sót, sai lớp hoặc tạo khung trên nền.
- Các ngưỡng chưa được tối ưu có hệ thống.
- Nhiều mục điểm 1.0 là báo động nhầm do mô hình bỏ sót.
- Cách ghép hiện tại chưa có ràng buộc một-một.
- Chỉ có một người review; chưa đánh giá độ đồng thuận giữa reviewer.
- Chưa kiểm chứng trên dữ liệu thật hoặc dữ liệu lớn hơn.
- Chi phí so sánh khung tăng theo số nhãn và dự đoán trong mỗi ảnh.
- Review đã lưu gắn với ID của fixture dev hiện tại. Khi dùng bộ
  input khác, cần tách chế độ chấm điểm khỏi áp dụng review đã lưu;
  chưa xác nhận chạy end-to-end trên hidden input khác.
- Chưa tích hợp Cleanlab hoặc disagreement của hai mô hình,
  dù đây là nội dung được nêu ở mốc +24h trong đề T11.
- Chưa thực hiện ablation hoặc hidden evaluation.

### Dữ liệu và trách nhiệm

Dữ liệu theo manifest là synthetic, giấy phép CC0-1.0.
Không sử dụng thêm ảnh người thật hoặc biển số thật.

Các chỉnh sửa được lưu riêng, có người review và lịch sử trước/sau.
Kết quả kỹ thuật không phải chứng nhận tuân thủ pháp luật.

Quá trình thực hiện có trợ lý AI hỗ trợ giải thích, tạo đoạn code
và soạn báo cáo. Người thực hiện chạy chương trình, xem ảnh và
xác nhận các quyết định review.

### Hướng cải tiến

- Đánh giá lại cách ưu tiên nhãn không có dự đoán khớp trên dev.
- Cân nhắc phân bổ ngân sách review theo loại nghi ngờ.
- Bổ sung ghép khung một-một.
- Thử Cleanlab hoặc thêm mô hình độc lập.
- Thêm test cho add/edit, từ chối sửa heldout và chạy lại không
  tạo nhãn lặp.
- Tách chế độ scoring cho input mới khỏi replay review của fixture.
- Sau khi chốt phương pháp, đánh giá trên tập độc lập và báo cáo
  cả trường hợp không cải thiện so với baseline.

## 10 · Team contribution

Nhóm G04 gồm Nguyễn Mạnh Đức — mã học viên 03153.
Bảng chi tiết: reports/team_contributions.csv.

| Học viên | Git author | Git email | Vai trò |
|---|---|---|---|
| Nguyễn Mạnh Đức | nguyennducgn | nguyennducg@gmail.com | Tích hợp, thuật toán, QA, human review và báo cáo |

| Commit | Minh chứng công việc |
|---|---|
| adf51c1 | Cấu hình T11 cho nhóm G04 |
| 7013215 | Thuật toán chấm điểm và công cụ xem ảnh |
| 0c48180 | Audit review và bổ sung nhãn thiếu |
| e438172 | Hỗ trợ sửa khung và lưu lịch sử chỉnh sửa |
| e454767 | Lưu minh chứng, thêm test và bảo toàn byte fixture |

Các commit sau khi hoàn thiện báo cáo sẽ được bổ sung khi chốt bài.
Đối chiếu tác giả bằng git shortlog -sne --all.

Nguyễn Mạnh Đức dự kiến trình bày demo.
Chưa ghi nhận showcase hoặc phản biện đã diễn ra.

## 11 · References

Tài liệu được tham khảo khi hoàn thiện báo cáo ngày 14/11/2026.
Việc dẫn tài liệu không có nghĩa thư viện đó đã được tích hợp.

1. [Torchvision - box_iou](https://docs.pytorch.org/vision/main/generated/torchvision.ops.box_iou.html)
   Vai trò: đối chiếu khái niệm IoU và biểu diễn khung.
   Bài tự cài bbox_iou, không gọi torchvision.

2. [Cleanlab - object_detection.filter](https://docs.cleanlab.ai/stable/cleanlab/object_detection/filter.html)
   Vai trò: tham khảo hướng phát hiện và xếp hạng lỗi nhãn đối tượng.
   Chưa tích hợp hoặc chạy Cleanlab trong PoC hiện tại.

3. docs/tracks/T11.md và README.md của repo.
   Vai trò: yêu cầu đầu ra, metric, review và các mốc nộp bài.

---


**Bảng 3 · Checklist chốt khi nộp**

- [ ] Link repo và tag cuối cùng trong README; input mẫu không chứa PII thật.
- [ ] Đúng 1 lệnh run, 1 lệnh evaluate, 1 lệnh tests; không cần download khi chạy.
- [ ] Có baseline/PoC metrics, ≥1 failure case, reviewer evidence, decision log.
- [ ] Có license/source provenance, data splits, seed, offline environment, GT/eval N.
- [ ] Mỗi thành viên có ≥1 commit thực chất và được nêu minh bạch trong bảng trên.
