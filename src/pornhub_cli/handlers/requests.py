import re
import threading

from curl_cffi import CurlHttpVersion
from curl_cffi import requests as _requests


def get_user_agent() -> str:
    """Return the configured User-Agent override, or None if not set."""
    from pornhub_cli.config import config_manager

    config = config_manager.load_config()
    return config.get("user_agent", "")


def get_browser(ua: str) -> _requests.BrowserTypeLiteral:
    """Detect browser family from a User-Agent string for curl_cffi TLS impersonation.

    Matching order is deliberate:
    1. Edge first — its UA also contains ``Chrome/``.
    2. Chrome Android — distinguish phone (``Mobile``) vs tablet.
    3. Chrome desktop — ``Chrome/`` without ``Mobile``.
    4. Firefox — ``Firefox/`` + ``Gecko/``.
    5. iOS Safari — ``iPhone/iPad/iPod`` + ``Safari/``.
    6. Desktop Safari — ``Safari/`` + ``Version/``, no ``Mobile``, no ``Chrome/``.

    Tor Browser is intentionally **not** detected — it forges a generic Firefox
    UA on all platforms and actively hides its fingerprint.
    """
    if not ua:
        return "chrome"

    # Edge — contains the Edg/ marker (newer Chromium-based Edge).
    if re.search(r"Edg/", ua):
        return "edge"

    # Chrome on Android — Linux + Android + Chrome/.
    if "Android" in ua and re.search(r"Chrome/", ua):
        return "chrome_android"

    # Chrome desktop — Chrome/ without Edg/, Android, or Mobile.
    if re.search(r"Chrome/", ua) and "Mobile" not in ua:
        return "chrome"

    # Firefox — Firefox/ + Gecko/.
    if re.search(r"Firefox/", ua) and re.search(r"Gecko/", ua):
        return "firefox"

    # iOS Safari — iPhone/iPad/iPod device token + Safari/.
    if re.search(r"(?:iPhone|iPad|iPod)", ua) and re.search(r"Safari/", ua):
        return "safari_ios"

    # Desktop Safari — Safari/ + Version/, no Mobile, no Chrome/.
    if re.search(r"Safari/", ua) and re.search(r"Version/", ua) and "Mobile" not in ua:
        return "safari"

    return "chrome"


def _build_session() -> _requests.Session:
    """Create a Session with the configured or profile User-Agent."""
    ua = get_user_agent()
    sess = _requests.Session(
        impersonate=get_browser(ua),
        # HTTP/2 — the CDN (phncdn.com) serves segments over HTTP/2
        # (matching system curlʼs default).  HTTP/3 / QUIC (V3) can be
        # materially slower on networks that throttle or poorly route UDP.
        http_version=CurlHttpVersion.V2_0,
    )
    if ua:
        sess.headers["User-Agent"] = ua
    # The CDN uses these to authorise / prioritise segment downloads.
    # Omitting them can trigger rate-limiting or low-priority delivery.
    sess.headers["Referer"] = "https://www.pornhub.com/"
    sess.headers["Origin"] = "https://www.pornhub.com"
    return sess


# ── thread-local sessions ────────────────────────────────────────────────
# The global session is kept for single-threaded callers (fetch_page_html,
# search, etc.).  Parallel downloads in ThreadPoolExecutor use per-thread
# sessions so each thread maintains its own libcurl connection pool —
# eliminating the per-segment TLS-handshake tax (~200 ms × N segments).

_local = threading.local()


def _get_thread_session() -> _requests.Session:
    """Return (or create) a curl_cffi session bound to the calling thread."""
    sess = getattr(_local, "session", None)
    if sess is None:
        sess = _build_session()
        _local.session = sess
    return sess


# Shared global session for single-threaded use.
headers: dict[str, str] = {}
session = requests = _build_session()


def reload_session() -> None:
    """Reload the global session with headers from the active profile."""
    global headers, session, requests
    sess = _build_session()
    headers = dict(sess.headers)
    session = requests = sess


def fetch_page_html(url: str) -> str:
    url = url.replace("http://", "https://")
    return session.get(url).text


class M3U8HttpClient:
    """An ``m3u8`` HTTP-client adapter backed by our curl_cffi session.

    The `m3u8` library defaults to ``urllib``, which sends no TLS
    fingerprint, no HTTP/2, and no Referer / Origin headers.  On CDNs that
    inspect those signals (phncdn.com) this can mean throttled or
    deprioritised delivery — even for tiny playlist files.

    Pass an instance of this class as the *http_client* argument to
    :func:`m3u8.load` so every playlist fetch goes through the same
    impersonated, header-rich channel as the segment downloads.
    """

    def __init__(self, sess: _requests.Session | None = None) -> None:
        self._sess = sess or session

    def download(
        self, uri: str, timeout: float | None = None, headers: dict | None = None, verify_ssl: bool = True
    ) -> tuple[str, str]:
        from urllib.parse import urljoin

        kw = {}
        if timeout is not None:
            kw["timeout"] = timeout
        resp = self._sess.get(uri, **kw)
        resp.raise_for_status()
        content = resp.text
        base_uri = urljoin(resp.url or uri, ".")
        return content, base_uri


def download(url: str, desc: str | None = None, position: int | None = None) -> bytes:
    """Download binary content with a per-segment progress bar and speed display.

    Uses the **non-streaming** path on a thread-local session so each worker:

    * reuses its TCP+TLS connection across segments (eliminating the
      ~200 ms per-segment TLS-handshake tax), and
    * avoids the queue / background-thread overhead of curl_cffi streaming
      (chunks travel through libcurlʼs native BytesIO buffer in C).

    Because individual .ts segments are small (~2.5 MiB, ~1–2 s) there is
    no per-chunk progress — tqdm jumps from 0→100 % on completion.
    """
    from tqdm import tqdm

    url = url.replace("http://", "https://")
    sess = _get_thread_session()
    total = 0

    with tqdm(
        # total is filled in after the HEAD / response headers arrive.
        total=None,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=desc,
        position=position,
        leave=False,
        bar_format="{desc}: {percentage:3.0f}%|{bar:16}| {rate_fmt}",
        mininterval=0.1,
    ) as bar:
        response = sess.get(url)  # non-streaming — fast path, connection reuse
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        data = response.content
        if total > 0:
            bar.total = total
        bar.update(len(data))
    return data
