"""Record every API response a chart run needs, for offline end-to-end tests.

  uv run python -m tests.record_fixture mexico_2026_fp1 2026 "Mexico City" FP1
"""
import json
import sys
import tempfile
from pathlib import Path

from pitwall import __main__ as cli
from pitwall import net

FIXTURES = Path(__file__).parent / "fixtures"


def record(name, argv):
    responses = {}
    real_fetch = net.fetch_json

    def recording_fetch(url, cache=False):
        responses[url] = real_fetch(url, cache)
        return responses[url]

    net.fetch_json = recording_fetch
    with tempfile.TemporaryDirectory() as out:
        cli.main([*argv, "--out", out])
    FIXTURES.mkdir(exist_ok=True)
    (FIXTURES / f"{name}.json").write_text(json.dumps(responses))


if __name__ == "__main__":
    record(sys.argv[1], sys.argv[2:])
