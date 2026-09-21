"""Hoeflicher HTTP-Client: robots.txt, Rate-Limit, ehrlicher User-Agent.

Bewusst defensiv. Ein Scraper, der Portale haemmert, fliegt raus - und
nimmt die Geschaeftsidee mit. Siehe docs/RECHTLICHES.md.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from .base import SourceError


class RobotsDisallowed(SourceError):
    """Die Seite untersagt automatisierten Abruf dieses Pfads."""


class PoliteFetcher:
    def __init__(
        self,
        user_agent: str,
        delay_seconds: float = 3.0,
        timeout: float = 20.0,
        respect_robots: bool = True,
    ):
        self.user_agent = user_agent
        self.delay = delay_seconds
        self.timeout = timeout
        self.respect_robots = respect_robots
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}

    # --- robots.txt ----------------------------------------------------

    def _robots_for(self, url: str) -> RobotFileParser | None:
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host in self._robots:
            return self._robots[host]
        parser = RobotFileParser()
        parser.set_url(f"{host}/robots.txt")
        try:
            parser.read()
        except Exception:
            # robots.txt nicht lesbar -> im Zweifel nicht crawlen.
            parser = None
        self._robots[host] = parser
        return parser

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parser = self._robots_for(url)
        if parser is None:
            return False
        return parser.can_fetch(self.user_agent, url)

    # --- Abruf ---------------------------------------------------------

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_request.get(host)
        if last is not None:
            wait = self.delay - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request[host] = time.monotonic()

    def get(self, url: str) -> str:
        if not self.allowed(url):
            raise RobotsDisallowed(
                f"robots.txt der Seite verbietet den Abruf von {url}. "
                "Nutze die offizielle API/Partnerschnittstelle oder den "
                "CSV-Import (siehe docs/RECHTLICHES.md)."
            )
        self._throttle(url)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "de-DE,de;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise SourceError(
                    f"{url} hat {exc.code} geantwortet - der Abruf wird blockiert "
                    "oder gedrosselt. Nicht umgehen, sondern offiziellen Zugang klaeren."
                ) from exc
            raise SourceError(f"HTTP {exc.code} bei {url}") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Netzwerkfehler bei {url}: {exc.reason}") from exc
