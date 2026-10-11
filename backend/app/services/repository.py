"""Bridges ORM records and the database-independent engine types."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..engine.evidence import MembraneEvidence, ParamValue, resolve_parameters
from ..models import ExperimentalObservation, Membrane, MembraneSpecification, ResearchSource


def spec_to_param(s: MembraneSpecification) -> ParamValue:
    return ParamValue(parameter=s.parameter, value=s.value, unit=s.unit, evidence_type=s.evidence_type,
                      verification_status=s.verification_status, source_id=s.source_id, value_min=s.value_min,
                      value_max=s.value_max, value_text=s.value_text, test_conditions=s.test_conditions, spec_id=s.id,
                      notes=s.notes)


def observation_dict(o: ExperimentalObservation) -> dict:
    return {c.name: getattr(o, c.name) for c in ExperimentalObservation.__table__.columns
            if c.name not in ("created_at",)}


def membrane_to_evidence(m: Membrane) -> MembraneEvidence:
    params, conflicts = resolve_parameters([spec_to_param(s) for s in m.specifications])
    return MembraneEvidence(id=m.id, manufacturer=m.manufacturer, model=m.model, category=m.category,
                            intended_applications=list(m.intended_applications or []), element_size=m.element_size,
                            verification_status=m.verification_status, notes=m.notes, feed_limitations=m.feed_limitations,
                            params=params, conflicts=conflicts, observations=[observation_dict(o) for o in m.observations])


def load_active_membranes(db: Session) -> list[MembraneEvidence]:
    rows = db.scalars(
        select(Membrane).where(Membrane.archived.is_(False))
        .options(selectinload(Membrane.specifications), selectinload(Membrane.observations))
        .order_by(Membrane.manufacturer, Membrane.model)
    ).all()
    return [membrane_to_evidence(m) for m in rows]


def source_dict(s: ResearchSource) -> dict:
    return {"id": s.id, "title": s.title, "authors": s.authors, "year": s.year, "doi": s.doi, "url": s.url,
            "source_type": s.source_type, "publisher": s.publisher, "page_table": s.page_table,
            "verification_status": s.verification_status, "notes": s.notes}


def load_sources(db: Session) -> dict[int, dict]:
    return {s.id: source_dict(s) for s in db.scalars(select(ResearchSource)).all()}
