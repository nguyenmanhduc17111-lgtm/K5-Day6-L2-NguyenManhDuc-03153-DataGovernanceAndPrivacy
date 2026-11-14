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

    known_ids = set(annotations["ann_id"])
    additions = []
    changes = []

    for request in requests:
        if request["operation"] != "add":
            raise ValueError("Only add operations are supported here")
        if not request.get("reviewer", "").strip():
            raise ValueError("Reviewer is required")
        if not request.get("reason", "").strip():
            raise ValueError("Review reason is required")
        if not Path(request.get("evidence_path", "")).is_file():
            raise ValueError("Evidence image is missing")

        row = dict(request["annotation"])
        if set(row) != set(annotations.columns):
            raise ValueError("Annotation columns do not match")
        if row["ann_id"] in known_ids:
            raise ValueError(f"Duplicate annotation ID: {row['ann_id']}")
        if row["image_id"] not in images.index:
            raise ValueError("Unknown image ID")

        image = images.loc[row["image_id"]]
        if image["split"] != "dev":
            raise ValueError("Manual development edits must target dev")
        if request["item_id"] != f"img:{row['image_id']}":
            raise ValueError("Request item_id does not match image_id")
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

        known_ids.add(row["ann_id"])
        additions.append(row)
        changes.append((request, row))

    corrected = pd.concat(
        [annotations, pd.DataFrame(additions)],
        ignore_index=True,
    )
    corrected.to_csv(ctx.out("annotations_reviewed.csv"), index=False)

    for request, row in changes:
        ctx.audit.log(
            actor=request["reviewer"],
            action="dev_review:add_annotation",
            item_id=request["item_id"],
            before=None,
            after=row,
            reason=request["reason"],
            evidence_path=request["evidence_path"],
            review_scope="supplemental_dev",
        )

    ctx.stats["n_dev_added"] = len(additions)