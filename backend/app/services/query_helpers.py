"""Zentrale Eager-Loading-Strategien je Aggregat (gegen N+1).

Bündelt die wiederkehrenden ``selectinload``-Kombinationen, die sonst über
viele Routes/Services verstreut waren. Aufrufer behalten ihr eigenes
``select(...).where(...)`` und übergeben nur noch die hier gebündelten
Loader-Options::

    from app.services.query_helpers import case_relations

    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(*case_relations())
    )

``selectinload`` erzeugt pro Relation genau eine zusätzliche Query
(unabhängig von der Zeilenzahl) und vermeidet so N+1-Lazy-Loads im
async-Kontext (``MissingGreenlet``).
"""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from app.models import CaseModel, FindingModel


def case_relations(
    *,
    documents: bool = True,
    findings: bool = True,
    privacy_policies: bool = False,
) -> list[LoaderOption]:
    """Loader-Options für das ``Case``-Aggregat.

    Default lädt ``documents`` + ``findings`` eager — die mit Abstand
    häufigste Kombination. Über die Flags lassen sich die selteneren
    Varianten (nur documents, nur findings, inkl. privacy_policies)
    abbilden, ohne die Aufruferseite zu duplizieren.
    """
    opts: list[LoaderOption] = []
    if documents:
        opts.append(selectinload(CaseModel.documents))
    if findings:
        opts.append(selectinload(CaseModel.findings))
    if privacy_policies:
        opts.append(selectinload(CaseModel.privacy_policies))
    return opts


def finding_relations(*, case: bool = True) -> list[LoaderOption]:
    """Loader-Options für das ``Finding``-Aggregat (N:1 zu ``Case``)."""
    opts: list[LoaderOption] = []
    if case:
        opts.append(selectinload(FindingModel.case))
    return opts


def select_case_by_id(
    case_id: UUID,
    *,
    documents: bool = True,
    findings: bool = True,
    privacy_policies: bool = False,
) -> Select[tuple[CaseModel]]:
    """Fertiges ``SELECT`` für einen einzelnen Case inkl. Eager-Loading.

    Convenience für den häufigsten Single-Case-Fetch. Für Listen-/Filter-
    Queries stattdessen ``case_relations()`` direkt in ``.options(...)``
    verwenden.
    """
    return (
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(
            *case_relations(
                documents=documents,
                findings=findings,
                privacy_policies=privacy_policies,
            )
        )
    )
