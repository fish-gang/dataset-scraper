from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Paths
FISHES_JSON = BASE_DIR / "fishes.json"
OUT_DIR = BASE_DIR / "out"
DATA_DIR = OUT_DIR / "data"
DATASET_PATH = OUT_DIR / "dataset.json"

# iNaturalist
INAT_API_URL = "https://api.inaturalist.org/v1/observations"
INAT_TAXA_URL = "https://api.inaturalist.org/v1/taxa"
INAT_PER_PAGE = 200
INAT_ALLOWED_LICENSES = {"cc0", "cc-by"}
# Covers all fish species, including jawless fish, cartilaginous fish, and bony fish
INAT_FISH_GROUPS = ("Actinopterygii", "Chondrichthyes")

# Download limits
PINNED_SPECIES_LIMIT = 500
UNKNOWN_FISH_LIMIT = 1000
NO_FISH_LIMIT_PER_CLASS = 50

# HTTP
REQUEST_TIMEOUT = 30
MAX_RETRIES = 4

# No-fish labels (Open Images)
NO_FISH_LABELS = [
    # Urban / everyday
    "Chair",
    "Car",
    "Table",
    "Person",
    "Dog",
    "Cat",
    "Bicycle",
    "Bus",
    "Truck",
    "Motorcycle",
    "Airplane",
    "Boat",
    "House",
    "Bottle",
    # Underwater / coastal
    "Sea turtle",
    "Tortoise",
    "Starfish",
    "Jellyfish",
    "Crab",
    "Lobster",
    "Dolphin",
    "Whale",
    # Natural
    "Mushroom",
    "Tree",
]
