import json
from pathlib import Path

import pandas as pd

root = Path("fixtures/t11_label_errors")
images = pd.read_csv(root / "images.csv")
annotations = pd.read_csv(root / "annotations.csv")
manifest = pd.read_csv(root / "manifest.csv")

joined = annotations.merge(
    images[["image_id", "split"]],
    on="image_id",
    how="left",
    validate="many_to_one",
)
if joined["split"].isna().any():
    raise ValueError("Some annotations have no image split")

counts = images.groupby("split").size().rename("images").to_frame()
counts["annotations"] = joined.groupby("split").size()
counts = counts.fillna(0).astype(int)
counts["candidates"] = counts["images"] + counts["annotations"]

inventory = {
    "images_total": len(images),
    "annotations_total": len(annotations),
    "candidates_total": len(images) + len(annotations),
    "splits": counts.reset_index().to_dict("records"),
    "sources": sorted(manifest["source"].dropna().unique().tolist()),
    "licenses": sorted(manifest["license"].dropna().unique().tolist()),
}

Path("reports/data_inventory.json").write_text(
    json.dumps(inventory, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(counts.to_string())
print("Sources:", inventory["sources"])
print("Licenses:", inventory["licenses"])
print("Saved: reports/data_inventory.json")