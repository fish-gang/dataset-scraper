import certifi
import logging
import time

import requests
from pyrate_limiter import Duration, Limiter, Rate

from config import MAX_RETRIES, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# iNaturalist only allows 60 requests per minute
_limiter = Limiter(Rate(60, Duration.MINUTE))


@_limiter.as_decorator(name="inat", weight=1)
def get(url: str, **kwargs) -> requests.Response:
    logger.debug(f"GET {url}")
    r = requests.get(url, timeout=REQUEST_TIMEOUT, verify=certifi.where(), **kwargs)
    r.raise_for_status()
    logger.debug(f"Request URL: {r.url} - Status: {r.status_code}")
    return r


def get_with_retry(url: str, **kwargs) -> requests.Response:
    """GET with exponential backoff retries. Use for image downloads."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return get(url, **kwargs)
        except requests.RequestException as exc:
            last_error = exc
            wait = min(2 ** (attempt - 1), 8)
            logger.warning(f"Request failed (attempt {attempt}/{MAX_RETRIES}): {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(wait)
    raise RuntimeError(
        f"Request failed after {MAX_RETRIES} attempts: {url}"
    ) from last_error
