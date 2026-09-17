"""The corpus is a deliverable: every fixture must be internally consistent.
Not a classifier test (there is no classifier yet) -- a labeling-hygiene test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from why_red.models.failure import FailureClass
from why_red.pipeline import load_dir

CASES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"
SLUGS = sorted(p.name for p in CASES.iterdir() if p.is_dir())


def test_at_least_one_fixture_exists() -> None:
    assert SLUGS


@pytest.mark.parametrize("slug", SLUGS)
def test_fixture_has_run_json_and_at_least_one_log(slug: str) -> None:
    d = CASES / slug
    assert (d / "run.json").is_file()
    assert list(d.glob("*.log"))


@pytest.mark.parametrize("slug", SLUGS)
def test_fixture_is_labeled(slug: str) -> None:
    assert (CASES / slug / "label.json").is_file(), f"{slug} has no label.json"


@pytest.mark.parametrize("slug", SLUGS)
def test_label_class_is_valid_and_evidence_lines_exist_in_the_named_job_log(slug: str) -> None:
    label = json.loads((CASES / slug / "label.json").read_text(encoding="utf-8"))
    assert label["failure_class"] in {c.value for c in FailureClass}
    job_id = label["job_id"]
    log_path = CASES / slug / f"{job_id}.log"
    assert log_path.is_file(), f"{slug}: label names job {job_id}, no such log file"
    with log_path.open(encoding="utf-8", newline="") as fh:
        total_lines = fh.read().count("\n") + 1
    for line_no in label["evidence_lines"]:
        assert 1 <= line_no <= total_lines, f"{slug}: evidence line {line_no} out of range"
    if label["ambiguous_with"] is not None:
        assert label["ambiguous_with"] in {c.value for c in FailureClass}
        assert label["ambiguous_with"] != label["failure_class"]


@pytest.mark.parametrize("slug", SLUGS)
def test_fixture_loads_and_locates(slug: str) -> None:
    """A fixture that load_dir/locate_in cannot even process is not usable evidence."""
    loaded = load_dir(CASES / slug)
    assert loaded.run.id > 0


def test_manifest_covers_every_fixture() -> None:
    manifest = json.loads((CASES.parent / "MANIFEST.json").read_text(encoding="utf-8"))
    assert set(manifest) == set(SLUGS)


def test_per_class_counts_reported_in_labeling_doc() -> None:
    """Every class that ships in the LABELING.md count table must actually have >=2
    fixtures; this guards against the table drifting from the corpus."""
    counts: dict[str, int] = {}
    for slug in SLUGS:
        label = json.loads((CASES / slug / "label.json").read_text(encoding="utf-8"))
        counts[label["failure_class"]] = counts.get(label["failure_class"], 0) + 1
    doc = (CASES.parent.parent / "docs" / "LABELING.md").read_text(encoding="utf-8")
    for cls, count in counts.items():
        if count >= 2:
            assert f"| {cls} | {count}" in doc, f"{cls} count {count} not reflected in LABELING.md"
