"""Shared Pydantic schema helpers."""
from __future__ import annotations
from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class ErrorDetail(BaseModel):
    detail: str
