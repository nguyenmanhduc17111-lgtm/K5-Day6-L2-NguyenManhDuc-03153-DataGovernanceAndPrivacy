from types import SimpleNamespace

import pandas as pd

from src.pipeline import process


def make_data(with_predictions=True):
    annotations = pd.DataFrame([
        {
            "ann_id": "correct",
            "image_id": "sample",
            "class": "car",
            "x": 10, "y": 20, "w": 30, "h": 40,
        },
        {
            "ann_id": "wrong_class",
            "image_id": "sample",
            "class": "pedestrian",
            "x": 10, "y": 20, "w": 30, "h": 40,
        },
    ])

    predictions = pd.DataFrame(
        [{
            "image_id": "sample",
            "class": "car",
            "x": 10, "y": 20, "w": 30, "h": 40,
            "conf": 0.95,
        }] if with_predictions else [],
        columns=["image_id", "class", "x", "y", "w", "h", "conf"],
    )

    return {
        "images": pd.DataFrame([{"image_id": "sample"}]),
        "annotations": annotations,
        "predictions": predictions,
    }


def test_class_disagreement_gets_higher_priority():
    result = process(SimpleNamespace(track="t11"), make_data())
    rows = result.set_index("item_id")

    assert set(rows.index) == {"correct", "wrong_class", "img:sample"}
    assert rows.loc["wrong_class", "score"] > rows.loc["correct", "score"]
    assert rows.loc["wrong_class", "reason"] == "class_disagreement"
    assert result["score"].between(0, 1).all()


def test_missing_predictions_are_flagged_without_crashing():
    data = make_data(with_predictions=False)
    result = process(SimpleNamespace(track="t11"), data)
    rows = result.set_index("item_id")

    for item_id in ("correct", "wrong_class"):
        assert rows.loc[item_id, "score"] == 1.0
        assert rows.loc[item_id, "reason"] == "no_overlapping_prediction"

    assert rows.loc["img:sample", "score"] == 0.0
    assert result["score"].notna().all()