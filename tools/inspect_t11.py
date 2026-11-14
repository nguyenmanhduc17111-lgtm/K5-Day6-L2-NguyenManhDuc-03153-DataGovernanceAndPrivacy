import sys

from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

root = Path("fixtures/t11_label_errors")
image_id = sys.argv[1] if len(sys.argv) > 1 else "lbl_43"
use_reviewed = "--reviewed" in sys.argv[2:]

images = pd.read_csv(root / "images.csv")
info = images.loc[images["image_id"] == image_id].iloc[0]
assert info["split"] == "dev", "Only inspect dev images here."

annotation_path = (
    Path("out/poc/annotations_reviewed.csv")
    if use_reviewed
    else root / "annotations.csv"
)
annotations = pd.read_csv(annotation_path)
predictions = pd.read_csv(root / "model_predictions.csv")

with Image.open(root / info["path"]) as source:
    original = source.convert("RGB")

panels = []

for table, title, color in [
    (annotations, "REVIEWED ANNOTATIONS" if use_reviewed else "CURRENT ANNOTATIONS", "lime"),
    (predictions, "MODEL PREDICTIONS", "orange"),
]:
    panel = original.copy()
    draw = ImageDraw.Draw(panel)

    for _, row in table[table["image_id"] == image_id].iterrows():
        x, y, w, h = (float(row[k]) for k in ("x", "y", "w", "h"))
        draw.rectangle((x, y, x + w, y + h), outline=color, width=2)

        if "ann_id" in row.index:
            label = f'{row["ann_id"]} {row["class"]}'
        else:
            label = f'{row["class"]} {row["conf"]:.2f}'

        draw.text((max(0, x), max(0, y - 12)), label, fill=color)

    enlarged = panel.resize((panel.width * 2, panel.height * 2))
    framed = Image.new("RGB", (enlarged.width, enlarged.height + 30), "black")
    framed.paste(enlarged, (0, 30))
    ImageDraw.Draw(framed).text((10, 8), title, fill=color)
    panels.append(framed)

canvas = Image.new("RGB", (panels[0].width * 2, panels[0].height), "black")
canvas.paste(panels[0], (0, 0))
canvas.paste(panels[1], (panels[0].width, 0))

suffix = "_reviewed" if use_reviewed else ""
output = Path(f"out/poc/inspect_{image_id}{suffix}.png")
output.parent.mkdir(parents=True, exist_ok=True)
canvas.save(output)
print(f"Saved: {output}")