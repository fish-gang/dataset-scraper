import logging
import time

import requests

from config import (
    DATA_DIR,
    INAT_ALLOWED_LICENSES,
    INAT_API_URL,
    INAT_PER_PAGE,
    UNKNOWN_FISH_LIMIT,
)
from src.dataset_store import Dataset, NEGATIVE_LABEL_UNKNOWN_FISH
from src.http import get_with_retry
from src.taxon_utils import (
    observation_matches_excluded_taxa,
    resolve_fish_group_taxa,
)

logger = logging.getLogger(__name__)

OUT_DIR = DATA_DIR / "unknown_fish"


def run(dataset: Dataset, families: list[dict]) -> None:
    excluded_taxa = _build_excluded_taxa(families)
    family_taxon_ids = [int(fam["family_taxon_id"]) for fam in families]

    already = dataset.count_negative_by_label(NEGATIVE_LABEL_UNKNOWN_FISH)
    if already >= UNKNOWN_FISH_LIMIT:
        logger.info(f"Skipped unknown_fish (already complete: {already} images)")
        return

    logger.info("Resolving fish group taxa...")
    fish_group_taxa = resolve_fish_group_taxa(family_taxon_ids)
    logger.info(f"Fish group taxa: {fish_group_taxa}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    remaining = UNKNOWN_FISH_LIMIT - already
    downloaded = 0
    pages = {taxon_id: 1 for taxon_id in fish_group_taxa}
    exhausted: set[int] = set()

    while downloaded < remaining and len(exhausted) < len(fish_group_taxa):
        for taxon_id in fish_group_taxa:
            if taxon_id in exhausted or downloaded >= remaining:
                continue

            params = {
                "taxon_id": taxon_id,
                "without_taxon_id": ",".join(str(t) for t in sorted(excluded_taxa)),
                "quality_grade": "research",
                "photos": "true",
                "license": ",".join(INAT_ALLOWED_LICENSES),
                "per_page": INAT_PER_PAGE,
                "page": pages[taxon_id],
                "order_by": "created_at",
                "order": "desc",
            }

            try:
                results = (
                    get_with_retry(INAT_API_URL, params=params)
                    .json()
                    .get("results", [])
                )
            except RuntimeError as exc:
                logger.warning(f"Skipping page for taxon {taxon_id}: {exc}")
                pages[taxon_id] += 1
                continue

            if not results:
                exhausted.add(taxon_id)
                logger.info(f"No more observations for taxon {taxon_id}")
                continue

            for obs in results:
                if observation_matches_excluded_taxa(obs, excluded_taxa):
                    continue

                for photo in obs.get("photos", []) or []:
                    if downloaded >= remaining:
                        break

                    photo_id = photo.get("id")
                    photo_url = photo.get("url")
                    license_code = str(photo.get("license_code") or "").lower()

                    if not photo_id or not photo_url:
                        continue
                    try:
                        photo_id_int = int(photo_id)
                    except (TypeError, ValueError):
                        continue
                    if license_code not in INAT_ALLOWED_LICENSES:
                        continue
                    if dataset.has_negative_photo(photo_id_int):
                        continue

                    img_url = photo_url.replace("square", "original")
                    ext = img_url.split(".")[-1].split("?")[0] or "jpg"
                    path = OUT_DIR / f"unknown_fish_{already + downloaded:04}.{ext}"

                    try:
                        img = requests.get(img_url, timeout=15)
                        img.raise_for_status()
                    except requests.RequestException as exc:
                        logger.debug(f"Failed to download {img_url}: {exc}")
                        continue

                    path.write_bytes(img.content)
                    dataset.add_negative_inat(local_path=path, obs=obs, photo=photo)
                    dataset.save()

                    downloaded += 1
                    logger.info(
                        f"✔ unknown_fish: {already + downloaded}/{UNKNOWN_FISH_LIMIT}"
                    )

            pages[taxon_id] += 1
            time.sleep(0.5)

    logger.info(f"Done: unknown_fish ({already + downloaded} images)")


def _build_excluded_taxa(families: list[dict]) -> set[int]:
    excluded: set[int] = set()
    for fam in families:
        for species in fam.get("pinned_species", []):
            taxon_id = species.get("species_taxon_id")
            if taxon_id is not None:
                try:
                    excluded.add(int(taxon_id))
                except (TypeError, ValueError):
                    pass
    return excluded
