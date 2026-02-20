from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Action(str, Enum):
    noop = "noop"
    append = "append"
    update = "update"
    create = "create"


class CoordinatorDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolved_date: date
    action: Action
    candidate_entry_ids: list[int] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=2000)
