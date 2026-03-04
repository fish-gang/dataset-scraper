import requests
import logging
from pyrate_limiter import Rate, Limiter, Duration


logger = logging.getLogger(__name__)

# iNaturalist rate limit is 60 requests per minute
_limiter = Limiter(Rate(60, Duration.MINUTE))


@_limiter.as_decorator(name="inat", weight=1)
def get(url: str, **kwargs) -> requests.Response:
    logger.debug(f"GET {url}")
    r = requests.get(url, **kwargs)
    r.raise_for_status()
    logger.debug(f"Request URL: {r.url} - Status: {r.status_code}")
    return r
