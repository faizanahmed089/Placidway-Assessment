"""Step 1 of ingestion: download the source pages politely.

Rules from the assessment brief, and where each one is enforced:
  * only the listed URLs            -> we loop over config.SOURCES, nothing else
  * respect robots.txt              -> _load_robots() + can_fetch() before every request
  * identify with a clear User-Agent-> config.USER_AGENT on every request
  * about one request per second    -> time.sleep(CRAWL_DELAY_SECONDS) between requests
"""

import logging
import time
from urllib.robotparser import RobotFileParser

import requests

from app import config

log = logging.getLogger(__name__)


class CrawlError(Exception):
    """Raised when a page cannot be fetched (blocked, or failed after retries)."""


def _get_with_retries(session: requests.Session, url: str) -> requests.Response:
    """GET a URL, retrying a few times on network errors or 5xx responses.

    The wait grows after each failure (2s, 4s, ...) so we never hammer a server
    that is already struggling.
    """
    last_error: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS)
            # 4xx means "this will not work next time either" -> fail immediately.
            if 400 <= response.status_code < 500:
                raise CrawlError(f"{url} returned HTTP {response.status_code}")
            response.raise_for_status()  # turns 5xx into an exception -> retry
            return response
        except CrawlError:
            raise
        except requests.RequestException as error:
            last_error = error
            wait = 2 * attempt
            log.warning("Fetch failed (%s/%s) for %s: %s - retrying in %ss",
                        attempt, config.MAX_RETRIES, url, error, wait)
            time.sleep(wait)
    raise CrawlError(f"{url} failed after {config.MAX_RETRIES} attempts: {last_error}")


def _load_robots(session: requests.Session) -> RobotFileParser:
    """Download and parse robots.txt using our own User-Agent."""
    response = _get_with_retries(session, config.ROBOTS_URL)
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser


def fetch_sources() -> list[dict]:
    """Fetch every page in config.SOURCES.

    Returns one dict per page: the source entry plus its raw `html`.
    Raises CrawlError if ANY page fails, so the caller never builds a
    half-complete knowledge base.
    """
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT

    robots = _load_robots(session)
    pages = []

    for source in config.SOURCES:
        url = source["url"]

        # robots.txt check: skip (and fail loudly) if we are not allowed.
        if not robots.can_fetch(config.USER_AGENT, url):
            raise CrawlError(f"robots.txt disallows fetching {url}")

        time.sleep(config.CRAWL_DELAY_SECONDS)  # rate limit: ~1 request/second
        response = _get_with_retries(session, url)
        log.info("Fetched %s (%s bytes)", url, len(response.content))

        pages.append({**source, "html": response.text})

    return pages
