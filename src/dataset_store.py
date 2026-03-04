from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

DATASET_PATH = Path(__file__).resolve().parent.parent / "dataset.json"


class Dataset:
    def __init__(self, path: Path = DATASET_PATH):
        self.path = path
        self.records: list[dict] = []

    @classmethod
    def load(cls, path: Path = DATASET_PATH) -> "Dataset":
        ds = cls(path)
        if path.exists():
            ds.records = json.loads(path.read_text(encoding="utf-8"))
            logger.debug(f"Loaded {len(ds.records)} records from {path}")
        return ds

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self.records, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.debug(f"Saved {len(self.records)} records to {self.path}")

    def add(
        self,
        obs: dict,
        photo: dict,
        family_sci_name: str,
        species_sci_name: str,
        local_path: Path,
    ) -> None:
        self.records.append(
            self._build_record(
                obs, photo, family_sci_name, species_sci_name, local_path
            )
        )

    def _build_record(
        self,
        obs: dict,
        photo: dict,
        family_sci_name: str,
        species_sci_name: str,
        local_path: Path,
    ) -> dict:
        taxon = obs.get("taxon", {})

        return {
            "file": str(local_path.relative_to(self.path.parent)),
            "family_scientific_name": family_sci_name,
            "species_scientific_name": species_sci_name,
            "species_common_name": taxon.get("preferred_common_name"),
            "taxon_id": taxon.get("id"),
            "observation_id": obs.get("id"),
            "observation_uri": obs.get("uri"),
            "quality_grade": obs.get("quality_grade"),
            "photo_id": photo.get("id"),
            "photo_url_original": photo.get("url", "").replace("square", "original"),
            "photo_license": photo.get("license_code"),
            "photo_attribution": photo.get("attribution"),
        }

    def __len__(self) -> int:
        return len(self.records)

    def __repr__(self) -> str:
        return f"Dataset(path={self.path}, records={len(self.records)})"
