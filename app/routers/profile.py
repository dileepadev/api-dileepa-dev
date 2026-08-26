"""The five straight-CRUD resources ported from v1.

Each is a `crud_router` with its own models. Nothing here is bespoke; if one of
them needs behaviour the others do not, it gets its own module rather than a
flag on the factory.
"""

from __future__ import annotations

from app.models.profile import (
    Community,
    CommunityCreate,
    CommunityUpdate,
    Education,
    EducationCreate,
    EducationUpdate,
    Experience,
    ExperienceCreate,
    ExperienceUpdate,
    Tool,
    ToolCreate,
    ToolUpdate,
    Video,
    VideoCreate,
    VideoUpdate,
)
from app.routers.crud import crud_router

experiences_router = crud_router(
    collection="experiences",
    prefix="/experiences",
    tag="experiences",
    label="experience",
    read_model=Experience,
    create_model=ExperienceCreate,
    update_model=ExperienceUpdate,
)

educations_router = crud_router(
    collection="educations",
    prefix="/educations",
    tag="educations",
    label="education",
    read_model=Education,
    create_model=EducationCreate,
    update_model=EducationUpdate,
)

tools_router = crud_router(
    collection="tools",
    prefix="/tools",
    tag="tools",
    label="tool",
    read_model=Tool,
    create_model=ToolCreate,
    update_model=ToolUpdate,
)

communities_router = crud_router(
    collection="communities",
    prefix="/communities",
    tag="communities",
    label="community",
    plural="communities",
    read_model=Community,
    create_model=CommunityCreate,
    update_model=CommunityUpdate,
)

videos_router = crud_router(
    collection="videos",
    prefix="/videos",
    tag="videos",
    label="video",
    read_model=Video,
    create_model=VideoCreate,
    update_model=VideoUpdate,
)
