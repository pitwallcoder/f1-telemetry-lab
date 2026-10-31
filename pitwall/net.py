"""The only module that talks to the network, so tests can replace `fetch_json` with recorded responses."""
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "pitwallcoder/f1-telemetry-lab"
CACHE_DIR = Path(".cache")
RETRIES = 4


def fetch_json(url, cache=False):
    """Parsed JSON body, or None when the server has nothing for that URL (404).

    `cache` is for data that never changes once published, like a finished session's telemetry.
    """
    cached = CACHE_DIR / f"{hashlib.sha256(url.encode()).hexdigest()}.json"
    if cache and cached.exists():
        return json.loads(cached.read_text())
    body = _download(url)
    # Empty answers are not cached: OpenF1 can still be processing a session that just ended.
    if cache and body:
        CACHE_DIR.mkdir(exist_ok=True)
        cached.write_text(json.dumps(body))
    return body


def _download(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code != 429 or attempt == RETRIES - 1:
                raise
            time.sleep(float(error.headers.get("Retry-After") or 2 ** attempt))


def build_url(base, **params):
    # Keys stay raw: OpenF1 filters like `date>` stop working once the `>` is percent-encoded.
    query = "&".join(f"{key}={urllib.parse.quote(str(value), safe='')}" for key, value in params.items())
    return f"{base}?{query}" if query else base
