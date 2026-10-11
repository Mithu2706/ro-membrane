"""Protected admin console API. Every route requires a valid admin session;
state-changing routes additionally require the CSRF header (see security.py).
"""
from __future__ import annotations

import csv
import io
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..catalog import CRITICAL_PARAMETERS, PARAMETERS
from ..config import settings
from ..db import get_db
from ..engine.recommend import methodology
from ..models import (
    EVIDENCE_TYPES,
    MEMBRANE_CATEGORIES,
    SOURCE_TYPES,
    VERIFICATION_STATUSES,
    AdminSession,
    AuditLog,
    ClientSubmission,
    ExperimentalObservation,
    Membrane,
    MembraneSpecification,
    ResearchSource,
)
from ..schemas import ArchiveIn, LoginIn, MembraneIn, ObservationIn, SourceIn, SpecIn, VerifyIn
from ..security import admin_configured, create_session, destroy_session, optional_admin, require_admin, verify_credentials
from ..services import export as export_svc
from ..services.repository import load_sources, membrane_to_evidence, observation_dict, source_dict
from .public import report_response

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Simple in-memory login throttling per client address
_FAILED: dict[str, list[float]] = defaultdict(list)
MAX_FAILURES, WINDOW_S = 8, 600


def audit(db: Session, user: str, action: str, entity: str, entity_id, details: dict | None = None) -> None:
    db.add(AuditLog(username=user, action=action, entity=entity, entity_id=None if entity_id is None else str(entity_id),
                    details=details or {}))


def _row(obj, exclude=()) -> dict:
    out = {}
    for c in obj.__table__.columns:
        if c.name in exclude:
            continue
        v = getattr(obj, c.name)
        out[c.name] = v.isoformat() if isinstance(v, datetime) else v
    return out


# Authentication -----------------------------------------------------------------

@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if not admin_configured():
        raise HTTPException(503, "Admin console is not configured. Set RO_ADMIN_PASSWORD or RO_ADMIN_PASSWORD_HASH.")
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    _FAILED[ip] = [t for t in _FAILED[ip] if now - t < WINDOW_S]
    if len(_FAILED[ip]) >= MAX_FAILURES:
        raise HTTPException(429, "Too many failed attempts. Try again later.")
    if not verify_credentials(body.username, body.password):
        _FAILED[ip].append(now)
        raise HTTPException(401, "Invalid username or password")
    _FAILED.pop(ip, None)
    sess = create_session(db, response, body.username)
    audit(db, body.username, "login", "session", None)
    db.commit()
    return {"username": sess.username, "csrf_token": sess.csrf_token}


@router.post("/logout")
def logout(response: Response, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    destroy_session(db, response, sess)
    return {"ok": True}


@router.get("/me")
def me(sess: AdminSession | None = Depends(optional_admin)):
    if sess is None:
        return {"authenticated": False, "configured": admin_configured()}
    return {"authenticated": True, "username": sess.username, "csrf_token": sess.csrf_token}


# Dashboard ---------------------------------------------------------------------

@router.get("/stats")
def stats(_: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    membranes = db.scalars(select(Membrane).options(selectinload(Membrane.specifications))).all()
    active = [m for m in membranes if not m.archived]
    coverage = []
    for m in active:
        ev = membrane_to_evidence(m)
        present = [p for p in CRITICAL_PARAMETERS if ev.get(p)]
        has_perf = bool(ev.get("rated_flux_lmh") or (ev.get("rated_permeate_flow_m3d") and ev.get("active_area_m2")))
        coverage.append({"id": m.id, "name": m.display_name, "category": m.category,
                         "verification_status": m.verification_status,
                         "critical_present": len(present) + (1 if has_perf else 0),
                         "critical_total": len(CRITICAL_PARAMETERS) + 1,
                         "missing": [PARAMETERS[p][0] for p in CRITICAL_PARAMETERS if p not in present]
                         + ([] if has_perf else ["Rated flow/flux"]),
                         "conflicts": sorted(ev.conflicts.keys()), "spec_count": len(m.specifications)})
    subs = db.scalars(select(ClientSubmission)).all()
    by_outcome, by_app = defaultdict(int), defaultdict(int)
    for s in subs:
        by_outcome[s.outcome] += 1
        by_app[s.application] += 1
    recent = db.scalars(select(ClientSubmission).order_by(ClientSubmission.created_at.desc()).limit(6)).all()
    return {
        "submissions_total": len(subs),
        "submissions_by_outcome": by_outcome,
        "submissions_by_application": by_app,
        "membranes_active": len(active),
        "membranes_archived": len(membranes) - len(active),
        "membranes_verified": sum(1 for m in active if m.verification_status == "verified"),
        "sources_total": db.scalar(select(func.count(ResearchSource.id))),
        "specifications_total": db.scalar(select(func.count(MembraneSpecification.id))),
        "observations_total": db.scalar(select(func.count(ExperimentalObservation.id))),
        "coverage": coverage,
        "recent_submissions": [_submission_summary(s) for s in recent],
    }


def _submission_summary(s: ClientSubmission) -> dict:
    i = s.inputs or {}
    return {"id": s.id, "created_at": s.created_at.isoformat(), "client_name": s.client_name,
            "client_organization": s.client_organization, "project_name": s.project_name, "application": s.application,
            "outcome": s.outcome, "recommended_membrane": s.recommended_membrane, "feed_tds_mg_l": i.get("feed_tds_mg_l"),
            "permeate_flow_m3d": i.get("permeate_flow_m3d"), "recovery_pct": i.get("recovery_pct"),
            "warning_count": len(s.warnings or []), "input_origin": i.get("input_origin", "client")}


@router.get("/vocabularies")
def vocabularies(_: AdminSession = Depends(require_admin)):
    return {"parameters": {k: {"label": v[0], "unit": v[1]} for k, v in PARAMETERS.items()},
            "evidence_types": EVIDENCE_TYPES, "verification_statuses": VERIFICATION_STATUSES,
            "categories": MEMBRANE_CATEGORIES, "source_types": SOURCE_TYPES,
            "applications": ["bwro", "swro", "industrial", "second_pass", "other"]}


@router.get("/methodology")
def get_methodology(_: AdminSession = Depends(require_admin)):
    from ..engine import recommend as r

    return {"equations": methodology(), "assumptions": r.ASSUMPTIONS, "unavailable": r.UNAVAILABLE,
            "policy": {"pressure_margin_fraction": r.PRESSURE_MARGIN_FRACTION,
                       "element_flow_tolerance": r.ELEMENT_FLOW_TOLERANCE,
                       "comparable_salinity_ratio": r.COMPARABLE_SALINITY_RATIO,
                       "comparable_temperature_delta_c": r.COMPARABLE_TEMPERATURE_DELTA_C,
                       "calc_range_tds_mg_l": r.CALC_RANGE_TDS_MG_L, "calc_range_temperature_c": r.CALC_RANGE_TEMPERATURE_C},
            "compatibility": r.COMPATIBILITY}


# Submissions -----------------------------------------------------------------------

@router.get("/submissions")
def list_submissions(q: str | None = None, application: str | None = None, outcome: str | None = None,
                     page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
                     _: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(ClientSubmission)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(ClientSubmission.client_name.ilike(like), ClientSubmission.client_organization.ilike(like),
                              ClientSubmission.project_name.ilike(like), ClientSubmission.client_email.ilike(like),
                              ClientSubmission.recommended_membrane.ilike(like)))
    if application:
        stmt = stmt.where(ClientSubmission.application == application)
    if outcome:
        stmt = stmt.where(ClientSubmission.outcome == outcome)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(ClientSubmission.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_submission_summary(s) for s in rows]}


@router.get("/submissions/{sid}")
def get_submission(sid: int, _: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    s = db.get(ClientSubmission, sid)
    if s is None:
        raise HTTPException(404, "Submission not found")
    d = _row(s, exclude=("public_token",))
    d["reference"] = s.public_token
    return d


@router.get("/submissions/{sid}/report.pdf")
def submission_report(sid: int, _: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    s = db.get(ClientSubmission, sid)
    if s is None:
        raise HTTPException(404, "Submission not found")
    return report_response(s, load_sources(db))


# Membranes -------------------------------------------------------------------------

def _membrane_full(m: Membrane, sources: dict) -> dict:
    ev = membrane_to_evidence(m)
    d = _row(m)
    d["display_name"] = m.display_name
    d["specifications"] = [{**_row(s), "label": PARAMETERS.get(s.parameter, (s.parameter, ""))[0],
                            "source_title": sources.get(s.source_id, {}).get("title")} for s in m.specifications]
    d["observations"] = [{**observation_dict(o), "source_title": sources.get(o.source_id, {}).get("title")}
                         for o in m.observations]
    d["resolved"] = {k: v.as_dict() for k, v in ev.params.items()}
    d["conflicts"] = {k: [p.as_dict() for p in v] for k, v in ev.conflicts.items()}
    d["missing_critical"] = [PARAMETERS[p][0] for p in CRITICAL_PARAMETERS if not ev.get(p)]
    return d


@router.get("/membranes")
def list_membranes(include_archived: bool = True, _: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Membrane).options(selectinload(Membrane.specifications), selectinload(Membrane.observations))
    if not include_archived:
        stmt = stmt.where(Membrane.archived.is_(False))
    out = []
    for m in db.scalars(stmt.order_by(Membrane.manufacturer, Membrane.model)):
        ev = membrane_to_evidence(m)
        out.append({**_row(m), "display_name": m.display_name, "spec_count": len(m.specifications),
                    "observation_count": len(m.observations), "conflicts": sorted(ev.conflicts.keys()),
                    "missing_critical": [PARAMETERS[p][0] for p in CRITICAL_PARAMETERS if not ev.get(p)]})
    return out


def _get_membrane(db: Session, mid: int) -> Membrane:
    m = db.get(Membrane, mid)
    if m is None:
        raise HTTPException(404, "Membrane not found")
    return m


@router.get("/membranes/{mid}")
def get_membrane(mid: int, _: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    return _membrane_full(_get_membrane(db, mid), load_sources(db))


@router.post("/membranes", status_code=201)
def create_membrane(body: MembraneIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Membrane).where(Membrane.manufacturer == body.manufacturer, Membrane.model == body.model)):
        raise HTTPException(409, "A membrane with this manufacturer and model already exists")
    m = Membrane(**body.model_dump())
    db.add(m)
    db.flush()
    audit(db, sess.username, "create", "membrane", m.id, body.model_dump())
    db.commit()
    return _membrane_full(m, load_sources(db))


@router.put("/membranes/{mid}")
def update_membrane(mid: int, body: MembraneIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    m = _get_membrane(db, mid)
    before = {k: getattr(m, k) for k in body.model_dump()}
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    audit(db, sess.username, "update", "membrane", mid, {"before": before, "after": body.model_dump()})
    db.commit()
    return _membrane_full(m, load_sources(db))


@router.post("/membranes/{mid}/archive")
def archive_membrane(mid: int, body: ArchiveIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    m = _get_membrane(db, mid)
    m.archived = body.archived
    audit(db, sess.username, "archive" if body.archived else "unarchive", "membrane", mid)
    db.commit()
    return {"id": mid, "archived": m.archived}


@router.post("/membranes/{mid}/verify")
def verify_membrane(mid: int, body: VerifyIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    m = _get_membrane(db, mid)
    audit(db, sess.username, "verify", "membrane", mid, {"from": m.verification_status, "to": body.verification_status})
    m.verification_status = body.verification_status
    db.commit()
    return {"id": mid, "verification_status": m.verification_status}


# Specifications ------------------------------------------------------------------------

def _check_source(db: Session, source_id: int | None) -> None:
    if source_id is not None and db.get(ResearchSource, source_id) is None:
        raise HTTPException(422, f"Source {source_id} does not exist")


@router.post("/membranes/{mid}/specifications", status_code=201)
def add_spec(mid: int, body: SpecIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    _get_membrane(db, mid)
    _check_source(db, body.source_id)
    s = MembraneSpecification(membrane_id=mid, **body.model_dump())
    db.add(s)
    db.flush()
    audit(db, sess.username, "create", "specification", s.id, {"membrane_id": mid, **body.model_dump()})
    db.commit()
    return _row(s)


@router.put("/specifications/{spec_id}")
def update_spec(spec_id: int, body: SpecIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    s = db.get(MembraneSpecification, spec_id)
    if s is None:
        raise HTTPException(404, "Specification not found")
    _check_source(db, body.source_id)
    before = _row(s)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    audit(db, sess.username, "update", "specification", spec_id, {"before": before, "after": body.model_dump()})
    db.commit()
    return _row(s)


@router.delete("/specifications/{spec_id}")
def delete_spec(spec_id: int, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    s = db.get(MembraneSpecification, spec_id)
    if s is None:
        raise HTTPException(404, "Specification not found")
    audit(db, sess.username, "delete", "specification", spec_id, _row(s))
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.post("/specifications/{spec_id}/verify")
def verify_spec(spec_id: int, body: VerifyIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    s = db.get(MembraneSpecification, spec_id)
    if s is None:
        raise HTTPException(404, "Specification not found")
    audit(db, sess.username, "verify", "specification", spec_id, {"from": s.verification_status, "to": body.verification_status})
    s.verification_status = body.verification_status
    db.commit()
    return _row(s)


# Observations ------------------------------------------------------------------------------

@router.post("/membranes/{mid}/observations", status_code=201)
def add_observation(mid: int, body: ObservationIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    _get_membrane(db, mid)
    _check_source(db, body.source_id)
    o = ExperimentalObservation(membrane_id=mid, **body.model_dump())
    db.add(o)
    db.flush()
    audit(db, sess.username, "create", "observation", o.id, {"membrane_id": mid})
    db.commit()
    return _row(o)


@router.delete("/observations/{oid}")
def delete_observation(oid: int, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    o = db.get(ExperimentalObservation, oid)
    if o is None:
        raise HTTPException(404, "Observation not found")
    audit(db, sess.username, "delete", "observation", oid, _row(o))
    db.delete(o)
    db.commit()
    return {"ok": True}


# Sources ------------------------------------------------------------------------------------

@router.get("/sources")
def list_sources(_: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(MembraneSpecification.source_id, func.count()).group_by(MembraneSpecification.source_id)).all())
    ocounts = dict(db.execute(select(ExperimentalObservation.source_id, func.count()).group_by(ExperimentalObservation.source_id)).all())
    return [{**source_dict(s), "spec_count": counts.get(s.id, 0), "observation_count": ocounts.get(s.id, 0)}
            for s in db.scalars(select(ResearchSource).order_by(ResearchSource.id))]


@router.post("/sources", status_code=201)
def create_source(body: SourceIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    s = ResearchSource(**body.model_dump())
    db.add(s)
    db.flush()
    audit(db, sess.username, "create", "source", s.id, body.model_dump())
    db.commit()
    return source_dict(s)


@router.put("/sources/{source_id}")
def update_source(source_id: int, body: SourceIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    s = db.get(ResearchSource, source_id)
    if s is None:
        raise HTTPException(404, "Source not found")
    before = source_dict(s)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    audit(db, sess.username, "update", "source", source_id, {"before": before, "after": body.model_dump()})
    db.commit()
    return source_dict(s)


@router.post("/sources/{source_id}/verify")
def verify_source(source_id: int, body: VerifyIn, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    s = db.get(ResearchSource, source_id)
    if s is None:
        raise HTTPException(404, "Source not found")
    audit(db, sess.username, "verify", "source", source_id, {"from": s.verification_status, "to": body.verification_status})
    s.verification_status = body.verification_status
    db.commit()
    return source_dict(s)


# CSV import -----------------------------------------------------------------------------------

IMPORT_COLUMNS = ["manufacturer", "model", "parameter", "value", "value_min", "value_max", "value_text", "unit",
                  "source_id", "evidence_type", "test_conditions", "verification_status", "notes"]


def _f(v: str | None) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    return float(str(v).replace(",", ""))


@router.get("/import/specifications/template.csv")
def import_template(_: AdminSession = Depends(require_admin)):
    body = ",".join(IMPORT_COLUMNS) + "\n" + "Example Mfr,EXAMPLE-400,max_operating_pressure_bar,41,,,600 psig (41 bar),bar,1,manufacturer-rated,,unverified,\n"
    return Response(body, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="specifications_template.csv"'})


@router.post("/import/specifications")
async def import_specifications(file: UploadFile = File(...), dry_run: bool = True,
                                sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(413, "File too large (max 2 MB)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "File must be UTF-8 encoded CSV")
    reader = csv.DictReader(io.StringIO(text))
    missing_cols = [c for c in ("manufacturer", "model", "parameter", "evidence_type") if c not in (reader.fieldnames or [])]
    if missing_cols:
        raise HTTPException(422, f"Missing required columns: {', '.join(missing_cols)}")
    errors, valid = [], []
    for i, row in enumerate(reader, start=2):
        try:
            m = db.scalar(select(Membrane).where(Membrane.manufacturer == (row.get("manufacturer") or "").strip(),
                                                 Membrane.model == (row.get("model") or "").strip()))
            if m is None:
                raise ValueError("membrane not found (create it first)")
            sid = int(row["source_id"]) if (row.get("source_id") or "").strip() else None
            if sid is not None and db.get(ResearchSource, sid) is None:
                raise ValueError(f"source {sid} not found")
            spec = SpecIn(parameter=(row.get("parameter") or "").strip(), value=_f(row.get("value")),
                          value_min=_f(row.get("value_min")), value_max=_f(row.get("value_max")),
                          value_text=(row.get("value_text") or None), unit=(row.get("unit") or None), source_id=sid,
                          evidence_type=(row.get("evidence_type") or "").strip(),
                          test_conditions=row.get("test_conditions") or None,
                          verification_status=(row.get("verification_status") or "unverified").strip(),
                          notes=row.get("notes") or None)
            valid.append((m.id, spec))
        except Exception as e:  # noqa: BLE001 - report every row problem to the admin
            msg = str(e).splitlines()
            errors.append({"row": i, "error": " ".join(msg[:3])})
    if not dry_run and not errors:
        for mid, spec in valid:
            db.add(MembraneSpecification(membrane_id=mid, **spec.model_dump()))
        audit(db, sess.username, "import", "specification", None, {"rows": len(valid), "file": file.filename})
        db.commit()
    return {"dry_run": dry_run, "valid_rows": len(valid), "errors": errors,
            "imported": 0 if (dry_run or errors) else len(valid)}


# Export ------------------------------------------------------------------------------------------

@router.get("/export/{dataset}.csv")
def export_csv(dataset: str, sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    if dataset not in export_svc.DATASETS:
        raise HTTPException(404, "Unknown dataset")
    cols, rows = export_svc.rows_for(db, dataset)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(export_svc.to_csv(cols, rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{dataset}_{stamp}.csv"'})


@router.get("/export/workbook.xlsx")
def export_xlsx(sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    data = export_svc.to_xlsx(db, export_svc.DATASETS)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="ro_platform_export_{stamp}.xlsx"'})


# Backup ------------------------------------------------------------------------------------------

@router.post("/backup")
def backup(sess: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    if settings.database_url:
        raise HTTPException(501, "This deployment uses a hosted database: use your database provider's backups "
                                 "(e.g. Neon point-in-time restore) and the Excel export for a copy of the records.")
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    target = settings.backup_dir / f"ro_membrane_{stamp}.db"
    src = sqlite3.connect(settings.database_path)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    audit(db, sess.username, "backup", "database", None, {"file": target.name})
    db.commit()
    return Response(target.read_bytes(), media_type="application/vnd.sqlite3",
                    headers={"Content-Disposition": f'attachment; filename="{target.name}"'})


@router.get("/audit")
def audit_log(limit: int = Query(100, ge=1, le=1000), _: AdminSession = Depends(require_admin), db: Session = Depends(get_db)):
    return [_row(a) for a in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))]
