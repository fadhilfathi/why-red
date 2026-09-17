# Accuracy

Measured against the 12-fixture corpus in `fixtures/cases/`, hand-labeled
per `docs/LABELING.md`. Regenerate with `uv run python fixtures/measure.py`
(also runnable as `make measure`) after any change to the corpus or the
rules -- these numbers are written by the script, never by hand.

**Limitation, stated plainly:** labels were assigned by a single labeler
(the project's maintainer, working through this repo's own automation)
against criteria committed before labeling started, with no independent
second labeler. These are precision/recall against that one labeler's
judgment, not against an externally verified ground truth. The
procedural guard that exists: `docs/LABELING.md` was committed before
any fixture was labeled, and its tie-break rules were extended -- once,
for `deno-runner-shutdown-during-tests` -- before the fixture that
needed the new rule was labeled, not after, specifically to prevent
labeling decisions from being rationalized after the fact. If you think
a specific fixture is mislabeled, open a misclassification issue (the
template in `.github/ISSUE_TEMPLATE/`) naming the fixture and the class
you'd expect -- that disagreement is the only independent check a solo
project has, and it is genuinely wanted.

## Shipped classes

A class ships (gets a rule) only once it has >=2 real fixtures; see
`docs/LABELING.md`'s per-class count table for the other 12.

| Class | Precision | Recall | Support |
|---|---|---|---|
| LINT_FAILURE | 1.00 | 1.00 | 2 |
| NETWORK_FAILURE | 1.00 | 1.00 | 2 |
| TEST_FAILURE | 1.00 | 1.00 | 2 |

UNCLASSIFIED rate: 6/12 of all fixtures predicted UNCLASSIFIED.

## Control: fixtures outside the shipped classes

Every fixture whose labeled class has no rule MUST come back UNCLASSIFIED.
A rule firing on a class it was never built for is a confidently wrong
answer, which the brief calls worse than not knowing -- this is the
check for that failure mode specifically, reported on its own rather
than folded into the precision numbers above.

**6/6 correctly UNCLASSIFIED.**

_Generated 2026-09-17T18:46:39Z._
