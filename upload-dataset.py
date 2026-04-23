import json
from pathlib import Path

from datasets import ClassLabel, Dataset, DatasetDict, Features, Image
from huggingface_hub import HfApi

from config import DATASET_PATH, OUT_DIR

REPO_ID = "fish-gang/deepscan-dataset"
REVISION = "v1.0"


def build_dataset() -> Dataset:
    raw = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    # Build label list: pinned species first, then negative classes
    label_names = [
        entry["species_scientific_name"].lower().replace(" ", "_")
        for entry in raw["labels"]
    ]
    label_names += ["unknown_fish", "no_fish"]

    label2idx = {name: idx for idx, name in enumerate(label_names)}

    images = []
    labels = []

    # Pinned species
    taxon_to_label = {
        entry["species_taxon_id"]: entry["species_scientific_name"].lower().replace(" ", "_")
        for entry in raw["labels"]
    }
    for record in raw["data"]:
        path = OUT_DIR / record["file"]
        if not path.exists():
            print(f"Warning: missing file {path}, skipping")
            continue
        images.append(str(path))
        labels.append(label2idx[taxon_to_label[record["species_taxon_id"]]])

    # Negative classes
    for record in raw["negative_data"]:
        path = OUT_DIR / record["file"]
        if not path.exists():
            print(f"Warning: missing file {path}, skipping")
            continue
        images.append(str(path))
        labels.append(label2idx[record["label_id"]])

    features = Features({
        "image": Image(),
        "label": ClassLabel(names=label_names),
    })

    return Dataset.from_dict(
        {"image": images, "label": labels},
        features=features,
    )


def main():
    print("Building dataset...")
    dataset = build_dataset()
    print(f"Total samples: {len(dataset)}")
    print(f"Labels: {dataset.features['label'].names}")

    print(f"Pushing to {REPO_ID} as {REVISION}...")

    dataset_dict = DatasetDict({"train": dataset})
    dataset_dict.push_to_hub(
    REPO_ID,
        commit_message=f"{REVISION}: structured dataset with image and label columns",
    )

    print("Tagging release...")
    api = HfApi()
    api.create_tag(
        repo_id=REPO_ID,
        repo_type="dataset",
        tag=REVISION,
        tag_message=f"{REVISION}: add unknown_fish and no_fish negative classes",
    )

    print("Done.")


if __name__ == "__main__":
    main()