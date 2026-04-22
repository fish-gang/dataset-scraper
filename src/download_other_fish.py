#!/usr/bin/env python3
"""
Dieses Skript erstellt ein "other_fish"-Dataset aus iNaturalist.
Es lädt nur Fischbilder herunter, schließt aber alle Zielarten aus `fishes.json` aus.

Start:
    python3 src/download_other_fish.py

Benötigte Pakete:
    pip install requests

Hinweis:
    `oi_download_images` ist für diesen Fall unpraktisch, weil Taxon-basierte Excludes,
    flache Dateinamen und nachvollziehbare iNaturalist-Metadaten damit nicht zuverlässig
    kontrollierbar sind. Deshalb verwendet dieses Skript direkt die iNaturalist API.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# When this file is started as `python src/download_other_fish.py`, Python puts
# `src/` first on `sys.path`. That shadows the stdlib module `http` with the
# local file `src/http.py`, which breaks `requests`/`urllib3`.
if str(SCRIPT_DIR) in sys.path:
    sys.path.remove(str(SCRIPT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests


DOWNLOAD_COMMAND = "oi_download_images"
OUTPUT_DIR = "/Users/enis.namikaze/Desktop/OtherFish"
LIMIT_TOTAL = 500

API_OBSERVATIONS_URL = "https://api.inaturalist.org/v1/observations"
API_TAXA_URL = "https://api.inaturalist.org/v1/taxa"
JSON_PATH = PROJECT_ROOT / "fishes.json"
METADATA_FILENAME = "metadata.csv"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 4
PER_PAGE = 200
ALLOWED_LICENSES = ("cc0", "cc-by")
GROUP_NAMES = ("Actinopterygii", "Chondrichthyes")
TARGET_FILENAME_PREFIX = "other_fish_"
REQUEST_PAUSE_SECONDS = 0.6
DOWNLOAD_PAUSE_SECONDS = 0.1

METADATA_COLUMNS = [
    "filename",
    "observation_id",
    "photo_id",
    "taxon_id",
    "scientific_name",
    "common_name",
    "url",
]


def load_excluded_taxa(json_path: Path) -> set[int]:
    with json_path.open("r", encoding="utf-8") as handle:
        families = json.load(handle)

    excluded: set[int] = set()
    for family in families:
        for species in family.get("pinned_species", []):
            taxon_id = species.get("species_taxon_id")
            if taxon_id is None:
                continue
            try:
                excluded.add(int(taxon_id))
            except (TypeError, ValueError):
                print(f"Warnung: Ungültige species_taxon_id übersprungen: {taxon_id}")

    return excluded


def load_family_taxa(json_path: Path) -> list[int]:
    with json_path.open("r", encoding="utf-8") as handle:
        families = json.load(handle)

    family_taxa: list[int] = []
    for family in families:
        taxon_id = family.get("family_taxon_id")
        if taxon_id is None:
            continue
        try:
            family_taxa.append(int(taxon_id))
        except (TypeError, ValueError):
            print(f"Warnung: Ungültige family_taxon_id übersprungen: {taxon_id}")
    return family_taxa


def request_json(
    session: requests.Session,
    url: str,
    params: dict | None = None,
) -> dict:
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            wait_seconds = min(2 ** (attempt - 1), 8)
            print(f"Netzwerkfehler bei {url} (Versuch {attempt}/{MAX_RETRIES}): {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(wait_seconds)

    raise RuntimeError(f"API-Anfrage fehlgeschlagen: {url}") from last_error


def fetch_taxon(session: requests.Session, taxon_id: int) -> dict:
    payload = request_json(session, API_TAXA_URL, params={"id": taxon_id})
    results = payload.get("results", [])
    if not results:
        raise RuntimeError(f"Kein Taxon für ID {taxon_id} gefunden.")
    return results[0]


def resolve_taxon_id_by_name(
    session: requests.Session, scientific_name: str
) -> int | None:
    payload = request_json(
        session,
        f"{API_TAXA_URL}/autocomplete",
        params={"q": scientific_name, "per_page": 30},
    )
    for result in payload.get("results", []):
        if str(result.get("name", "")).lower() == scientific_name.lower():
            try:
                return int(result["id"])
            except (KeyError, TypeError, ValueError):
                continue
    return None


def resolve_fish_group_taxa(
    session: requests.Session,
    family_taxa: Iterable[int],
) -> list[int]:
    resolved: dict[str, int] = {}

    for family_taxon_id in family_taxa:
        try:
            family_taxon = fetch_taxon(session, family_taxon_id)
        except RuntimeError as exc:
            print(
                f"Warnung: Konnte Familien-Taxon {family_taxon_id} nicht laden: {exc}"
            )
            continue

        lineage = family_taxon.get("ancestors", [])
        lineage.append(family_taxon)
        for ancestor in lineage:
            name = str(ancestor.get("name", ""))
            if name in GROUP_NAMES:
                try:
                    resolved[name] = int(ancestor["id"])
                except (KeyError, TypeError, ValueError):
                    continue

    for name in GROUP_NAMES:
        if name not in resolved:
            fallback_taxon_id = resolve_taxon_id_by_name(session, name)
            if fallback_taxon_id is not None:
                resolved[name] = fallback_taxon_id

    missing = [name for name in GROUP_NAMES if name not in resolved]
    if missing:
        raise RuntimeError(
            "Konnte die Fisch-Gruppen nicht vollständig auflösen: " + ", ".join(missing)
        )

    return [resolved[name] for name in GROUP_NAMES]


def load_existing_metadata(
    metadata_path: Path,
) -> tuple[list[dict[str, str]], set[int], set[str]]:
    if not metadata_path.exists():
        return [], set(), set()

    rows: list[dict[str, str]] = []
    photo_ids: set[int] = set()
    filenames: set[str] = set()

    with metadata_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            rows.append(row)
            filenames.add(row.get("filename", ""))
            try:
                photo_id = int(row["photo_id"])
                photo_ids.add(photo_id)
            except (KeyError, TypeError, ValueError):
                continue

    return rows, photo_ids, filenames


def get_next_sequence_number(existing_filenames: Iterable[str]) -> int:
    max_number = 0
    for filename in existing_filenames:
        if not filename.startswith(TARGET_FILENAME_PREFIX):
            continue
        stem = Path(filename).stem
        suffix = stem.removeprefix(TARGET_FILENAME_PREFIX)
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return max_number + 1


def sanitize_image_extension(url: str, content_type: str | None = None) -> str:
    path_suffix = Path(urlparse(url).path).suffix.lower()
    if path_suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if path_suffix == ".jpeg" else path_suffix

    if content_type:
        content_type = content_type.lower()
        if "png" in content_type:
            return ".png"
        if "webp" in content_type:
            return ".webp"

    return ".jpg"


def build_unique_output_path(
    output_dir: Path,
    sequence_number: int,
    existing_filenames: set[str],
    extension: str,
) -> tuple[Path, int]:
    candidate_number = sequence_number
    while True:
        filename = f"{TARGET_FILENAME_PREFIX}{candidate_number:04d}{extension}"
        if filename not in existing_filenames and not (output_dir / filename).exists():
            existing_filenames.add(filename)
            return output_dir / filename, candidate_number + 1
        candidate_number += 1


def observation_matches_excluded_taxa(
    observation: dict, excluded_taxa: set[int]
) -> bool:
    taxon = observation.get("taxon") or {}
    taxon_id = taxon.get("id")
    try:
        if taxon_id is not None and int(taxon_id) in excluded_taxa:
            return True
    except (TypeError, ValueError):
        return False

    for ancestor_id in taxon.get("ancestor_ids", []) or []:
        try:
            if int(ancestor_id) in excluded_taxa:
                return True
        except (TypeError, ValueError):
            continue

    return False


def fetch_candidate_observations(
    session: requests.Session,
    fish_group_taxa: list[int],
    excluded_taxa: set[int],
    seen_photo_ids: set[int],
    limit_total: int,
) -> list[dict]:
    candidates: list[dict] = []
    pages = {taxon_id: 1 for taxon_id in fish_group_taxa}
    exhausted_taxa: set[int] = set()

    print(
        "Suche Kandidaten in iNaturalist für Fisch-Gruppen:",
        ", ".join(str(taxon_id) for taxon_id in fish_group_taxa),
    )

    while len(candidates) < limit_total and len(exhausted_taxa) < len(fish_group_taxa):
        for fish_taxon_id in fish_group_taxa:
            if fish_taxon_id in exhausted_taxa or len(candidates) >= limit_total:
                continue

            params = {
                "taxon_id": fish_taxon_id,
                "without_taxon_id": ",".join(
                    str(taxon_id) for taxon_id in sorted(excluded_taxa)
                ),
                "quality_grade": "research",
                "photos": "true",
                "license": ",".join(ALLOWED_LICENSES),
                "per_page": PER_PAGE,
                "page": pages[fish_taxon_id],
                "order_by": "created_at",
                "order": "desc",
            }

            try:
                payload = request_json(session, API_OBSERVATIONS_URL, params=params)
            except RuntimeError as exc:
                print(
                    f"Warnung: Kandidatenseite für Taxon {fish_taxon_id} übersprungen: {exc}"
                )
                pages[fish_taxon_id] += 1
                continue

            observations = payload.get("results", [])
            if not observations:
                exhausted_taxa.add(fish_taxon_id)
                print(f"Keine weiteren Beobachtungen für Fisch-Taxon {fish_taxon_id}.")
                continue

            page_candidates = 0
            for observation in observations:
                if observation_matches_excluded_taxa(observation, excluded_taxa):
                    continue

                for photo in observation.get("photos", []) or []:
                    photo_id = photo.get("id")
                    photo_url = photo.get("url")
                    license_code = str(photo.get("license_code") or "").lower()
                    if not photo_id or not photo_url:
                        continue
                    try:
                        photo_id_int = int(photo_id)
                    except (TypeError, ValueError):
                        continue
                    if photo_id_int in seen_photo_ids:
                        continue
                    if license_code not in ALLOWED_LICENSES:
                        continue

                    candidates.append(
                        {
                            "observation": observation,
                            "photo": photo,
                        }
                    )
                    seen_photo_ids.add(photo_id_int)
                    page_candidates += 1

                    if len(candidates) >= limit_total:
                        break
                if len(candidates) >= limit_total:
                    break

            print(
                f"Kandidaten gesammelt: {len(candidates)}/{limit_total} "
                f"(Taxon {fish_taxon_id}, Seite {pages[fish_taxon_id]}, neu {page_candidates})"
            )
            pages[fish_taxon_id] += 1
            time.sleep(REQUEST_PAUSE_SECONDS)

    return candidates


def download_image(
    session: requests.Session,
    image_url: str,
    target_path: Path,
) -> bool:
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with session.get(
                image_url, stream=True, timeout=REQUEST_TIMEOUT
            ) as response:
                response.raise_for_status()
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with target_path.open("wb") as handle:
                    shutil.copyfileobj(response.raw, handle)
            return True
        except requests.RequestException as exc:
            last_error = exc
            wait_seconds = min(2 ** (attempt - 1), 8)
            print(
                f"Bilddownload fehlgeschlagen für {image_url} "
                f"(Versuch {attempt}/{MAX_RETRIES}): {exc}"
            )
            if target_path.exists():
                target_path.unlink(missing_ok=True)
            if attempt < MAX_RETRIES:
                time.sleep(wait_seconds)

    print(f"Warnung: Bild dauerhaft übersprungen: {image_url} ({last_error})")
    return False


def build_metadata_row(
    filename: str, observation: dict, photo: dict, image_url: str
) -> dict[str, str]:
    taxon = observation.get("taxon") or {}
    return {
        "filename": filename,
        "observation_id": str(observation.get("id", "")),
        "photo_id": str(photo.get("id", "")),
        "taxon_id": str(taxon.get("id", "")),
        "scientific_name": str(taxon.get("name", "")),
        "common_name": str(
            taxon.get("preferred_common_name")
            or (taxon.get("preferred_common_names") or [{}])[0].get("name", "")
        ),
        "url": image_url,
    }


def save_metadata(metadata_path: Path, rows: list[dict[str, str]]) -> None:
    with metadata_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METADATA_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    print(
        "Starte other-fish Download. "
        f"Konfiguration: OUTPUT_DIR={OUTPUT_DIR}, LIMIT_TOTAL={LIMIT_TOTAL}"
    )
    print(
        f"Hinweis: '{DOWNLOAD_COMMAND}' wird bewusst nicht verwendet, "
        "weil der direkte iNaturalist-API-Download hier zuverlässiger ist."
    )

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not JSON_PATH.exists():
        raise FileNotFoundError(f"fishes.json nicht gefunden: {JSON_PATH}")

    excluded_taxa = load_excluded_taxa(JSON_PATH)
    family_taxa = load_family_taxa(JSON_PATH)
    metadata_path = output_dir / METADATA_FILENAME
    existing_rows, existing_photo_ids, existing_filenames = load_existing_metadata(
        metadata_path
    )
    next_sequence_number = get_next_sequence_number(existing_filenames)

    print(f"Ausgeschlossene Zielarten: {len(excluded_taxa)} Taxa")
    print(f"Bereits vorhandene Bilder laut metadata.csv: {len(existing_rows)}")

    if len(existing_rows) >= LIMIT_TOTAL:
        print(
            f"LIMIT_TOTAL={LIMIT_TOTAL} bereits erreicht. "
            "Es werden keine weiteren Bilder heruntergeladen."
        )
        return

    remaining = LIMIT_TOTAL - len(existing_rows)

    rows = list(existing_rows)
    downloaded_now = 0

    try:
        with requests.Session() as session:
            fish_group_taxa = resolve_fish_group_taxa(session, family_taxa)
            print(f"Ermittelte Fisch-Gruppen-Taxa: {fish_group_taxa}")

            candidates = fetch_candidate_observations(
                session=session,
                fish_group_taxa=fish_group_taxa,
                excluded_taxa=excluded_taxa,
                seen_photo_ids=set(existing_photo_ids),
                limit_total=remaining,
            )

            if not candidates:
                print("Keine passenden Kandidaten gefunden.")
                return

            for index, candidate in enumerate(candidates, start=1):
                observation = candidate["observation"]
                photo = candidate["photo"]
                preview_url = str(photo.get("url", ""))
                image_url = preview_url.replace("square", "original")

                extension = sanitize_image_extension(image_url)
                target_path, next_sequence_number = build_unique_output_path(
                    output_dir=output_dir,
                    sequence_number=next_sequence_number,
                    existing_filenames=existing_filenames,
                    extension=extension,
                )

                print(
                    f"Lade Bild {index}/{len(candidates)} herunter: "
                    f"Obs {observation.get('id')} | Photo {photo.get('id')} -> {target_path.name}"
                )

                success = download_image(session, image_url, target_path)
                if not success:
                    continue

                metadata_row = build_metadata_row(
                    target_path.name, observation, photo, image_url
                )
                rows.append(metadata_row)
                save_metadata(metadata_path, rows)

                downloaded_now += 1
                print(
                    f"Gespeichert: {target_path.name} "
                    f"({len(rows)}/{LIMIT_TOTAL} insgesamt)"
                )
                time.sleep(DOWNLOAD_PAUSE_SECONDS)

                if len(rows) >= LIMIT_TOTAL:
                    break
    except RuntimeError as exc:
        print(f"Fehler: {exc}")
        return

    print()
    print("Download abgeschlossen.")
    print(f"Neu heruntergeladen: {downloaded_now}")
    print(f"Gesamtanzahl in metadata.csv: {len(rows)}")
    print(f"Zielordner: {output_dir}")


if __name__ == "__main__":
    main()
