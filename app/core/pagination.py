"""The one list envelope and the one set of common query parameters.

`{"items": [...], "total": N, "limit": L, "offset": O}` on every collection
endpoint. There is no second shape — a caller that can page one resource can
page all of them.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel, Field

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(description="Matching documents, ignoring limit and offset")
    limit: int
    offset: int


class ListParams(BaseModel):
    limit: int = DEFAULT_LIMIT
    offset: int = 0


async def list_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListParams:
    return ListParams(limit=limit, offset=offset)


ListParamsDep = Annotated[ListParams, Depends(list_params)]


def page[T](items: list[T], total: int, params: ListParams) -> Page[T]:
    return Page[T](items=items, total=total, limit=params.limit, offset=params.offset)
