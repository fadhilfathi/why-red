"""Run / job / step metadata as returned by the GitHub Actions REST API, plus the
located failure. Extra API fields are ignored so schema drift upstream does not
break parsing."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Conclusion(StrEnum):
    """GitHub's `conclusion` values. UNKNOWN covers null and any value we do not model."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    NEUTRAL = "neutral"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    STARTUP_FAILURE = "startup_failure"
    UNKNOWN = "unknown"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class Step(_Model):
    number: int = Field(ge=1, description="1-based step index within the job.")
    name: str
    conclusion: Conclusion = Conclusion.UNKNOWN
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Job(_Model):
    id: int
    name: str
    conclusion: Conclusion = Conclusion.UNKNOWN
    started_at: datetime | None = None
    completed_at: datetime | None = None
    runner_name: str | None = None
    html_url: str | None = None
    steps: list[Step] = Field(default_factory=list)


class Run(_Model):
    id: int
    repo: str = Field(description="`owner/name`.")
    workflow_name: str
    run_number: int
    run_attempt: int = 1
    event: str
    head_branch: str | None = None
    head_sha: str
    conclusion: Conclusion = Conclusion.UNKNOWN
    created_at: datetime | None = None
    html_url: str | None = None
    jobs: list[Job] = Field(default_factory=list)


class Location(_Model):
    """The failing job and step chosen by the locate stage, with the reason it was
    chosen. `reason` must name the rule applied, because a wrong location poisons
    every downstream stage."""

    job_id: int
    job_name: str
    step_number: int = Field(ge=1)
    step_name: str
    reason: str = Field(min_length=1)
    other_failed_steps: list[int] = Field(
        default_factory=list,
        description="Step numbers that also failed but were not chosen (e.g. cleanup).",
    )
