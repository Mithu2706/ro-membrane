"""Versioned database initialisation.

Each migration has an integer version and is applied once; applied versions are
recorded in ``schema_version``. To evolve the schema, append a new function to
``MIGRATIONS`` - never edit an applied one.
"""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from . import db as dbmod
from .models import Base, ExperimentalObservation, Membrane, MembraneSpecification, ResearchSource, SchemaVersion
from .seed_data import MEMBRANES, SOURCES


def _v1_schema(engine: Engine, session: Session) -> None:
    Base.metadata.create_all(engine)


def _v2_seed(engine: Engine, session: Session) -> None:
    seed_starter_dataset(session)


def _v3_audit_corrections(engine: Engine, session: Session) -> None:
    """Audit 2026-10-10: bring existing databases in line with the corrected starter dataset.

    * Add the per-element minimum concentrate-to-permeate ratio (5:1) stated in the verified
      Hydranautics SWC4+ and ESPA-2540 datasheets.
    * Remove the unsourced "industrial" application from FilmTec BW30-400/34i.
    Idempotent: fresh databases already receive these from the v2 seed.
    """
    seed_by_model = {(m["manufacturer"], m["model"]): m for m in MEMBRANES}
    for key in (("Hydranautics (Nitto)", "SWC4+"), ("Hydranautics (Nitto)", "ESPA-2540")):
        membrane = session.scalar(select(Membrane).where(Membrane.manufacturer == key[0], Membrane.model == key[1]))
        if membrane is None:
            continue
        if any(s.parameter == "min_concentrate_permeate_ratio" for s in membrane.specifications):
            continue
        spec = dict(next(s for s in seed_by_model[key]["specs"] if s["parameter"] == "min_concentrate_permeate_ratio"))
        src = session.scalar(select(ResearchSource).where(ResearchSource.title == SOURCES[spec.pop("source")]["title"]))
        session.add(MembraneSpecification(membrane_id=membrane.id, source_id=src.id if src else None, **spec))
    bw = session.scalar(select(Membrane).where(Membrane.manufacturer == "FilmTec (Dow/DuPont)", Membrane.model == "BW30-400/34i"))
    if bw is not None and "industrial" in (bw.intended_applications or []):
        bw.intended_applications = [a for a in bw.intended_applications if a != "industrial"]
        bw.notes = seed_by_model[("FilmTec (Dow/DuPont)", "BW30-400/34i")]["notes"]


MIGRATIONS: list[tuple[int, str, Callable[[Engine, Session], None]]] = [
    (1, "Initial schema", _v1_schema),
    (2, "Starter research dataset from supplied review report and verified datasheets", _v2_seed),
    (3, "Audit corrections: per-element recovery limits; remove unsourced application", _v3_audit_corrections),
]


def seed_starter_dataset(session: Session) -> None:
    source_ids: dict[str, int] = {}
    for key, data in SOURCES.items():
        existing = session.scalar(select(ResearchSource).where(ResearchSource.title == data["title"]))
        if existing is None:
            existing = ResearchSource(**data)
            session.add(existing)
            session.flush()
        source_ids[key] = existing.id

    for m in MEMBRANES:
        m = dict(m)
        specs = m.pop("specs", [])
        observations = m.pop("observations", [])
        if session.scalar(select(Membrane).where(Membrane.manufacturer == m["manufacturer"], Membrane.model == m["model"])):
            continue
        membrane = Membrane(**m)
        session.add(membrane)
        session.flush()
        for spec in specs:
            spec = dict(spec)
            spec["source_id"] = source_ids[spec.pop("source")]
            session.add(MembraneSpecification(membrane_id=membrane.id, **spec))
        for obs in observations:
            obs = dict(obs)
            obs["source_id"] = source_ids[obs.pop("source")]
            session.add(ExperimentalObservation(membrane_id=membrane.id, **obs))


def current_version(engine: Engine) -> int:
    if not inspect(engine).has_table("schema_version"):
        return 0
    with Session(engine) as s:
        versions = s.scalars(select(SchemaVersion.version)).all()
    return max(versions, default=0)


MIGRATION_LOCK_KEY = 72_746_617  # arbitrary constant identifying Osmora's migration lock


def _apply(engine: Engine) -> int:
    Base.metadata.create_all(engine, tables=[SchemaVersion.__table__])
    applied = current_version(engine)
    for version, description, fn in MIGRATIONS:
        if version <= applied:
            continue
        with Session(engine) as session:
            fn(engine, session)
            session.add(SchemaVersion(version=version, description=description))
            session.commit()
        applied = version
    return applied


def migrate(engine: Engine | None = None) -> int:
    """Apply pending migrations.

    On Postgres a session-level advisory lock serialises concurrent callers, so several serverless
    instances cold-starting at once cannot seed the dataset twice. SQLite is single-process here.
    """
    engine = engine or dbmod.engine
    if engine.dialect.name != "postgresql":
        return _apply(engine)
    with engine.connect() as lock_conn:
        lock_conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": MIGRATION_LOCK_KEY})
        try:
            return _apply(engine)
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": MIGRATION_LOCK_KEY})
