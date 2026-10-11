"""Public (client) endpoints.

Client submissions are reachable only through an unguessable per-submission
token returned at creation; there is no listing or enumeration endpoint.
Responses use the client view (no internal calculation details).
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..engine import ENGINE_VERSION
from ..engine.inputs import AssessmentInput
from ..engine.recommend import assess, client_view
from ..models import ClientSubmission, Membrane, ResearchSource
from ..services.report import build_report
from ..services.repository import load_active_membranes, load_sources

router = APIRouter(prefix="/api", tags=["public"])

DEMO_EXAMPLES = [
    {
        "key": "swro",
        "title": "Coastal seawater intake",
        "description": "Open-sea intake, 5,000 m³/day drinking-water plant with a boron target.",
        "inputs": {
            "application": "swro", "feed_tds_mg_l": 35000, "feed_temperature_c": 25, "available_pressure_bar": 70,
            "permeate_flow_m3d": 5000, "recovery_pct": 45, "target_permeate_tds_mg_l": 500, "target_boron_mg_l": 1.0,
            "design_flux_lmh": 14, "pressure_loss_allowance_bar": 2, "priority": "balanced",
            "chemistry": {"ph": 8.1, "alkalinity_mg_l_caco3": 140, "calcium_mg_l": 410, "magnesium_mg_l": 1290,
                          "sulfate_mg_l": 2700, "chloride_mg_l": 19400, "sodium_mg_l": 10800, "boron_mg_l": 4.8,
                          "sdi": 3.0, "turbidity_ntu": 0.3, "oxidant_exposure": "dechlorinated",
                          "pretreatment": ["Ultrafiltration", "Dechlorination", "Antiscalant"]},
        },
    },
    {
        "key": "bwro",
        "title": "Brackish groundwater well",
        "description": "Inland well water, 1,000 m³/day, low-pressure pump.",
        "inputs": {
            "application": "bwro", "feed_tds_mg_l": 2500, "feed_temperature_c": 22, "available_pressure_bar": 16,
            "permeate_flow_m3d": 1000, "recovery_pct": 70, "target_permeate_tds_mg_l": 150, "design_flux_lmh": 22,
            "pressure_loss_allowance_bar": 1.5, "priority": "low_pressure",
            "chemistry": {"ph": 7.2, "alkalinity_mg_l_caco3": 120, "calcium_mg_l": 60, "magnesium_mg_l": 25,
                          "hardness_mg_l_caco3": 253, "sulfate_mg_l": 300, "chloride_mg_l": 1100, "sodium_mg_l": 750,
                          "silica_mg_l": 15, "sdi": 2.5, "turbidity_ntu": 0.2, "oxidant_exposure": "none",
                          "pretreatment": ["Cartridge filtration", "Antiscalant"]},
        },
    },
    {
        "key": "industrial",
        "title": "Industrial reuse (incomplete analysis)",
        "description": "Secondary effluent reuse with only basic data — demonstrates the insufficient-evidence pathway.",
        "inputs": {
            "application": "industrial", "feed_tds_mg_l": 3200, "feed_temperature_c": 28, "available_pressure_bar": 20,
            "permeate_flow_m3d": 800, "recovery_pct": 75, "priority": "balanced",
            "chemistry": {"toc_mg_l": 12, "oxidant_exposure": "unknown"},
        },
    },
]


def _new_token() -> str:
    return secrets.token_urlsafe(24)


@router.get("/health")
def health():
    return {"status": "ok", "engine_version": ENGINE_VERSION}


@router.get("/catalog/summary")
def catalog_summary(db: Session = Depends(get_db)):
    membranes = db.scalars(select(Membrane).where(Membrane.archived.is_(False))).all()
    by_cat: dict[str, int] = {}
    for m in membranes:
        by_cat[m.category] = by_cat.get(m.category, 0) + 1
    manufacturers = sorted({m.manufacturer.split(" (")[0] for m in membranes})
    return {
        "membranes": len(membranes),
        "verified_datasheets": sum(1 for m in membranes if m.verification_status == "verified"),
        "sources": db.scalar(select(func.count(ResearchSource.id))),
        "by_category": by_cat,
        "manufacturers": manufacturers,
    }


@router.get("/demo-examples")
def demo_examples():
    return DEMO_EXAMPLES


def _run(db: Session, inp: AssessmentInput) -> tuple[dict, dict]:
    sources = load_sources(db)
    result = assess(inp, load_active_membranes(db), sources)
    return result, sources


@router.post("/assessments", status_code=201)
def create_assessment(inp: AssessmentInput, db: Session = Depends(get_db)):
    result, _ = _run(db, inp)
    rec = result.get("recommended")
    sub = ClientSubmission(
        public_token=_new_token(), client_name=inp.client.name, client_organization=inp.client.organization,
        client_email=inp.client.email, project_name=inp.client.project_name, application=inp.application,
        inputs=inp.model_dump(), result=result, outcome=result["outcome"],
        recommended_membrane=rec["name"] if rec else None, warnings=result["warnings"], assumptions=result["assumptions"],
        evidence_refs=[s["id"] for s in result["sources"]], engine_version=ENGINE_VERSION,
    )
    db.add(sub)
    db.commit()
    return {"reference": sub.public_token, "created_at": sub.created_at.isoformat(), "inputs": sub.inputs,
            "result": client_view(result)}


def _get_by_token(db: Session, token: str) -> ClientSubmission:
    if not token or len(token) > 64:
        raise HTTPException(404, "Assessment not found")
    sub = db.scalar(select(ClientSubmission).where(ClientSubmission.public_token == token))
    if sub is None:
        raise HTTPException(404, "Assessment not found")
    return sub


@router.get("/assessments/{token}")
def get_assessment(token: str, db: Session = Depends(get_db)):
    sub = _get_by_token(db, token)
    return {"reference": sub.public_token, "created_at": sub.created_at.isoformat(), "inputs": sub.inputs,
            "result": client_view(sub.result)}


def report_response(sub: ClientSubmission, sources: dict, include_appendix: bool = True) -> Response:
    pdf = build_report({"inputs": sub.inputs, "created_at": sub.created_at, "reference": sub.public_token[:10].upper()},
                       sub.result, sources, include_appendix=include_appendix)
    name = f"RO-recommendation-{sub.public_token[:8]}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/assessments/{token}/report.pdf")
def assessment_report(token: str, appendix: bool = True, db: Session = Depends(get_db)):
    sub = _get_by_token(db, token)
    return report_response(sub, load_sources(db), include_appendix=appendix)
