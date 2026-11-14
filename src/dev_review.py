import json
import math
from pathlib import Path

import pandas as pd


def apply_dev_additions(ctx):
    annotations = pd.read_csv(ctx.input_dir / "annotations.csv")
    images = pd.read_csv(ctx.input_dir / "images.csv").set_index("image_id")
    request_path = Path("reports/dev_label_edits.json")

    requests = []
    if request_path.exists():
        requests = json.loads(request_path.read_text(encoding="utf-8-sig"))
    if not isinstance(requests, list):
        raise ValueError("Dev edit requests must be a list")

    corrected = annotations.copy()
    seen_ids = set()
    changes = []

    for request in requests:
        operation = request.get("operation")
        if operation not in {"add", "edit"}:
            raise ValueError("Supported operations: add, edit")
        if not request.get("reviewer", "").strip():
            raise ValueError("Reviewer is required")
        if not request.get("reason", "").strip():
            raise ValueError("Review reason is required")
        if not Path(request.get("evidence_path", "")).is_file():
            raise ValueError("Evidence image is missing")

        row = dict(request["annotation"])
        if set(row) != set(annotations.columns):
            raise ValueError("Annotation columns do not match")
        if row["ann_id"] in seen_ids:
            raise ValueError("Multiple requests for the same annotation")
        if row["image_id"] not in images.index:
            raise ValueError("Unknown image ID")

        image = images.loc[row["image_id"]]
        if image["split"] != "dev":
            raise ValueError("Manual development edits must target dev")

        expected_item = (
            f"img:{row['image_id']}" if operation == "add" else row["ann_id"]
        )
        if request["item_id"] != expected_item:
            raise ValueError("Request item_id does not match annotation")
        if row["class"] not in {"car", "motorbike", "pedestrian", "sign"}:
            raise ValueError("Unknown annotation class")

        for key in ("x", "y", "w", "h"):
            row[key] = float(row[key])
            if not math.isfinite(row[key]):
                raise ValueError("Box coordinates must be finite")

        x, y, w, h = (row[key] for key in ("x", "y", "w", "h"))
        if x < 0 or y < 0 or w <= 0 or h <= 0:
            raise ValueError("Invalid bounding box")
        if x + w > image["width"] or y + h > image["height"]:
            raise ValueError("Bounding box exceeds image bounds")

        mask = corrected["ann_id"] == row["ann_id"]
        before = None

        if operation == "add":
            if mask.any():
                raise ValueError(f"Annotation already exists: {row['ann_id']}")
            corrected = pd.concat(
                [corrected, pd.DataFrame([row])],
                ignore_index=True,
            )
        else:
            if int(mask.sum()) != 1:
                raise ValueError("Edit must target exactly one existing annotation")
            before = corrected.loc[mask].iloc[0].to_dict()
            if before["image_id"] != row["image_id"]:
                raise ValueError("Cannot move an annotation to another image")
            for column, value in row.items():
                corrected.loc[mask, column] = value

        seen_ids.add(row["ann_id"])
        changes.append((request, before, row))

    # Chỉ xuất file sau khi mọi yêu cầu đều hợp lệ
    corrected.to_csv(ctx.out("annotations_reviewed.csv"), index=False)

    for request, before, row in changes:
        ctx.audit.log(
            actor=request["reviewer"],
            action=f"dev_review:{request['operation']}_annotation",
            item_id=request["item_id"],
            before=before,
            after=row,
            reason=request["reason"],
            evidence_path=request["evidence_path"],
            review_scope=request.get("review_scope", "supplemental_dev"),
        )

    ctx.stats["n_dev_added"] = sum(
        request["operation"] == "add" for request in requests
    )
    ctx.stats["n_dev_edited"] = sum(
        request["operation"] == "edit" for request in requests
    )