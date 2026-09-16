"""The signal excerpt: the smallest span of real log lines that explains the failure."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class ExcerptLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_no: int = Field(ge=1, description="1-based line number in the raw job log.")
    text: str = Field(description="Verbatim line, ANSI stripped.")
    highlight: bool = Field(default=False, description="True if this line is evidence.")


class Excerpt(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: int
    total_lines: int = Field(ge=0, description="Line count of the raw job log.")
    lines: list[ExcerptLine] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def compression_ratio(self) -> float:
        """total_lines / shown lines. 0.0 when nothing is shown."""
        return self.total_lines / len(self.lines) if self.lines else 0.0

    @model_validator(mode="after")
    def _lines_ascending_and_in_range(self) -> Excerpt:
        prev = 0
        for line in self.lines:
            if line.line_no <= prev:
                msg = f"excerpt lines must be strictly ascending, got {line.line_no} after {prev}"
                raise ValueError(msg)
            if line.line_no > self.total_lines:
                msg = f"line {line.line_no} exceeds total_lines={self.total_lines}"
                raise ValueError(msg)
            prev = line.line_no
        return self
