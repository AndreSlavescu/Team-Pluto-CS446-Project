from __future__ import annotations

from typing import Any, Dict, List

from pydantic import Field

from .models import CamelModel


class CollectionInfo(CamelModel):
    name: str
    item_count: int


class CollectionListResponse(CamelModel):
    collections: List[CollectionInfo]


class ItemData(CamelModel):
    id: str
    data: Dict[str, Any]
    created_at: str
    updated_at: str


class ItemListResponse(CamelModel):
    items: List[ItemData]
    total: int
    limit: int
    offset: int


class ItemResponse(CamelModel):
    id: str
    data: Dict[str, Any]
    created_at: str
    updated_at: str


class CreateItemRequest(CamelModel):
    data: Dict[str, Any] = Field(..., description="The JSON data payload for this item")


class UpdateItemRequest(CamelModel):
    data: Dict[str, Any] = Field(..., description="The updated JSON data payload")


class DeletedResponse(CamelModel):
    status: str = "deleted"
