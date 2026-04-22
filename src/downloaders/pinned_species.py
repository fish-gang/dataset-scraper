import logging
import time

import requests

from config import (
    DATA_DIR,
    INAT_ALLOWED_LICENSES,
    INAT_API_URL,
    INAT_PER_PAGE,
    PINNED_SPECIES_LIMIT,
)
from src.dataset_store import Dataset
from src.http import get

logger = logging.getLogger(__name__)


def _normalize(name: str) -> str:
    return name.lower().replace(" ", "_")


def run(dataset: Dataset, families: list[dict]) -> None:
    for fam in families:
        family_sci = fam["family_scientific_name"]
        for species in fam.get("pinned_species", []):
            _download_species(
                family_scientific_name=family_sci,
                species_scientific_name=species["species_scientific_name"],
                species_taxon_id=int(species["species_taxon_id"]),
                dataset=dataset,
            )


def _download_species(
    family_scientific_name: str,
    species_scientific_name: str,
    species_taxon_id: int,
    dataset: Dataset,
) -> None:
    # Folder structure: out/data/<family_scientific_name>/<species_scientific_name>/
    out = (
        DATA_DIR
        / _normalize(family_scientific_name)
        / _normalize(species_scientific_name)
    )
    out.mkdir(parents=True, exist_ok=True)

    already = dataset.count_by_taxon(species_taxon_id)
    if already >= PINNED_SPECIES_LIMIT:
        logger.info(f"Skipped (complete): {species_scientific_name} ({already} images)")
        return

    logger.info(f"Downloading: {species_scientific_name} (have {already})")

    page = 1
    downloaded = already

    while downloaded < PINNED_SPECIES_LIMIT:
        params = {
            "taxon_id": species_taxon_id,
            "quality_grade": "research",
            "photos": "true",
            "license": ",".join(INAT_ALLOWED_LICENSES),
            "per_page": INAT_PER_PAGE,
            "page": page,
        }

        results = get(INAT_API_URL, params=params).json().get("results", [])
        if not results:
            break

        for obs in results:
            for photo in obs.get("photos", []):
                if downloaded >= PINNED_SPECIES_LIMIT:
                    break

                # Check photo-level license
                license_code = photo.get("license_code", "")
                if license_code not in INAT_ALLOWED_LICENSES:
                    continue

                # Check that photo has not already been downloaded
                photo_id = photo.get("id")
                if not photo_id or dataset.has_photo(photo_id):
                    continue

                url = photo.get("url")
                if not url:
                    continue

                img_url = url.replace("square", "original")
                ext = img_url.split(".")[-1].split("?")[0] or "jpg"
                path = (
                    out / f"{_normalize(species_scientific_name)}_{downloaded:03}.{ext}"
                )

                try:
                    img = requests.get(img_url, timeout=15)
                    img.raise_for_status()
                except requests.RequestException as exc:
                    logger.debug(f"Failed to download {img_url}: {exc}")
                    continue

                path.write_bytes(img.content)
                dataset.add(obs, photo, path)
                dataset.save()

                downloaded += 1
                logger.info(
                    f"✔ {species_scientific_name}: {downloaded}/{PINNED_SPECIES_LIMIT}"
                )

        page += 1
        time.sleep(0.5)

    logger.info(f"Done: {species_scientific_name} ({downloaded} images)")
