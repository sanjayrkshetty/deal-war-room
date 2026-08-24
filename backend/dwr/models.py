"""API request models (`dwr/models.py`)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    synthetic = "synthetic"
    sam_paste = "sam_paste"
    gem_paste = "gem_paste"
    other_public = "other_public"


class ScrubPreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=400_000)


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    source_type: SourceType
    agency: str | None = Field(default=None, max_length=300)
    external_ref: str | None = Field(default=None, max_length=500)
    text: str = Field(min_length=50, max_length=400_000)


class ReindexRequest(BaseModel):
    confirm: bool = False
