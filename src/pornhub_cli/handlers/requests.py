import re

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
    """Create a ZhihuSession with the configured or profile User-Agent."""
    ua = get_user_agent()
    sess = _requests.Session(
        impersonate=get_browser(ua),
        http_version=CurlHttpVersion.V3,
    )
    if ua:
        sess.headers["User-Agent"] = ua
    return sess


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
