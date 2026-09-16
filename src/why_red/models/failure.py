"""Classification output. A class is never emitted without the log lines that
triggered it; UNCLASSIFIED is the one honest exception."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FailureClass(StrEnum):
    DEPENDENCY_RESOLUTION = "DEPENDENCY_RESOLUTION"
    COMPILATION_ERROR = "COMPILATION_ERROR"
    TEST_FAILURE = "TEST_FAILURE"
    FLAKY_TEST = "FLAKY_TEST"
    OOM_KILLED = "OOM_KILLED"
    TIMEOUT = "TIMEOUT"
    DISK_FULL = "DISK_FULL"
    AUTH_FAILURE = "AUTH_FAILURE"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    CACHE_MISS = "CACHE_MISS"
    LINT_FAILURE = "LINT_FAILURE"
    MISSING_SECRET = "MISSING_SECRET"
    CONFIG_ERROR = "CONFIG_ERROR"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    UNCLASSIFIED = "UNCLASSIFIED"


class Evidence(BaseModel):
    """One real log line that supports a classification."""

    model_config = ConfigDict(frozen=True)

    line_no: int = Field(ge=1, description="1-based line number in the raw job log.")
    text: str = Field(description="Verbatim log line, ANSI stripped, never paraphrased.")


class Classification(BaseModel):
    model_config = ConfigDict(frozen=True)

    failure_class: FailureClass
    confidence: float = Field(ge=0.0, le=1.0)
    rule_id: str | None = Field(
        default=None, description="Identifier of the rule that fired; None for UNCLASSIFIED."
    )
    evidence: list[Evidence] = Field(default_factory=list)
    next_checks: list[str] = Field(
        default_factory=list, description="Rule-supplied things to look at next."
    )

    @model_validator(mode="after")
    def _evidence_required_unless_unclassified(self) -> Classification:
        unclassified = self.failure_class is FailureClass.UNCLASSIFIED
        if not unclassified and not self.evidence:
            msg = f"{self.failure_class} requires at least one evidence line"
            raise ValueError(msg)
        if unclassified and self.confidence != 0.0:
            msg = "UNCLASSIFIED must carry confidence 0.0"
            raise ValueError(msg)
        return self
