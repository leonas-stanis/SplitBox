from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RunSplitIn(BaseModel):
    split_id: int | None = None
    name: str = Field(min_length=1, max_length=80)
    position: int = Field(ge=0)
    segment_ms: int = Field(ge=0)
    cumulative_ms: int = Field(ge=0)


class RunCreate(BaseModel):
    category_id: int
    started_at: datetime
    finished_at: datetime
    total_ms: int = Field(ge=0)
    splits: list[RunSplitIn] = Field(min_length=1)


class RunSaved(BaseModel):
    run_id: int
    total_ms: int
    is_pb: bool
    previous_pb_ms: int | None = None
