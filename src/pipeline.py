"""YOUR PoC PIPELINE — this is the file your group owns.

Lab contract = 5 automated steps, run by `python -m src.main ...`:
    01 load      input + provenance check (manifest.csv)
    02 process   your algorithm / model (the research part)
    03 rank      prioritise for a fixed review budget B
    04 review    human-in-the-loop: queue -> reviewer decisions -> overrides + audit log
    05 decide    GO / HOLD / REWORK (or track equivalent) with reason_code + owner, write outputs

Required output: out/<pred_file> with the columns listed for your track in
docs/tracks/TXX.md (also in src/metrics/tracks.py::TRACKS). Then evaluate with
    python -m src.evaluate --track tXX --pred out/<pred_file>

Rules: never read fixtures/*/gt/ here (the GT guard will stop you); seed everything via ctx.rng;
no network calls; fail loudly on missing models instead of downloading.
See src/examples/random_baseline.py for a minimal end-to-end wiring example.
"""
from __future__ import annotations

import pandas as pd
from .dev_review import apply_dev_additions

from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.manifest import verify_manifest
from .common.review import load_review_decisions, make_review_queue, write_review_queue
from .metrics.tracks import get_track


# ---------------------------------------------------------------- 01 load
def load(ctx: RunContext) -> dict:
    if ctx.track != "t11":
        raise NotImplementedError(
            f"This pipeline supports t11 only; received {ctx.track}"
        )

    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems:
        ctx.audit.log(actor="pipeline", action="provenance_problems", item_id=str(manifest), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")
    data = {"manifest": pd.read_csv(manifest) if manifest.exists() else None}
    data["images"] = pd.read_csv(ctx.input_dir / "images.csv")
    data["annotations"] = pd.read_csv(ctx.input_dir / "annotations.csv")
    data["predictions"] = pd.read_csv(ctx.input_dir / "model_predictions.csv")
    return data
 
def bbox_iou(a, b) -> float:
    # Phần giao nhau của hai khung
    left = max(a["x"], b["x"])
    top = max(a["y"], b["y"])
    right = min(a["x"] + a["w"], b["x"] + b["w"])
    bottom = min(a["y"] + a["h"], b["y"] + b["h"])

    intersection = max(0.0, right - left) * max(0.0, bottom - top)

    # Diện tích hợp = tổng diện tích - phần giao
    area_a = max(0.0, a["w"]) * max(0.0, a["h"])
    area_b = max(0.0, b["w"]) * max(0.0, b["h"])
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0

# ---------------------------------------------------------------- 02 process
def process(ctx: RunContext, data: dict) -> pd.DataFrame:
    annotations = data["annotations"]
    predictions = data["predictions"]
    results = []

    for _, ann in annotations.iterrows():
        candidates = predictions[
            predictions["image_id"] == ann["image_id"]
        ]

        best_iou = 0.0
        best_prediction = None

        for _, pred in candidates.iterrows():
            overlap = bbox_iou(ann, pred)
            if overlap > best_iou:
                best_iou = overlap
                best_prediction = pred

        score = 1.0 - best_iou
        reason = "box_disagreement"

        if best_prediction is None:
            reason = "no_overlapping_prediction"
        elif ann["class"] != best_prediction["class"]:
            score = max(score, 0.9)
            reason = "class_disagreement"
        # Tìm nhãn khác cùng ảnh và cùng loại đối tượng
        other_annotations = annotations[
            (annotations["image_id"] == ann["image_id"])
            & (annotations["class"] == ann["class"])
            & (annotations["ann_id"] != ann["ann_id"])
        ]

        duplicate_iou = 0.0
        for _, other in other_annotations.iterrows():
            duplicate_iou = max(duplicate_iou, bbox_iou(ann, other))

        # Hai khung trùng nhau nhiều có thể là nhãn bị lặp
        if duplicate_iou >= 0.85:
            score = max(score, duplicate_iou)
            reason += ";possible_duplicate"
        results.append({
            "item_id": ann["ann_id"],
            "score": score,
            "reason": reason,
        })

        # Kiểm tra khả năng thiếu nhãn trên từng ảnh
    for image_id in data["images"]["image_id"]:
        image_annotations = annotations[
            annotations["image_id"] == image_id
        ]
        image_predictions = predictions[
            predictions["image_id"] == image_id
        ]

        missing_score = 0.0

        for _, pred in image_predictions.iterrows():
            if pred["conf"] < 0.7:
                continue

            best_overlap = 0.0
            for _, ann in image_annotations.iterrows():
                best_overlap = max(best_overlap, bbox_iou(pred, ann))

            if best_overlap < 0.3:
                suspicion = float(pred["conf"]) * (1.0 - best_overlap)
                missing_score = max(missing_score, suspicion)

        results.append({
            "item_id": f"img:{image_id}",
            "score": missing_score,
            "reason": (
                "possible_missing_annotation"
                if missing_score > 0
                else "no_missing_signal"
            ),
        })

    return pd.DataFrame(results, columns=["item_id", "score", "reason"])

# ---------------------------------------------------------------- 03 rank
def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    annotations = pd.read_csv(ctx.input_dir / "annotations.csv")
    images = pd.read_csv(ctx.input_dir / "images.csv")

    ann_images = annotations.set_index("ann_id")["image_id"].to_dict()
    image_splits = images.set_index("image_id")["split"].to_dict()

    pool = scored.copy()
    pool["image_id"] = pool["item_id"].map(
        lambda item: item[4:]
        if item.startswith("img:")
        else ann_images.get(item)
    )
    pool["slice"] = pool["image_id"].map(image_splits)

    # Chỉ review thủ công tập dev trong quá trình phát triển
    pool = pool[pool["slice"] == "dev"].copy()

    budget = int(ctx.param("budget", 10))
    queue = make_review_queue(
        pool,
        id_col="item_id",
        score_col="score",
        budget=budget,
        reason_col="reason",
        slice_col="slice",
    )
    write_review_queue(queue, ctx.out("review_queue.csv"))
    return queue

# ---------------------------------------------------------------- 04 review
def review(ctx: RunContext, scored: pd.DataFrame,
           queue: pd.DataFrame) -> pd.DataFrame:
    import json
    from pathlib import Path

    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if not reviewed_path.exists():
        reviewed_path = Path("reports/review_queue_reviewed.csv")
    request_path = Path("reports/dev_label_edits.json")
    ctx.stats["n_reviewed"] = 0

    requests = []
    if request_path.exists():
        requests = json.loads(request_path.read_text(encoding="utf-8-sig"))

    queue_requests = [
        r for r in requests if r.get("review_scope") == "queue_dev"
    ]
    queue_edits = {r["item_id"]: r for r in queue_requests}
    if len(queue_edits) != len(queue_requests):
        raise ValueError("Duplicate queue edit requests")

    if not reviewed_path.exists():
        if queue_edits:
            raise ValueError("Queue edits require a reviewed queue")
        return scored

    reviewed = load_review_decisions(reviewed_path)
    if reviewed["item_id"].duplicated().any():
        raise ValueError("Duplicate item_id in reviewed file")

    edit_ids = set(
        reviewed.loc[reviewed["reviewer_decision"] == "edit", "item_id"]
    )
    if edit_ids != set(queue_edits):
        raise ValueError("Review edits and queue edit requests must match")

    valid_ids = set(queue["item_id"])
    for row in reviewed.itertuples(index=False):
        if row.item_id not in valid_ids:
            raise ValueError(f"Item outside current queue: {row.item_id}")
        if row.reviewer_decision not in {"approve", "skip", "escalate", "edit"}:
            raise ValueError("Unsupported review decision")

        if row.reviewer_decision == "edit":
            request = queue_edits[row.item_id]
            if request["operation"] != "edit":
                raise ValueError("Expected an edit operation")
            if json.loads(row.override_value) != request["annotation"]:
                raise ValueError("Override does not match requested annotation")
            if row.reviewer != request["reviewer"]:
                raise ValueError("Reviewer names do not match")
            if row.evidence_path != request["evidence_path"]:
                raise ValueError("Review evidence paths do not match")

    for row in reviewed.itertuples(index=False):
        ctx.audit.log(
            actor=row.reviewer,
            action=f"review:{row.reviewer_decision}",
            item_id=row.item_id,
            after={
                "decision": row.reviewer_decision,
                "override_value": row.override_value,
                "evidence_path": row.evidence_path,
                "reviewed_at": row.reviewed_at,
            },
            reason=row.review_note,
        )

    ctx.stats["n_reviewed"] = len(reviewed)
    ctx.stats["n_queue_edits"] = len(edit_ids)
    return scored

# ---------------------------------------------------------------- 05 decide
def decide(ctx: RunContext, final: pd.DataFrame) -> Decision:
    from pathlib import Path

    queue = pd.read_csv(ctx.out("review_queue.csv"))
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if not reviewed_path.exists():
        reviewed_path = Path("reports/review_queue_reviewed.csv")

    reason_code = "REVIEW_INCOMPLETE"
    reason = "The selected development review queue is not fully resolved."

    if reviewed_path.exists():
        reviewed = load_review_decisions(reviewed_path)
        resolved = set(
            reviewed.loc[
                reviewed["reviewer_decision"].isin(["approve", "edit"]),
                "item_id",
            ]
        )

        if (reviewed["reviewer_decision"] == "escalate").any():
            reason_code = "REVIEW_ESCALATED"
            reason = "At least one item requires further human review."
        elif len(queue) > 0 and set(queue["item_id"]).issubset(resolved):
            reason_code = "HELDOUT_EVALUATION_PENDING"
            reason = (
                "Development review is complete. "
                f"Added {ctx.stats.get('n_dev_added', 0)} annotations and "
                f"edited {ctx.stats.get('n_dev_edited', 0)} annotations. "
                "Heldout evaluation is required before a release decision."
            )

    return Decision(
        status="HOLD",
        reason_code=reason_code,
        reason=reason,
        owner=ctx.config["owner"],
        scope=ctx.track,
    )

def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    data = load(ctx)
    scored = process(ctx, data)
    ctx.stats["n_items"] = len(scored)

    queue = rank(ctx, scored)
    final = review(ctx, scored, queue)
    apply_dev_additions(ctx)

    columns = spec.pred_columns + [
        column for column in final.columns
        if column not in spec.pred_columns
    ]
    final[columns].to_csv(ctx.out(spec.pred_file), index=False)

    write_decision(
        decide(ctx, final),
        ctx.out("decision.json"),
        ctx.out("decision_log.csv"),
    )
