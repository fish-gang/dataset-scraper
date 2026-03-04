from pathlib import Path
import requests
import json
import time
import logging

from src.dataset_store import Dataset
from src.http import get

logger = logging.getLogger(__name__)

API_URL = "https://api.inaturalist.org/v1/observations"
DEFAULT_MAX_IMAGES = 500
PER_PAGE = 200 # Maximum is 200
ALLOWED_LICENSES = {"cc0", "cc-by"}

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
    out.mkdir(parents=True, exist_ok=True)

    already_downloaded = dataset.count_by_taxon(taxon_id)
    if already_downloaded >= DEFAULT_MAX_IMAGES:
        logger.warning(
            f"Skipped (already complete): {family_dir}/{species_dir} ({already_downloaded} images)"
        )
        return

    logger.info(
        f"Start download for: {family_dir}/{species_dir} (already have {already_downloaded})"
    )

    page = 1
    downloaded = already_downloaded

    while downloaded < DEFAULT_MAX_IMAGES:
        params = {
            "taxon_id": taxon_id,
            "quality_grade": "research",
            "photos": "true",
            "license": ",".join(ALLOWED_LICENSES),
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

                # Check photo-level license
                photo_license = photo.get("license_code", "")
                if photo_license not in ALLOWED_LICENSES:
                    logger.debug(f"Skipped photo with license: {photo_license}")
                    continue

                # Check that photo has not already been downloaded
                photo_id = photo.get("id")
                if not photo_id or dataset.has_photo(photo_id):
                    logger.debug(f"Skipped duplicate photo: {photo_id}")
                    continue

                url = photo.get("url")
                if not url:
                    continue

                img_url = url.replace("square", "original")
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
