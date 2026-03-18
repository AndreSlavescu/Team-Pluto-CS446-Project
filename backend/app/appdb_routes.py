"""FastAPI router for per-app sandboxed database endpoints."""

from __future__ import annotations

import re
from typing import Dict

from fastapi import APIRouter, Depends, Query, Request

from . import appdb
from .appdb import AppDBError, NotFoundError, ResourceLimitError, ValidationError
from .appdb_models import (
    CollectionInfo,
    CollectionListResponse,
    CreateItemRequest,
    DeletedResponse,
    ItemData,
    ItemListResponse,
    ItemResponse,
    UpdateItemRequest,
)
from .auth import get_current_user
from .store import store

router = APIRouter(prefix="/v1/apps/{app_id}/db", tags=["appdb"])

_ID_PATTERN = re.compile(r"^[a-z]+_[0-9a-f]{16}$")


def _validate_app_id(app_id: str) -> None:
    if not _ID_PATTERN.match(app_id) or not app_id.startswith("app_"):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ID",
                "message": "Invalid app identifier",
            },
        )


def _check_ownership(app_id: str, user: dict) -> None:
    from fastapi import HTTPException

    app_record = store.get_app(app_id)
    if not app_record:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "APP_NOT_FOUND",
                "message": "App not found",
            },
        )
    if not app_record.get("ownerId"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "NO_OWNER",
                "message": "This app has no owner and cannot use the database feature",
            },
        )
    if app_record["ownerId"] != user["userId"]:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "You do not have access to this app's database",
            },
        )


def _handle_appdb_error(exc: AppDBError) -> None:
    from fastapi import HTTPException

    if isinstance(exc, NotFoundError):
        raise HTTPException(
            status_code=404,
            detail={
                "code": exc.code,
                "message": exc.message,
            },
        )
    elif isinstance(exc, ResourceLimitError):
        raise HTTPException(
            status_code=429,
            detail={
                "code": exc.code,
                "message": exc.message,
            },
        )
    elif isinstance(exc, ValidationError):
        raise HTTPException(
            status_code=400,
            detail={
                "code": exc.code,
                "message": exc.message,
            },
        )
    else:
        raise HTTPException(
            status_code=500,
            detail={
                "code": exc.code,
                "message": exc.message,
            },
        )


@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    app_id: str,
    user: dict = Depends(get_current_user),
) -> CollectionListResponse:
    _validate_app_id(app_id)
    _check_ownership(app_id, user)

    collections = appdb.list_collections(app_id)
    return CollectionListResponse(
        collections=[
            CollectionInfo(name=c["name"], item_count=c["itemCount"])
            for c in collections
        ]
    )


@router.get("/{collection}", response_model=ItemListResponse)
async def list_items(
    app_id: str,
    collection: str,
    request: Request,
    user: dict = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="created_at"),
) -> ItemListResponse:
    _validate_app_id(app_id)
    _check_ownership(app_id, user)

    # Extract filter.* query params
    filters: Dict[str, str] = {}
    for key, value in request.query_params.items():
        if key.startswith("filter."):
            field = key[len("filter.") :]
            filters[field] = value

    try:
        result = appdb.list_items(
            app_id,
            collection,
            limit=limit,
            offset=offset,
            sort=sort,
            filters=filters if filters else None,
        )
    except AppDBError as exc:
        _handle_appdb_error(exc)

    return ItemListResponse(
        items=[
            ItemData(
                id=item["id"],
                data=item["data"],
                created_at=item["createdAt"],
                updated_at=item["updatedAt"],
            )
            for item in result["items"]
        ],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


@router.post("/{collection}", response_model=ItemResponse, status_code=201)
async def create_item(
    app_id: str,
    collection: str,
    body: CreateItemRequest,
    user: dict = Depends(get_current_user),
) -> ItemResponse:
    _validate_app_id(app_id)
    _check_ownership(app_id, user)

    try:
        item = appdb.create_item(app_id, collection, body.data)
    except AppDBError as exc:
        _handle_appdb_error(exc)

    return ItemResponse(
        id=item["id"],
        data=item["data"],
        created_at=item["createdAt"],
        updated_at=item["updatedAt"],
    )


@router.get("/{collection}/{item_id}", response_model=ItemResponse)
async def get_item(
    app_id: str,
    collection: str,
    item_id: str,
    user: dict = Depends(get_current_user),
) -> ItemResponse:
    _validate_app_id(app_id)
    _check_ownership(app_id, user)

    try:
        item = appdb.get_item(app_id, collection, item_id)
    except AppDBError as exc:
        _handle_appdb_error(exc)

    return ItemResponse(
        id=item["id"],
        data=item["data"],
        created_at=item["createdAt"],
        updated_at=item["updatedAt"],
    )


@router.put("/{collection}/{item_id}", response_model=ItemResponse)
async def update_item(
    app_id: str,
    collection: str,
    item_id: str,
    body: UpdateItemRequest,
    user: dict = Depends(get_current_user),
) -> ItemResponse:
    _validate_app_id(app_id)
    _check_ownership(app_id, user)

    try:
        item = appdb.update_item(app_id, collection, item_id, body.data)
    except AppDBError as exc:
        _handle_appdb_error(exc)

    return ItemResponse(
        id=item["id"],
        data=item["data"],
        created_at=item["createdAt"],
        updated_at=item["updatedAt"],
    )


@router.delete("/{collection}/{item_id}", response_model=DeletedResponse)
async def delete_item(
    app_id: str,
    collection: str,
    item_id: str,
    user: dict = Depends(get_current_user),
) -> DeletedResponse:
    _validate_app_id(app_id)
    _check_ownership(app_id, user)

    try:
        appdb.delete_item(app_id, collection, item_id)
    except AppDBError as exc:
        _handle_appdb_error(exc)

    return DeletedResponse()


@router.delete("/{collection}", response_model=DeletedResponse)
async def drop_collection(
    app_id: str,
    collection: str,
    user: dict = Depends(get_current_user),
) -> DeletedResponse:
    _validate_app_id(app_id)
    _check_ownership(app_id, user)

    try:
        appdb.drop_collection(app_id, collection)
    except AppDBError as exc:
        _handle_appdb_error(exc)

    return DeletedResponse()
