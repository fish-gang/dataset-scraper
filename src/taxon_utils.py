import logging

from config import INAT_FISH_GROUPS, INAT_TAXA_URL
from src.http import get_with_retry

logger = logging.getLogger(__name__)


def fetch_taxon(taxon_id: int) -> dict:
    payload = get_with_retry(INAT_TAXA_URL, params={"id": taxon_id}).json()
    results = payload.get("results", [])
    if not results:
        raise RuntimeError(f"No taxon found for ID {taxon_id}")
    return results[0]


def resolve_taxon_id_by_name(scientific_name: str) -> int | None:
    payload = get_with_retry(
        f"{INAT_TAXA_URL}/autocomplete",
        params={"q": scientific_name, "per_page": 30},
    ).json()
    for result in payload.get("results", []):
        if str(result.get("name", "")).lower() == scientific_name.lower():
            try:
                return int(result["id"])
            except (KeyError, TypeError, ValueError):
                continue
    return None


def resolve_fish_group_taxa(family_taxon_ids: list[int]) -> list[int]:
    """
    Resolve the top-level iNaturalist taxon IDs for Actinopterygii and
    Chondrichthyes by walking the ancestor lineage of the known family taxa.
    Falls back to name-based lookup if not found in lineage.
    """
    resolved: dict[str, int] = {}

    for family_taxon_id in family_taxon_ids:
        try:
            family_taxon = fetch_taxon(family_taxon_id)
        except RuntimeError as exc:
            logger.warning(f"Could not load family taxon {family_taxon_id}: {exc}")
            continue

        lineage = family_taxon.get("ancestors", [])
        lineage.append(family_taxon)
        for ancestor in lineage:
            name = str(ancestor.get("name", ""))
            if name in INAT_FISH_GROUPS:
                try:
                    resolved[name] = int(ancestor["id"])
                except (KeyError, TypeError, ValueError):
                    continue

    for name in INAT_FISH_GROUPS:
        if name not in resolved:
            logger.info(f"Falling back to name lookup for: {name}")
            fallback_id = resolve_taxon_id_by_name(name)
            if fallback_id is not None:
                resolved[name] = fallback_id

    missing = [name for name in INAT_FISH_GROUPS if name not in resolved]
    if missing:
        raise RuntimeError(f"Could not resolve fish groups: {', '.join(missing)}")

    return [resolved[name] for name in INAT_FISH_GROUPS]


def observation_matches_excluded_taxa(obs: dict, excluded_taxa: set[int]) -> bool:
    taxon = obs.get("taxon") or {}
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