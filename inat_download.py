from pathlib import Path
import requests
import json
import time

API_URL = "https://api.inaturalist.org/v1/observations"
DEFAULT_MAX_IMAGES = 20
PER_PAGE = 200
LICENSE = "cc0"

BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "fishes.json"
OUT_DIR = BASE_DIR / "out"


def download_images_for_taxon(family_sci_name: str, species_sci_name: str, taxon_id: int):
    # Folder structure: out/<family_sci_name>/<species_sci_name>/
    out = OUT_DIR / family_sci_name / species_sci_name

    if out.exists():
        print(f"Skipped (already exists): {family_sci_name}/{species_sci_name}")
        return

    out.mkdir(parents=True, exist_ok=True)

    page = 1
    downloaded = 0

    while downloaded < DEFAULT_MAX_IMAGES:
        params = {
            "taxon_id": taxon_id,
            "quality_grade": "research",
            "photos": "true",
            "license": LICENSE,
            "per_page": PER_PAGE,
            "page": page,
        }

        r = requests.get(API_URL, params=params, timeout=15)
        r.raise_for_status()
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
                ext = img_url.split(".")[-1].split("?")[0] or "jpg"
                path = out / f"img_{downloaded:03}.{ext}"

                try:
                    img = requests.get(img_url, timeout=15)
                    img.raise_for_status()
                except requests.RequestException:
                    continue

                path.write_bytes(img.content)
                downloaded += 1
                print(f"✔ {family_sci_name}/{species_sci_name}: {downloaded}")

        page += 1
        time.sleep(0.5)

    print(f"Finished with {family_sci_name}/{species_sci_name}: {downloaded} Images\n")


def main():
    families = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    for fam in families:
        family_sci = fam["scientific_name"]

        for sp in fam.get("pinned_species", []):
            species_sci = sp["scientific_name"]
            taxon_id = int(sp["taxon_id"])

            print(f"\nStart download for: {family_sci}/{species_sci}")
            download_images_for_taxon(family_sci, species_sci, taxon_id)


if __name__ == "__main__":
    main()
