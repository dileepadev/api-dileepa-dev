"""The seven straight-CRUD profile resources.

Each is a `crud_router` with its own models. Nothing here is bespoke; if one of
them needs behaviour the others do not, it gets its own module rather than a
flag on the factory.

Five were ported from v1. `pillars` and `speaking_topics` are new in v2.0.0 and
hold copy that used to be compiled into the website — they are here, rather than
in modules of their own, precisely because they need nothing the other five do
not.
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
    Pillar,
    PillarCreate,
    PillarUpdate,
    SpeakingTopic,
    SpeakingTopicCreate,
    SpeakingTopicUpdate,
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

pillars_router = crud_router(
    collection="pillars",
    prefix="/pillars",
    tag="pillars",
    label="pillar",
    read_model=Pillar,
    create_model=PillarCreate,
    update_model=PillarUpdate,
)

# `/speaking-topics` on the wire, `speaking_topics` in Mongo. The path is
# hyphenated because every other path here is a single word and a URL is not
# the place to start reading snake_case; the collection is not, because it sits
# beside `blog_views` and `comment_reactions`.
speaking_topics_router = crud_router(
    collection="speaking_topics",
    prefix="/speaking-topics",
    tag="speaking-topics",
    label="speaking topic",
    read_model=SpeakingTopic,
    create_model=SpeakingTopicCreate,
    update_model=SpeakingTopicUpdate,
)
