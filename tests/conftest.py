"""Shared fixtures. `fake_gh` puts a scripted `gh` executable first on PATH and
records every invocation, so tests prove what the tool asks GitHub for."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

FAKE_GH = """
import json, sys, pathlib
root = pathlib.Path(sys.argv[0]).resolve().parent
calls = root / "calls.jsonl"
with calls.open("a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
path = sys.argv[2]
responses = json.loads((root / "responses.json").read_text())
key = next((k for k in responses if path.startswith(k)), None)
if key is None:
    sys.stderr.write("gh: Not Found (HTTP 404)\\n")
    sys.exit(1)
resp = responses[key]
if resp.get("status", 200) != 200:
    sys.stderr.write(f"gh: {resp.get('message', 'error')} (HTTP {resp['status']})\\n")
    sys.exit(1)
body = resp["body"]
if "--slurp" in sys.argv:
    body = [body]
if isinstance(body, str):
    sys.stdout.buffer.write(body.encode("utf-8"))
else:
    sys.stdout.write(json.dumps(body))
"""


class FakeGh:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.responses: dict[str, object] = {}

    def respond(self, prefix: str, body: object, status: int = 200) -> None:
        self.responses[prefix] = {"body": body, "status": status}
        (self.root / "responses.json").write_text(json.dumps(self.responses))

    @property
    def calls(self) -> list[list[str]]:
        path = self.root / "calls.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line]


@pytest.fixture
def fake_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeGh:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "gh.py"
    script.write_text(FAKE_GH)
    python = sys.executable
    if sys.platform == "win32":
        (bin_dir / "gh.cmd").write_text(f'@"{python}" "{script}" %*\n')
    else:
        sh = bin_dir / "gh"
        sh.write_text(f'#!/bin/sh\nexec "{python}" "{script}" "$@"\n')
        sh.chmod(sh.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    fake = FakeGh(bin_dir)
    fake.respond("__none__", {})
    return fake


SAMPLE_DIR = Path(__file__).parent / "data"
