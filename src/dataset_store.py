import json
import logging
from pathlib import Path

from config import DATASET_PATH

logger = logging.getLogger(__name__)

NEGATIVE_LABEL_NO_FISH = "no_fish"
NEGATIVE_LABEL_UNKNOWN_FISH = "unknown_fish"

SOURCE_INATURALIST = "inaturalist"
SOURCE_OPENIMAGES = "openimages"


class Dataset:
    def __init__(self, path: Path = DATASET_PATH):
        self.path = path
        self.records: list[dict] = []
        self.negative_records: list[dict] = []
        self._photo_ids: set[int] = set()
        self._negative_photo_ids: set[int] = set()
        self._labels: list[dict] = []

    @classmethod
    def load(cls, path: Path = DATASET_PATH) -> "Dataset":
        ds = cls(path)
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            ds.records = raw.get("data", [])
            ds.negative_records = raw.get("negative_data", [])
            ds._labels = raw.get("labels", [])
            ds._photo_ids = {r["photo_id"] for r in ds.records if r.get("photo_id")}
            ds._negative_photo_ids = {
                r["meta"]["photo_id"]
                for r in ds.negative_records
                if r.get("source") == SOURCE_INATURALIST
                and r.get("meta", {}).get("photo_id")
            }
            logger.debug(
                f"Loaded {len(ds.records)} records and "
                f"{len(ds.negative_records)} negative records from {path}"
            )
        return ds

    def set_labels(self, families: list[dict]) -> None:
        self._labels = []
        for fam in families:
            for species in fam.get("pinned_species", []):
                self._labels.append(
                    {
                        "species_taxon_id": species["species_taxon_id"],
                        "family_taxon_id": fam["family_taxon_id"],
                        "family_common_name": fam["family_common_name"],
                        "family_scientific_name": fam["family_scientific_name"],
                        "species_common_name": species["species_common_name"],
                        "species_scientific_name": species["species_scientific_name"],
                    }
                )

    def save(self) -> None:
        counts: dict[int, int] = {}
        for r in self.records:
            tid = r["species_taxon_id"]
            counts[tid] = counts.get(tid, 0) + 1

        labels_with_counts = [
            {**label, "image_count": counts.get(label["species_taxon_id"], 0)}
            for label in self._labels
        ]

        negative_counts: dict[str, int] = {}
        for r in self.negative_records:
            lid = r["label_id"]
            negative_counts[lid] = negative_counts.get(lid, 0) + 1

        negative_labels = [
            {"label_id": label_id, "image_count": negative_counts.get(label_id, 0)}
            for label_id in (NEGATIVE_LABEL_NO_FISH, NEGATIVE_LABEL_UNKNOWN_FISH)
        ]

        output = {
            "labels": labels_with_counts,
            "negative_labels": negative_labels,
            "data": self.records,
            "negative_data": self.negative_records,
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.debug(
            f"Saved {len(self.records)} records and "
            f"{len(self.negative_records)} negative records to {self.path}"
        )

    # ── Pinned species ────────────────────────────────────────────────────────

    def add(self, obs: dict, photo: dict, local_path: Path) -> None:
        record = self._build_inat_record(obs, photo, local_path)
        self.records.append(record)
        self._photo_ids.add(record["photo_id"])

    def has_photo(self, photo_id: int) -> bool:
        return photo_id in self._photo_ids

    def count_by_taxon(self, species_taxon_id: int) -> int:
        return sum(1 for r in self.records if r["species_taxon_id"] == species_taxon_id)

    # ── Negative data ─────────────────────────────────────────────────────────

    def add_negative_inat(self, local_path: Path, obs: dict, photo: dict) -> None:
        taxon = obs.get("taxon") or {}
        record = {
            "label_id": NEGATIVE_LABEL_UNKNOWN_FISH,
            "file": str(local_path.relative_to(self.path.parent)),
            "source": SOURCE_INATURALIST,
            "meta": {
                "photo_id": photo.get("id"),
                "observation_id": obs.get("id"),
                "observation_uri": obs.get("uri"),
                "photo_url_original": photo.get("url", "").replace(
                    "square", "original"
                ),
                "photo_license": photo.get("license_code"),
                "photo_attribution": photo.get("attribution"),
                "taxon_id": taxon.get("id"),
                "taxon_scientific_name": taxon.get("name"),
            },
        }
        self.negative_records.append(record)
        if photo_id := photo.get("id"):
            self._negative_photo_ids.add(photo_id)

    def add_negative_openimages(self, local_path: Path, original_label: str) -> None:
        record = {
            "label_id": NEGATIVE_LABEL_NO_FISH,
            "file": str(local_path.relative_to(self.path.parent)),
            "source": SOURCE_OPENIMAGES,
            "meta": {
                "original_label": original_label,
            },
        }
        self.negative_records.append(record)

    def has_negative_photo(self, photo_id: int) -> bool:
        return photo_id in self._negative_photo_ids

    def count_negative_by_label(self, label_id: str) -> int:
        return sum(1 for r in self.negative_records if r["label_id"] == label_id)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_inat_record(self, obs: dict, photo: dict, local_path: Path) -> dict:
        return {
            "species_taxon_id": obs.get("taxon", {}).get("id"),
            "file": str(local_path.relative_to(self.path.parent)),
            "observation_id": obs.get("id"),
            "observation_uri": obs.get("uri"),
            "photo_id": photo.get("id"),
            "photo_url_original": photo.get("url", "").replace("square", "original"),
            "photo_license": photo.get("license_code"),
            "photo_attribution": photo.get("attribution"),
        }

    def __len__(self) -> int:
        return len(self.records)

    def __repr__(self) -> str:
        return (
            f"Dataset(path={self.path}, records={len(self.records)}, "
            f"negative_records={len(self.negative_records)})"
        )
