"""Applying a reaction, wherever the thing being reacted to lives.

Posts and comments both carry the same four reactions, and the rule for
changing one is identical: a reader has at most one, pressing the one they have
takes it back, and the aggregate moves by the delta rather than being recounted.

That rule was written twice before this module existed, which is one place for
the two copies to drift — and the way they would drift is a count that no longer
matches the records behind it, which nothing would report.

The subject and the per-reader record are addressed by filter rather than by
type, so this knows nothing about blogs or comments. It only knows that
something holds counters and something else remembers who chose what.
"""

from __future__ import annotations

from app.models.blog import REACTION_KINDS, ReactionKind
from app.repositories.base import Document, DocumentRepository, Filters


async def viewer_reaction(
    records: DocumentRepository, record_filter: Filters
) -> ReactionKind | None:
    document = await records.find_one(record_filter)
    reaction = (document or {}).get("reaction")
    return reaction if reaction in REACTION_KINDS else None


async def apply_reaction(
    *,
    subjects: DocumentRepository,
    subject_filter: Filters,
    records: DocumentRepository,
    record_filter: Filters,
    record_seed: Document,
    requested: ReactionKind | None,
) -> tuple[Document | None, ReactionKind | None]:
    """Set, change, or clear one reader's reaction.

    Returns the subject after the counters moved, and what the reader now holds.

    `record_seed` is what identifies the record when one has to be created — the
    same fields the filter matches on. It is passed separately because the
    filter may contain operators, and an operator is not a value to store.
    """
    previous = await viewer_reaction(records, record_filter)

    # Pressing the reaction you already have is how you take it back. The UI
    # renders these as toggles, and a toggle that cannot untoggle is a trap.
    chosen = None if requested == previous else requested

    if chosen == previous:
        return await subjects.find_one(subject_filter), previous

    amounts: dict[str, int] = {}
    if previous is not None:
        amounts[f"reactions.{previous}"] = -1
    if chosen is not None:
        amounts[f"reactions.{chosen}"] = 1

    if chosen is None:
        await records.delete_one(record_filter)
    else:
        await records.update_one(record_filter, {**record_seed, "reaction": chosen}, upsert=True)

    if not amounts:
        return await subjects.find_one(subject_filter), chosen

    updated = await subjects.increment(subject_filter, amounts)
    return updated, chosen
