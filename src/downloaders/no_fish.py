import logging
import shutil
import subprocess
from pathlib import Path

from config import DATA_DIR, NO_FISH_LABELS, NO_FISH_LIMIT_PER_CLASS
from src.dataset_store import Dataset, NEGATIVE_LABEL_NO_FISH

logger = logging.getLogger(__name__)

OUT_DIR = DATA_DIR / "no_fish"


def run(dataset: Dataset) -> None:
    already = dataset.count_negative_by_label(NEGATIVE_LABEL_NO_FISH)
    total_target = NO_FISH_LIMIT_PER_CLASS * len(NO_FISH_LABELS)

    if already >= total_target:
        logger.info(f"Skipped no_fish (already complete: {already} images)")
        return

    command_path = shutil.which("oi_download_images")
    if command_path is None:
        raise RuntimeError(
            "'oi_download_images' not found. Make sure 'openimages' is installed: "
            "pip install openimages"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        command_path,
        "--base_dir",
        str(OUT_DIR),
        "--limit",
        str(NO_FISH_LIMIT_PER_CLASS),
        "--labels",
        *NO_FISH_LABELS,
    ]

    logger.info(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"oi_download_images failed with return code {exc.returncode}"
        ) from exc

    _ingest(dataset)


def _ingest(dataset: Dataset) -> None:
    for label in NO_FISH_LABELS:
        label_dir = OUT_DIR / label.lower()
        images_dir = label_dir / "images"

        if not images_dir.exists():
            logger.warning(f"No images dir for label '{label}', skipping")
            continue

        for image_file in sorted(images_dir.iterdir()):
            if not image_file.is_file():
                continue

            dest = _unique_path(OUT_DIR, image_file.stem, image_file.suffix)
            shutil.move(str(image_file), str(dest))

            dataset.add_negative_openimages(
                local_path=dest,
                original_label=label,
            )

        try:
            shutil.rmtree(label_dir)
        except Exception as exc:
            logger.warning(f"Could not remove {label_dir}: {exc}")

    dataset.save()
    logger.info("Ingested no_fish images into dataset")


def _unique_path(directory: Path, stem: str, suffix: str) -> Path:
    candidate = directory / f"{stem}{suffix}"
    i = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{i}{suffix}"
        i += 1
    return candidate
