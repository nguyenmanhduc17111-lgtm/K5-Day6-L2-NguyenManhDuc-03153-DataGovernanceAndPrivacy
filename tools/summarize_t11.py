import json
from pathlib import Path

import pandas as pd


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


baseline = pd.read_csv("out/baseline/ranking.csv")
poc = pd.read_csv("out/poc/ranking.csv")
baseline_run = read_json("out/baseline/run_info.json")
poc_run = read_json("out/poc/run_info.json")

if baseline_run["status"] != 0 or poc_run["status"] != 0:
    raise ValueError("Both runs must finish successfully")
if baseline_run["seed"] != poc_run["seed"]:
    raise ValueError("Seeds do not match")
if not baseline["item_id"].is_unique or not poc["item_id"].is_unique:
    raise ValueError("Duplicate candidate IDs")
if set(baseline["item_id"]) != set(poc["item_id"]):
    raise ValueError("Candidate pools do not match")

reviewed = pd.read_csv(
    "reports/review_queue_reviewed.csv", dtype=str
).fillna("")
done = reviewed[reviewed["reviewer_decision"] != ""]
decision_counts = {
    key: int(value)
    for key, value in done["reviewer_decision"].value_counts().items()
}

raw = pd.read_csv(
    "fixtures/t11_label_errors/annotations.csv"
).set_index("ann_id")
corrected = pd.read_csv(
    "out/poc/annotations_reviewed.csv"
).set_index("ann_id")

if not raw.index.is_unique or not corrected.index.is_unique:
    raise ValueError("Duplicate annotation IDs")

added_ids = corrected.index.difference(raw.index).tolist()
removed_ids = raw.index.difference(corrected.index).tolist()
common_ids = raw.index.intersection(corrected.index)

changed = raw.loc[common_ids].ne(corrected.loc[common_ids]).any(axis=1)
edited_ids = changed[changed].index.tolist()

requests = read_json("reports/dev_label_edits.json")
queue_requests = sum(
    request.get("review_scope") == "queue_dev"
    for request in requests
)

summary = {
    "track": "t11",
    "seed": baseline_run["seed"],
    "candidate_pool": {
        "baseline": len(baseline),
        "poc": len(poc),
        "same_ids": True,
        "unique_ids": True,
    },
    "official_metrics": {
        "status": "not_evaluated",
        "gt_available": Path(
            "fixtures/t11_label_errors/gt/gt_errors.csv"
        ).is_file(),
        "baseline_error_recall_at_b": None,
        "poc_error_recall_at_b": None,
    },
    "dev_review": {
        "queue_size": len(reviewed),
        "reviewed": len(done),
        "decisions": decision_counts,
    },
    "dev_corrections": {
        "added": len(added_ids),
        "edited": len(edited_ids),
        "removed": len(removed_ids),
        "added_ids": added_ids,
        "edited_ids": edited_ids,
        "removed_ids": removed_ids,
        "queue_requests": queue_requests,
        "supplemental_requests": len(requests) - queue_requests,
        "validation": "Human visual review; not hidden-GT verification",
    },
    "runs": {
        "baseline": baseline_run,
        "poc": poc_run,
    },
    "decision": read_json("out/poc/decision.json"),
    "limitations": [
        "Official quality metrics have not been evaluated.",
        "Supplemental corrections are not top-B discoveries.",
        "Runtime includes different baseline and PoC workflow tasks.",
        "Runtime values describe one run, not a benchmark average.",
    ],
}

output = Path("reports/dev_summary.json")
output.write_text(
    json.dumps(summary, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("Saved:", output)
print("Candidates:", len(baseline), "/", len(poc))
print("Reviewed:", len(done), "/", len(reviewed))
print("Decisions:", decision_counts)
print("Added:", len(added_ids))
print("Edited:", len(edited_ids))
print("Removed:", len(removed_ids))
print("Official quality metrics: NOT EVALUATED")

baseline_seconds = baseline_run["runtime_seconds"]
poc_seconds = poc_run["runtime_seconds"]
corrections = summary["dev_corrections"]

section04 = f"""## 04 · Baseline vs PoC

Nguồn số liệu: reports/dev_summary.json.
Nội dung phần này được sinh bằng python -m tools.summarize_t11.

| Nội dung | Baseline | PoC |
|---|---|---|
| Phương pháp | Điểm ngẫu nhiên | Quy tắc đối chiếu nhãn và dự đoán |
| Seed | {baseline_run["seed"]} | {poc_run["seed"]} |
| Số ứng viên toàn bộ dữ liệu | {len(baseline)} | {len(poc)} |
| Commit của lần chạy | {baseline_run["git_sha"]} | {poc_run["git_sha"]} |
| Error Recall@B trên heldout | Chưa đánh giá | Chưa đánh giá |
| Precision@B trên heldout | Chưa đánh giá | Chưa đánh giá |
| Thời gian toàn bộ lần chạy (giây) | {baseline_seconds} | {poc_seconds} |
| Thời gian quy đổi / 100 ứng viên (giây) | {baseline_seconds * 100 / len(baseline):.6f} | {poc_seconds * 100 / len(poc):.6f} |

Hai file ranking có cùng tập ứng viên và không trùng ID.
Đánh giá chính thức cần lọc cùng split heldout và dùng cùng budget
theo evaluator. Chưa có GT nên chưa tính được chênh lệch chất lượng.

Thời gian trên là một lần chạy, không phải trung bình benchmark.
Số quy đổi được hiển thị đến 6 chữ số thập phân và tính theo ứng viên,
không phải số ảnh. Baseline và PoC thực hiện các công việc phụ khác nhau,
nên không dùng bảng này để kết luận tốc độ riêng của thuật toán.

### Kết quả review phát triển của PoC

- Đã review {len(done)}/{len(reviewed)} mục trong hàng đợi dev.
- Giữ nguyên: {decision_counts.get("approve", 0)} mục.
- Sửa trong hàng đợi: {decision_counts.get("edit", 0)} mục.
- Review bổ sung có {corrections["supplemental_requests"]} yêu cầu chỉnh sửa.
- Tổng thay đổi trên bản nhãn: thêm {corrections["added"]},
  sửa {corrections["edited"]}, xóa {corrections["removed"]}.

Đây là kết quả kiểm tra trực quan trên dev, không phải metric chính thức
trên heldout. Các chỉnh sửa bổ sung không tính vào kết quả top-10.
Chưa có review tương đương cho baseline để so sánh chất lượng thủ công.

Kết luận hiện tại: chưa đủ bằng chứng khẳng định PoC tốt hơn baseline.
"""

Path("reports/section04_baseline_vs_poc.md").write_text(
    section04, encoding="utf-8"
)
print("Saved: reports/section04_baseline_vs_poc.md")