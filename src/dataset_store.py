from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent / "out"
DATASET_PATH = OUT_DIR / "dataset.json"


class Dataset:
    def __init__(self, path: Path = DATASET_PATH):
        self.path = path
        self.records: list[dict] = []
        self._photo_ids: set[int] = set()
        self._labels: list[dict] = []

    @classmethod
    def load(cls, path: Path = DATASET_PATH) -> "Dataset":
        ds = cls(path)
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            ds.records = raw.get("data", [])
            ds._labels = raw.get("labels", [])
            ds._photo_ids = {r["photo_id"] for r in ds.records}
            logger.debug(f"Loaded {len(ds.records)} records from {path}")
        return ds

    def set_labels(self, families: list[dict]) -> None:
        """Build labels from fishes.json structure. Call once before scraping."""
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

        # Attach counts to labels
        labels_with_counts = [
            {**label, "image_count": counts.get(label["species_taxon_id"], 0)}
            for label in self._labels
        ]

        output = {
            "labels": labels_with_counts,
            "data": self.records,
        }

        self.path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.debug(f"Saved {len(self.records)} records to {self.path}")

    def add(
        self,
        obs: dict,
        photo: dict,
        local_path: Path,
    ) -> None:
        record = self._build_record(
            obs, photo, local_path
        )
        self.records.append(record)
        self._photo_ids.add(record["photo_id"])

    def has_photo(self, photo_id: int) -> bool:
        return photo_id in self._photo_ids

    def count_by_taxon(self, species_taxon_id: int) -> int:
        return sum(1 for r in self.records if r["species_taxon_id"] == species_taxon_id)

    def _build_record(
        self,
        obs: dict,
        photo: dict,
        local_path: Path,
    ) -> dict:
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
        return f"Dataset(path={self.path}, records={len(self.records)})"
