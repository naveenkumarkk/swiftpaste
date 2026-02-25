# app/routes/snippet_routes.py

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.manager import fastapi_users
from app.db.database import get_async_session
from app.schemas.snippet import (
    SnippetCreate,
    SnippetUpdate,
    SnippetResponse,
    SnippetOut,
    SnippetOutResponse,
)
from app.services.snippet_service import (
    create_snippet,
    update_snippet,
    delete_snippet,
    snippet_out_url,
    get_snippet_cached,
)

router = APIRouter()

current_user = fastapi_users.current_user(active=True)
optional_user = fastapi_users.current_user(optional=True)


@router.post(
    "/",
    response_model=SnippetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Snippet",
    description="Create a Snippet and share the url among your peers",
)
async def create(
    request: Request,
    payload: SnippetCreate,
    db: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    request_id = getattr(request.state, "request_id", None)
    return await create_snippet(
        db_session=db, payload=payload, user=user, request_id=request_id
    )


@router.put(
    "/{id}",
    response_model=SnippetResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a Snippet",
    description="Update a snippet you own",
)
async def update(
    id: UUID,
    request: Request,
    payload: SnippetUpdate,
    db: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    request_id = getattr(request.state, "request_id", None)
    return await update_snippet(
        id=id, db_session=db, payload=payload, user=user, request_id=request_id
    )


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Snippet",
    description="Soft delete a snippet you own",
)
async def delete(
    id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    request_id = getattr(request.state, "request_id", None)
    await delete_snippet(id=id, db_session=db, user=user, request_id=request_id)
    return


@router.post(
    "/{id}/share",
    response_model=SnippetOutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a share URL",
    description="Get the snippet url and share among your peers (extends expiry each time)",
)
async def share(
    id: UUID,
    payload: SnippetOut,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    user=Depends(current_user),
):
    request_id = getattr(request.state, "request_id", None)
    return await snippet_out_url(
        id=id, db_session=db, payload=payload, user=user, request_id=request_id
    )


@router.get(
    "/view/{short_id}",
    response_model=SnippetResponse,
    status_code=status.HTTP_200_OK,
    summary="View shared snippet",
    description="Endpoint to access the shared snippet",
)
async def view_snippet_out(
    short_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    user=Depends(optional_user),
):
    request_id = getattr(request.state, "request_id", None)
    return await get_snippet_cached(
        short_id=short_id, db_session=db, user=user, request_id=request_id
    )
