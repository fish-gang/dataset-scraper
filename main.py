import json
import logging
import sys

from config import FISHES_JSON
from src.dataset_store import Dataset
from src.downloaders import no_fish, pinned_species, unknown_fish

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def main() -> None:
    if not FISHES_JSON.exists():
        raise FileNotFoundError(f"fishes.json not found: {FISHES_JSON}")

    families = json.loads(FISHES_JSON.read_text(encoding="utf-8"))
    dataset = Dataset.load()
    dataset.set_labels(families)

    logger.info("=== Step 1/3: Pinned species ===")
    pinned_species.run(dataset, families)

    # logger.info("=== Step 2/3: Unknown fish ===")
    # unknown_fish.run(dataset, families)

    # logger.info("=== Step 3/3: No fish ===")
    # no_fish.run(dataset)

    logger.info("=== All done ===")
    logger.info(f"Pinned species images : {len(dataset.records)}")
    logger.info(f"Negative images       : {len(dataset.negative_records)}")


if __name__ == "__main__":
    main()
