"""One CRUD router, built per resource.

`experiences`, `educations`, `tools`, `communities` and `videos` differ only in
their models. Writing five near-identical routers means five places to fix a
pagination bug, so the shape is defined once here.

The endpoint functions are declared with placeholder annotations and then have
`__annotations__` replaced with the concrete models. FastAPI reads annotations
at decoration time, so the generated OpenAPI is the same as if each router had
been written out by hand — `tests/test_openapi.py` asserts exactly that.

**Visibility.** Public callers only ever see `published: true` records. An admin
sees everything, and can filter explicitly with `?published=`. A v1 document has
no `published` field at all, and missing means published: everything in the
database today is live on the site.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import AdminUser, OptionalUser, repository
from app.core.errors import NotFoundError
from app.core.pagination import ListParamsDep, Page, page
from app.models.auth import AuthenticatedUser
from app.models.common import ApiModel, DeleteResult, ReorderRequest, ReorderResult
from app.repositories.base import Document, DocumentRepository, Filters, Sort, is_object_id

# Priority first — higher `order` sorts first, matching v1's `index: -1` — then
# newest first as a stable tiebreak.
#
# `index` is in the key list because sorting happens in the database, before the
# model's `order`/`index` alias applies. A collection the backfill has not
# reached yet has no `order` field at all, so every document ties at null and
# `index` restores exactly the v1 order. After the backfill `index` is gone and
# this key is inert. A half-migrated collection sorts v2 documents above v1
# ones, which is why `scripts/migrate_v1_documents.py` runs to completion before
# traffic moves — see TODO.md.
DEFAULT_SORT: Sort = [("order", -1), ("index", -1), ("createdAt", -1), ("_id", -1)]


# A filter no document can satisfy. Used when a public caller asks to see
# unpublished records: answering with the published ones instead would be a
# silently ignored filter, which is worse than an empty page.
MATCHES_NOTHING: Filters = {"$and": [{"published": True}, {"published": False}]}


def visibility_filter(user: AuthenticatedUser | None, published: bool | None) -> Filters:
    """Translate the caller and an optional `?published=` into a query filter."""
    is_admin = user is not None and user.has_role("admin")
    if not is_admin:
        if published is False:
            return MATCHES_NOTHING
        # `$ne: false` rather than `== true`, so documents written before the
        # field existed stay visible.
        return {"published": {"$ne": False}}
    if published is None:
        return {}
    return {"published": True} if published else {"published": False}


async def find_or_404(
    repo: DocumentRepository,
    identifier: str,
    *,
    label: str,
    slug_field: str | None = None,
    filters: Filters | None = None,
) -> Document:
    """Look a record up by id, or by slug when the resource has one.

    An ObjectId is 24 hex characters and a slug never is, so there is no
    ambiguity between the two.
    """
    document: Document | None = None
    if is_object_id(identifier):
        document = await repo.get(identifier)
    elif slug_field:
        document = await repo.find_one({slug_field: identifier})
    if document is None and slug_field and document is None and not is_object_id(identifier):
        document = await repo.find_one({slug_field: identifier})
    if document is None:
        raise NotFoundError(f"No {label} with id or slug '{identifier}'.")
    if filters and not _passes(document, filters):
        raise NotFoundError(f"No {label} with id or slug '{identifier}'.")
    return document


def _passes(document: Document, filters: Filters) -> bool:
    # Only the visibility filter is ever checked here, so equality and `$ne`
    # cover it. Anything else belongs in the query, not in Python.
    for field, condition in filters.items():
        value = document.get(field)
        if isinstance(condition, dict):
            if "$ne" in condition and value == condition["$ne"]:
                return False
        elif value != condition:
            return False
    return True


def crud_router(
    *,
    collection: str,
    prefix: str,
    tag: str,
    label: str,
    read_model: type[Any],
    create_model: type[ApiModel],
    update_model: type[ApiModel],
    sort: Sort | None = None,
    slug_field: str | None = None,
    include_list: bool = True,
    transform: Callable[[Document], Document] | None = None,
) -> APIRouter:
    """Build a CRUD router.

    `transform` is applied to every stored document before the response model
    validates it. Resources with a computed field use it — blogs compose `path`
    and `canonicalUrl`, events derive `status` — and it runs on every route,
    not only the list, so a single record is never returned half-built.
    """
    router = APIRouter(prefix=prefix, tags=[tag])
    provide_repo = repository(collection)
    repo_dep = Annotated[DocumentRepository, Depends(provide_repo)]
    resolved_sort = sort or DEFAULT_SORT
    prepare = transform or (lambda document: document)

    async def list_records(
        params: ListParamsDep,
        user: OptionalUser,
        repo: repo_dep,
        published: Annotated[bool | None, Query()] = None,
    ) -> Any:
        filters = visibility_filter(user, published)
        documents, total = await repo.list(
            filters=filters, sort=resolved_sort, limit=params.limit, offset=params.offset
        )
        return page([read_model.model_validate(prepare(doc)) for doc in documents], total, params)

    list_records.__name__ = f"list_{collection}"
    list_records.__doc__ = f"List {label}s. Public callers see published records only."
    list_records.__annotations__ = {
        "params": ListParamsDep,
        "user": OptionalUser,
        "repo": repo_dep,
        "published": Annotated[bool | None, Query()],
        "return": Page[read_model],  # type: ignore[valid-type]
    }

    async def get_record(identifier: str, user: OptionalUser, repo: repo_dep) -> Any:
        document = await find_or_404(
            repo,
            identifier,
            label=label,
            slug_field=slug_field,
            filters=visibility_filter(user, None),
        )
        return read_model.model_validate(prepare(document))

    get_record.__name__ = f"get_{collection}"
    get_record.__doc__ = f"Get one {label} by id{' or slug' if slug_field else ''}."
    get_record.__annotations__ = {
        "identifier": str,
        "user": OptionalUser,
        "repo": repo_dep,
        "return": read_model,
    }

    async def create_record(payload: Any, _: AdminUser, repo: repo_dep) -> Any:
        document = await repo.create(payload.model_dump(by_alias=True, exclude_none=False))
        return read_model.model_validate(prepare(document))

    create_record.__name__ = f"create_{collection}"
    create_record.__doc__ = f"Create a {label}."
    create_record.__annotations__ = {
        "payload": create_model,
        "_": AdminUser,
        "repo": repo_dep,
        "return": read_model,
    }

    async def reorder_records(
        payload: ReorderRequest, _: AdminUser, repo: repo_dep
    ) -> ReorderResult:
        updated = await repo.set_order({item.id: item.order for item in payload.items})
        return ReorderResult(updated=updated)

    reorder_records.__name__ = f"reorder_{collection}"
    reorder_records.__annotations__ = {
        "payload": ReorderRequest,
        "_": AdminUser,
        "repo": repo_dep,
        "return": ReorderResult,
    }
    reorder_records.__doc__ = (
        f"Set the order of several {label}s in one request. Higher values sort first."
    )

    async def update_record(identifier: str, payload: Any, _: AdminUser, repo: repo_dep) -> Any:
        record = await find_or_404(repo, identifier, label=label, slug_field=slug_field)
        # Partial update: only the fields the caller actually sent.
        changes = payload.model_dump(by_alias=True, exclude_unset=True)
        if not changes:
            return read_model.model_validate(prepare(record))
        updated = await repo.update(str(record["_id"]), changes)
        if updated is None:  # pragma: no cover - the record was found a line ago
            raise NotFoundError(f"No {label} with id or slug '{identifier}'.")
        return read_model.model_validate(prepare(updated))

    update_record.__name__ = f"update_{collection}"
    update_record.__doc__ = f"Update a {label}. Only the fields sent are changed."
    update_record.__annotations__ = {
        "identifier": str,
        "payload": update_model,
        "_": AdminUser,
        "repo": repo_dep,
        "return": read_model,
    }

    async def delete_record(identifier: str, _: AdminUser, repo: repo_dep) -> DeleteResult:
        record = await find_or_404(repo, identifier, label=label, slug_field=slug_field)
        await repo.delete(str(record["_id"]))
        return DeleteResult(id=str(record["_id"]))

    delete_record.__name__ = f"delete_{collection}"
    delete_record.__annotations__ = {
        "identifier": str,
        "_": AdminUser,
        "repo": repo_dep,
        "return": DeleteResult,
    }
    delete_record.__doc__ = f"Delete a {label}."

    # Resources with filters of their own declare `GET ""` themselves and pass
    # include_list=False, so the spec never carries two list routes.
    if include_list:
        router.add_api_route(
            "",
            list_records,
            methods=["GET"],
            response_model=Page[read_model],  # type: ignore[valid-type]
            summary=f"List {label}s",
        )
    router.add_api_route(
        "",
        create_record,
        methods=["POST"],
        response_model=read_model,
        status_code=status.HTTP_201_CREATED,
        summary=f"Create a {label}",
    )
    # Declared before `/{identifier}` so `order` is not read as an id.
    router.add_api_route(
        "/order",
        reorder_records,
        methods=["PATCH"],
        response_model=ReorderResult,
        summary=f"Reorder {label}s",
    )
    router.add_api_route(
        "/{identifier}",
        get_record,
        methods=["GET"],
        response_model=read_model,
        summary=f"Get a {label}",
    )
    router.add_api_route(
        "/{identifier}",
        update_record,
        methods=["PATCH"],
        response_model=read_model,
        summary=f"Update a {label}",
    )
    router.add_api_route(
        "/{identifier}",
        delete_record,
        methods=["DELETE"],
        response_model=DeleteResult,
        summary=f"Delete a {label}",
    )
    return router


__all__ = ["DEFAULT_SORT", "Response", "crud_router", "find_or_404", "visibility_filter"]
