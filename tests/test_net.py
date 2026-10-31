import io
import json
import urllib.error

import pytest

from pitwall import net


class FakeServer:
    """Stands in for urlopen: answers with the queued status codes, then 200 with `body`."""

    def __init__(self, statuses, body, headers=None):
        self.statuses, self.body, self.headers, self.calls = list(statuses), body, headers or {}, 0

    def __call__(self, request, timeout):
        self.calls += 1
        if self.statuses:
            raise urllib.error.HTTPError(request.full_url, self.statuses.pop(0), "", self.headers, None)
        return io.BytesIO(json.dumps(self.body).encode())


@pytest.fixture
def sleeps(monkeypatch):
    waited = []
    monkeypatch.setattr(net.time, "sleep", waited.append)
    return waited


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(net, "CACHE_DIR", tmp_path / "cache")
    return tmp_path / "cache"


def serve(monkeypatch, server):
    monkeypatch.setattr(net.urllib.request, "urlopen", server)
    return server


def test_retries_after_rate_limiting_and_honours_retry_after(monkeypatch, sleeps):
    server = serve(monkeypatch, FakeServer([429, 429], [{"ok": 1}], {"Retry-After": "3"}))
    assert net.fetch_json("https://x/laps") == [{"ok": 1}]
    assert server.calls == 3
    assert sleeps == [3.0, 3.0]


def test_backs_off_exponentially_without_retry_after(monkeypatch, sleeps):
    serve(monkeypatch, FakeServer([429, 429, 429], [1]))
    net.fetch_json("https://x/laps")
    assert sleeps == [1, 2, 4]


def test_gives_up_after_the_last_retry(monkeypatch, sleeps):
    serve(monkeypatch, FakeServer([429] * net.RETRIES, [1]))
    with pytest.raises(urllib.error.HTTPError):
        net.fetch_json("https://x/laps")


def test_not_found_means_no_data(monkeypatch, sleeps):
    serve(monkeypatch, FakeServer([404], [1]))
    assert net.fetch_json("https://x/laps") is None


def test_other_errors_are_not_swallowed(monkeypatch, sleeps):
    serve(monkeypatch, FakeServer([500], [1]))
    with pytest.raises(urllib.error.HTTPError):
        net.fetch_json("https://x/laps")


def test_cached_responses_skip_the_network(monkeypatch):
    server = serve(monkeypatch, FakeServer([], [{"speed": 300}]))
    assert net.fetch_json("https://x/car_data", cache=True) == [{"speed": 300}]
    assert net.fetch_json("https://x/car_data", cache=True) == [{"speed": 300}]
    assert server.calls == 1


def test_empty_responses_are_not_cached(monkeypatch, cache_dir):
    serve(monkeypatch, FakeServer([], []))
    net.fetch_json("https://x/laps", cache=True)
    assert not cache_dir.exists()


def test_build_url_keeps_openf1_comparison_keys_raw():
    url = net.build_url("https://api/car_data", **{"date>": "2026-10-30T19:00:37+00:00"})
    assert url == "https://api/car_data?date>=2026-10-30T19%3A00%3A37%2B00%3A00"
