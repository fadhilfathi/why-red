"""Top-level result of one `why-red <run-id>` invocation. This is what `--json` emits."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from why_red.models.excerpt import Excerpt
from why_red.models.failure import Classification
from why_red.models.run import Location, Run


class AiSummary(BaseModel):
    """Output of the optional AI layer. Absent unless `--ai` was passed."""

    model_config = ConfigDict(frozen=True)

    model: str
    summary: str
    suggested_fix: str | None = None


class Report(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    run: Run
    location: Location | None = Field(
        default=None, description="None when no failing step could be located."
    )
    classification: Classification
    excerpt: Excerpt
    ai: AiSummary | None = None
