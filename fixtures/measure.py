"""Measure the classification engine against the labeled corpus.

    uv run python fixtures/measure.py

Prints per-class precision/recall/support for the shipped classes, the overall
UNCLASSIFIED rate, and the control number the brief specifically asked for:
how many of the fixtures OUTSIDE the shipped classes correctly came back
UNCLASSIFIED (a rule firing on a class it was never meant to detect is a
false positive in the most dangerous direction). Writes the same numbers to
docs/ACCURACY.md. Never tune a rule against these numbers -- add a fixture
from an unmeasured source first (see CONTRIBUTING.md).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from why_red.classify.rules import SHIPPED_CLASSES
from why_red.models.failure import FailureClass
from why_red.pipeline import classify_in, load_dir, locate_in

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
ACCURACY_DOC = ROOT.parent / "docs" / "ACCURACY.md"


@dataclass(frozen=True)
class Row:
    slug: str
    expected: FailureClass
    predicted: FailureClass
    confidence: float


def measure() -> list[Row]:
    rows = []
    for case_dir in sorted(p for p in CASES.iterdir() if p.is_dir()):
        label = json.loads((case_dir / "label.json").read_text(encoding="utf-8"))
        loaded = load_dir(case_dir)
        location = locate_in(loaded)
        result = classify_in(loaded, location)
        rows.append(
            Row(
                slug=case_dir.name,
                expected=FailureClass(label["failure_class"]),
                predicted=result.failure_class,
                confidence=result.confidence,
            )
        )
    return rows


def _precision_recall(rows: list[Row], cls: FailureClass) -> tuple[float, float, int]:
    support = sum(1 for r in rows if r.expected is cls)
    predicted_as = sum(1 for r in rows if r.predicted is cls)
    correct = sum(1 for r in rows if r.expected is cls and r.predicted is cls)
    precision = correct / predicted_as if predicted_as else float("nan")
    recall = correct / support if support else float("nan")
    return precision, recall, support


def render(rows: list[Row]) -> str:
    lines = [
        "# Accuracy",
        "",
        "Measured against the 12-fixture corpus in `fixtures/cases/`, hand-labeled",
        "per `docs/LABELING.md`. Regenerate with `uv run python fixtures/measure.py`",
        "(also runnable as `make measure`) after any change to the corpus or the",
        "rules -- these numbers are written by the script, never by hand.",
        "",
        "**Limitation, stated plainly:** labels were assigned by a single labeler",
        "(the project's maintainer, working through this repo's own automation)",
        "against criteria committed before labeling started, with no independent",
        "second labeler. These are precision/recall against that one labeler's",
        "judgment, not against an externally verified ground truth. The",
        "procedural guard that exists: `docs/LABELING.md` was committed before",
        "any fixture was labeled, and its tie-break rules were extended -- once,",
        "for `deno-runner-shutdown-during-tests` -- before the fixture that",
        "needed the new rule was labeled, not after, specifically to prevent",
        "labeling decisions from being rationalized after the fact. If you think",
        "a specific fixture is mislabeled, open a misclassification issue (the",
        "template in `.github/ISSUE_TEMPLATE/`) naming the fixture and the class",
        "you'd expect -- that disagreement is the only independent check a solo",
        "project has, and it is genuinely wanted.",
        "",
        "## Shipped classes",
        "",
        "A class ships (gets a rule) only once it has >=2 real fixtures; see",
        "`docs/LABELING.md`'s per-class count table for the other 12.",
        "",
        "| Class | Precision | Recall | Support |",
        "|---|---|---|---|",
    ]
    for cls in sorted(SHIPPED_CLASSES, key=lambda c: c.value):
        precision, recall, support = _precision_recall(rows, cls)
        lines.append(f"| {cls.value} | {precision:.2f} | {recall:.2f} | {support} |")

    unclassified = sum(1 for r in rows if r.predicted is FailureClass.UNCLASSIFIED)
    lines += [
        "",
        f"UNCLASSIFIED rate: {unclassified}/{len(rows)} of all fixtures predicted UNCLASSIFIED.",
        "",
        "## Control: fixtures outside the shipped classes",
        "",
        "Every fixture whose labeled class has no rule MUST come back UNCLASSIFIED.",
        "A rule firing on a class it was never built for is a confidently wrong",
        "answer, which the brief calls worse than not knowing -- this is the",
        "check for that failure mode specifically, reported on its own rather",
        "than folded into the precision numbers above.",
        "",
    ]
    unshipped = [r for r in rows if r.expected not in SHIPPED_CLASSES]
    correct_unclassified = [r for r in unshipped if r.predicted is FailureClass.UNCLASSIFIED]
    leaked = [r for r in unshipped if r.predicted is not FailureClass.UNCLASSIFIED]
    lines.append(f"**{len(correct_unclassified)}/{len(unshipped)} correctly UNCLASSIFIED.**")
    if leaked:
        lines.append("")
        lines.append("False positives (a shipped rule fired on an unshipped class):")
        lines.append("")
        for r in leaked:
            lines.append(
                f"- `{r.slug}`: labeled {r.expected.value}, rule predicted {r.predicted.value}"
            )
    lines.append("")
    lines.append(f"_Generated {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}._")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    rows = measure()
    doc = render(rows)
    ACCURACY_DOC.write_text(doc, encoding="utf-8")
    print(doc)
    unshipped = [r for r in rows if r.expected not in SHIPPED_CLASSES]
    leaked = [r for r in unshipped if r.predicted is not FailureClass.UNCLASSIFIED]
    return 1 if leaked else 0


if __name__ == "__main__":
    sys.exit(main())
