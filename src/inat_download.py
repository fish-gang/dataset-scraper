from pathlib import Path
import requests
import json
import time
import logging

from src.dataset_store import Dataset
from src.http import get

logger = logging.getLogger(__name__)

API_URL = "https://api.inaturalist.org/v1/observations"
DEFAULT_MAX_IMAGES = 250
PER_PAGE = 200
LICENSE = "cc0,cc-by"

BASE_DIR = Path(__file__).resolve().parent.parent
JSON_PATH = BASE_DIR / "fishes.json"
OUT_DIR = BASE_DIR / "out"


def normalize_name(name: str) -> str:
    return name.lower().replace(" ", "_")


def download_images_for_taxon(
    family_sci_name: str, species_sci_name: str, taxon_id: int, dataset: Dataset
):
    # Folder structure: out/<family_sci_name>/<species_sci_name>/
    family_dir = normalize_name(family_sci_name)
    species_dir = normalize_name(species_sci_name)
    out = OUT_DIR / family_dir / species_dir

    if out.exists():
        logger.warning(f"Skipped (already exists): {family_dir}/{species_dir}")
        return

    out.mkdir(parents=True, exist_ok=True)
    logger.info(f"Start download for: {family_dir}/{species_dir}")

    page = 1
    downloaded = 0

    while downloaded < DEFAULT_MAX_IMAGES:
        params = {
            "taxon_id": taxon_id,
            "quality_grade": "research",
            "photos": "true",
            "photo_license": LICENSE,
            "per_page": PER_PAGE,
            "page": page,
        }

        r = get(API_URL, params=params)
        results = r.json().get("results", [])

        if not results:
            break

        for obs in results:
            for photo in obs.get("photos", []):
                if downloaded >= DEFAULT_MAX_IMAGES:
                    break

                url = photo.get("url")
                if not url:
                    continue

                img_url = url.replace("square", "large")
                logger.debug(f"Downloading image: {img_url}")
                ext = img_url.split(".")[-1].split("?")[0] or "jpg"
                path = out / f"{normalize_name(species_sci_name)}_{downloaded:03}.{ext}"

                try:
                    img = requests.get(img_url, timeout=15)
                    img.raise_for_status()
                except requests.RequestException as e:
                    logger.debug(f"Failed to download {img_url}: {e}")
                    continue

                path.write_bytes(img.content)
                dataset.add(obs, photo, family_sci_name, species_sci_name, path)
                dataset.save()

                downloaded += 1
                logger.info(f"✔ {family_dir}/{species_dir}: {downloaded}")

        page += 1
        time.sleep(0.5)

    logger.info(f"Finished {family_dir}/{species_dir}: {downloaded} images")


def run():
    families = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    dataset = Dataset.load()

    for fam in families:
        family_sci = fam["scientific_name"]

        for species in fam.get("pinned_species", []):
            species_sci = species["scientific_name"]
            taxon_id = int(species["taxon_id"])
            download_images_for_taxon(family_sci, species_sci, taxon_id, dataset)
