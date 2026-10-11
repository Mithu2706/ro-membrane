"""Technical recommendation report (PDF) built with ReportLab.

The client dashboard never shows equations; they appear here only in the
optional technical appendix.
"""
from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..engine.inputs import APPLICATION_LABELS, PRIORITY_LABELS
from ..engine.recommend import RATED_KEYS, methodology

MIDNIGHT = colors.HexColor("#102A2A")
GRAPHITE = colors.HexColor("#202927")
IVORY = colors.HexColor("#F5F2EA")
TEAL = colors.HexColor("#2D7771")
BRASS = colors.HexColor("#C29B58")
WARN = colors.HexColor("#C4552B")
RULE = colors.HexColor("#D9D3C4")

def _vera(name: str) -> str:
    """Bitstream Vera fonts bundled with ReportLab: always present, so servers without system fonts
    (e.g. serverless Linux) still get Unicode text. Vera lacks only the Greek capital delta."""
    import os

    import reportlab

    return os.path.join(os.path.dirname(reportlab.__file__), "fonts", name)


_FONT_CANDIDATES = {
    "Body": ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", _vera("Vera.ttf")],
    "Body-Bold": ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", _vera("VeraBd.ttf")],
    "Body-Italic": ["C:/Windows/Fonts/ariali.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf", _vera("VeraIt.ttf")],
    "Serif-Bold": ["C:/Windows/Fonts/georgiab.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", _vera("VeraBd.ttf")],
    "Mono": ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", _vera("Vera.ttf")],
}
VERA_IN_USE = False
_FALLBACK = {"Body": "Helvetica", "Body-Bold": "Helvetica-Bold", "Body-Italic": "Helvetica-Oblique",
             "Serif-Bold": "Times-Bold", "Mono": "Courier"}
FONTS: dict[str, str] = {}
UNICODE_OK = True


def _register_fonts() -> None:
    """Use Unicode TrueType fonts when available; otherwise fall back to Type1 fonts with ASCII transliteration."""
    global UNICODE_OK, VERA_IN_USE
    if FONTS:
        return
    from pathlib import Path

    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for name, paths in _FONT_CANDIDATES.items():
        path = next((p for p in paths if Path(p).exists()), None)
        if path:
            try:
                pdfmetrics.registerFont(TTFont(f"RO-{name}", path))
                FONTS[name] = f"RO-{name}"
                VERA_IN_USE = VERA_IN_USE or "Vera" in Path(path).name
                continue
            except Exception:  # pragma: no cover - font file unreadable
                pass
        FONTS[name] = _FALLBACK[name]
        UNICODE_OK = False
    if FONTS["Body"].startswith("RO-"):
        addMapping(FONTS["Body"], 0, 0, FONTS["Body"])
        addMapping(FONTS["Body"], 1, 0, FONTS["Body-Bold"])
        addMapping(FONTS["Body"], 0, 1, FONTS["Body-Italic"])
        addMapping(FONTS["Body"], 1, 1, FONTS["Body-Bold"])


_ASCII = str.maketrans({"π": "pi", "≈": "~", "−": "-", "–": "-", "—": "-", "⌈": "ceil(", "⌉": ")", "̄": "", "·": "*",
                        "≤": "<=", "≥": ">=", "×": "x", "÷": "/", "₃": "3", "Δ": "d", "→": "->", "…": "..."})

EVIDENCE_SHORT = {"manufacturer-rated": "Mfr. rating", "laboratory-experimental": "Lab test", "pilot-plant": "Pilot/plant",
                  "calculated": "Calculated", "estimated": "Estimated"}

STATUS_COLORS = {"suitable": TEAL, "conditional": BRASS, "insufficient_evidence": colors.HexColor("#6B7472"),
                 "unsuitable": WARN}


def _styles():
    _register_fonts()
    ss = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=ss["Normal"], fontName=FONTS["Body"], fontSize=9, leading=12.5, textColor=GRAPHITE)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=7.5, leading=10, textColor=colors.HexColor("#4A5553")),
        "h1": ParagraphStyle("h1", parent=base, fontName=FONTS["Serif-Bold"], fontSize=22, leading=26, textColor=MIDNIGHT),
        "h2": ParagraphStyle("h2", parent=base, fontName=FONTS["Serif-Bold"], fontSize=14, leading=18, textColor=MIDNIGHT,
                             spaceBefore=10, spaceAfter=4),
        "h3": ParagraphStyle("h3", parent=base, fontName=FONTS["Body-Bold"], fontSize=9.5, leading=13, textColor=TEAL,
                             spaceBefore=6, spaceAfter=2),
        "eyebrow": ParagraphStyle("eyebrow", parent=base, fontName=FONTS["Body-Bold"], fontSize=7.5, textColor=BRASS,
                                  alignment=TA_LEFT),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8, leading=10.5),
        "cellb": ParagraphStyle("cellb", parent=base, fontSize=8, leading=10.5, fontName=FONTS["Body-Bold"]),
        "mono": ParagraphStyle("mono", parent=base, fontName=FONTS["Mono"], fontSize=8, leading=11),
    }


def _esc(v) -> str:
    s = "" if v is None else str(v)
    if not UNICODE_OK:
        s = s.translate(_ASCII).encode("latin-1", "replace").decode("latin-1")
    elif VERA_IN_USE:
        s = s.replace("Δ", "d")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _num(v, nd=1, unit=""):
    if v is None:
        return "Not reported"
    return f"{v:,.{nd}f}{(' ' + unit) if unit else ''}"


def _table(rows, widths, st, header=True):
    data = [[Paragraph(_esc(c) if not isinstance(c, Paragraph) else c.text, st["cellb" if (header and i == 0) else "cell"])
             if not isinstance(c, Paragraph) else c for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), IVORY), ("LINEBELOW", (0, 0), (-1, 0), 0.8, MIDNIGHT)]
    t.setStyle(TableStyle(style))
    return t


def _page(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(MIDNIGHT)
    canvas.rect(0, h - 10 * mm, w, 10 * mm, stroke=0, fill=1)
    canvas.setFillColor(IVORY)
    canvas.setFont(FONTS["Body-Bold"], 7.5)
    canvas.drawString(18 * mm, h - 6.5 * mm, "OSMORA  ·  RO MEMBRANE SELECTION — PRELIMINARY TECHNICAL REPORT")
    canvas.setFillColor(colors.HexColor("#6B7472"))
    canvas.setFont(FONTS["Body"], 7)
    canvas.drawString(18 * mm, 10 * mm, "Preliminary design support only. Not a substitute for manufacturer projections, pilot testing or detailed engineering.")
    canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_report(submission: dict, result: dict, sources: dict[int, dict], include_appendix: bool = True) -> bytes:
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm, title="RO Membrane Recommendation Report", author="Osmora")
    inp = submission["inputs"]
    ch = inp.get("chemistry") or {}
    client = inp.get("client") or {}
    story = []
    W = doc.width

    created = submission.get("created_at")
    created_s = created.strftime("%d %B %Y, %H:%M UTC") if isinstance(created, datetime) else str(created or "")
    story += [
        Paragraph("TECHNICAL RECOMMENDATION REPORT", st["eyebrow"]), Spacer(1, 3),
        Paragraph(_esc(client.get("project_name") or "RO membrane preliminary selection"), st["h1"]), Spacer(1, 4),
        Paragraph(f"Reference {_esc(submission.get('reference'))} · {created_s} · Engine {_esc(result.get('engine_version'))}", st["small"]),
        Spacer(1, 8),
    ]
    banner = Table([[Paragraph(
        "<b>Preliminary design support.</b> Estimates are indicative, derived from manufacturer ratings and published "
        "evidence under stated assumptions. They are not guaranteed to match any real installation and do not replace "
        "detailed engineering validation.", st["cell"])]], colWidths=[W])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), IVORY), ("LINEBEFORE", (0, 0), (0, -1), 2.5, BRASS),
                                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [banner, Spacer(1, 6)]
    demo = (result.get("input_origin") or inp.get("input_origin")) == "demo"
    if demo:
        demo_banner = Table([[Paragraph(
            "<b>Demonstration data.</b> This report was produced from a built-in demonstration example (possibly edited), "
            "not from a measured water analysis. It must not be used for a real project.", st["cell"])]], colWidths=[W])
        demo_banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9EAE3")),
                                         ("LINEBEFORE", (0, 0), (0, -1), 2.5, WARN), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                         ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story += [demo_banner, Spacer(1, 6)]

    # 1. Requirements
    story.append(Paragraph("1. Client requirements", st["h2"]))
    if any(client.get(k) for k in ("name", "organization")):
        story.append(Paragraph(f"Prepared for {_esc(client.get('name') or '')} {('— ' + _esc(client.get('organization'))) if client.get('organization') else ''}", st["base"]))
    req = [
        ["Parameter", "Value", "Parameter", "Value"],
        ["Application", APPLICATION_LABELS.get(inp["application"], inp["application"]), "Priority", PRIORITY_LABELS.get(inp.get("priority", "balanced"))],
        ["Feed TDS", _num(inp["feed_tds_mg_l"], 0, "mg/L"), "Feed temperature", _num(inp["feed_temperature_c"], 1, "°C")],
        ["Available pressure", _num(inp["available_pressure_bar"], 1, "bar"), "Target permeate flow", _num(inp["permeate_flow_m3d"], 0, "m³/day")],
        ["Target recovery", _num(inp["recovery_pct"], 1, "%"), "Target permeate TDS", _num(inp.get("target_permeate_tds_mg_l"), 0, "mg/L") if inp.get("target_permeate_tds_mg_l") is not None else "Not specified"],
        ["Design flux", _num(inp.get("design_flux_lmh"), 1, "LMH") if inp.get("design_flux_lmh") else "Not specified",
         "Feed-flow limit", _num(inp.get("feed_flow_limit_m3d"), 0, "m³/day") if inp.get("feed_flow_limit_m3d") else "Not specified"],
        ["Data origin", "Demonstration example" if demo else "Client-supplied", "Pressure-loss allowance",
         _num(inp.get("pressure_loss_allowance_bar"), 1, "bar") if inp.get("pressure_loss_allowance_bar") is not None else "Not included"],
    ]
    story.append(_table(req, [W * 0.2, W * 0.3, W * 0.2, W * 0.3], st))
    chem_rows = [["Water analysis", "Value"]]
    labels = [("ph", "pH", ""), ("alkalinity_mg_l_caco3", "Alkalinity", "mg/L as CaCO3"), ("hardness_mg_l_caco3", "Total hardness", "mg/L as CaCO3"),
              ("calcium_mg_l", "Calcium", "mg/L"), ("magnesium_mg_l", "Magnesium", "mg/L"), ("sulfate_mg_l", "Sulfate", "mg/L"),
              ("chloride_mg_l", "Chloride", "mg/L"), ("sodium_mg_l", "Sodium", "mg/L"), ("silica_mg_l", "Silica", "mg/L"),
              ("boron_mg_l", "Boron", "mg/L"), ("sdi", "SDI", ""), ("turbidity_ntu", "Turbidity", "NTU"), ("toc_mg_l", "TOC", "mg/L"),
              ("cod_mg_l", "COD", "mg/L")]
    for k, lab, unit in labels:
        v = ch.get(k)
        chem_rows.append([lab, "Not provided" if v is None else f"{v:g} {unit}".strip()])
    chem_rows.append(["Oxidant exposure", str(ch.get("oxidant_exposure", "unknown")).replace("_", " ")])
    if ch.get("pretreatment"):
        chem_rows.append(["Existing pretreatment", ", ".join(ch["pretreatment"])])
    story += [Spacer(1, 4), _table(chem_rows, [W * 0.35, W * 0.65], st)]

    # 2. Outcome
    story.append(Paragraph("2. Recommendation", st["h2"]))
    story.append(Paragraph(f"<b>{_esc(result['headline'])}</b>", st["base"]))
    story.append(Paragraph(_esc(result["summary"]), st["base"]))
    if result.get("warnings"):
        story.append(Paragraph("Important considerations", st["h3"]))
        for w in result["warnings"]:
            colour = {"critical": WARN.hexval(), "caution": BRASS.hexval()}.get(w["severity"], TEAL.hexval())
            story.append(Paragraph(f"<font color='{colour}'><b>{_esc(w['severity'].upper())}</b></font> · "
                                   f"<b>{_esc(w['title'])}:</b> {_esc(w['message'])}", st["base"]))
    rec = result.get("recommended")
    if rec:
        story.append(Paragraph(f"Status: <font color='{STATUS_COLORS[rec['status']].hexval()}'><b>{_esc(rec['status_label'])}</b></font> · "
                               f"Evidence: {_esc(rec['evidence']['level'])}", st["base"]))
        if rec.get("positives"):
            story.append(Paragraph("Strengths: " + _esc("; ".join(rec["positives"])), st["base"]))
        if rec.get("concerns"):
            story.append(Paragraph("Conditions: " + _esc(" ".join(rec["concerns"])), st["base"]))
        story.append(Paragraph("Screening checks", st["h3"]))
        rows = [["Check", "Result", "Explanation"]]
        for c in rec["checks"]:
            rows.append([c["label"], c["status"].upper(), c["message"]])
        story.append(_table(rows, [W * 0.22, W * 0.12, W * 0.66], st))

        story.append(Paragraph("Reported membrane specifications", st["h3"]))
        rows = [["Parameter", "Value", "Evidence", "Verification", "Source"]]
        for key, lab in RATED_KEYS:
            p = rec["rated"].get(key)
            if p is None:
                rows.append([lab, "Not reported", "—", "—", "—"])
                continue
            val = p.get("value_text") or (_num(p["value"], 2, p["unit"]) if p["value"] is not None else
                                          f"{p.get('value_min')}–{p.get('value_max')} {p['unit']}")
            src = sources.get(p.get("source_id"), {})
            rows.append([lab, val, EVIDENCE_SHORT.get(p["evidence_type"], p["evidence_type"]), p["verification_status"],
                         (src.get("title") or "")[:70]])
        story.append(_table(rows, [W * 0.22, W * 0.2, W * 0.14, W * 0.15, W * 0.29], st))
        if rec.get("rated_test_conditions"):
            story.append(Paragraph("Rated test conditions: " + _esc(rec["rated_test_conditions"]), st["small"]))

    # 3. Alternatives
    story.append(Paragraph("3. Alternative and screened candidates", st["h2"]))
    rows = [["#", "Membrane", "Status", "Est. pressure (bar)", "Est. permeate TDS (mg/L)", "Elements", "Evidence"]]
    for c in result["candidates"]:
        e = c["estimates"]
        p = "—" if e["required_pressure_bar"] is None else f"{e['required_pressure_bar']:.0f}–{e['required_pressure_high_bar']:.0f}"
        cp = "—" if e["permeate_tds_mg_l"] is None else (f"{e['permeate_tds_mg_l']:.0f}" + (f"–{e['permeate_tds_high_mg_l']:.0f}" if e.get("permeate_tds_high_mg_l") else ""))
        n = e.get("elements_required")
        rows.append([str(c["rank"]) if c.get("rank") else "—", c["name"], c["status_label"], p, cp,
                     f"{n:,}" if n else "—", c["evidence"]["level"]])
    story.append(_table(rows, [W * 0.05, W * 0.26, W * 0.17, W * 0.12, W * 0.13, W * 0.11, W * 0.16], st))
    story.append(Paragraph("Only candidates that pass every hard constraint with sufficient evidence are ranked (#). "
                           "Element counts and pressures are membrane-level screening estimates, not a plant configuration.",
                           st["small"]))
    story.append(Paragraph("Reasons for exclusion or limited evidence", st["h3"]))
    rows = [["Membrane", "Reason"]]
    for c in result["candidates"]:
        if c["status"] in ("unsuitable", "insufficient_evidence"):
            rows.append([c["name"], c["summary"]])
    if len(rows) > 1:
        story.append(_table(rows, [W * 0.3, W * 0.7], st))

    # 4. Flow balance
    sysd = result["system"]
    fl = sysd["flow"]
    story.append(Paragraph("4. Estimated production and flow balance", st["h2"]))
    rows = [["Stream", "m³/day", "m³/h"],
            ["Permeate (product)", _num(fl["permeate_m3d"], 1), _num(fl["permeate_m3h"], 2)],
            ["Feed", _num(fl["feed_m3d"], 1), _num(fl["feed_m3h"], 2)],
            ["Concentrate", _num(fl["concentrate_m3d"], 1), _num(fl["concentrate_m3h"], 2)]]
    story.append(_table(rows, [W * 0.4, W * 0.3, W * 0.3], st))
    story.append(Paragraph(
        f"Recovery {fl['recovery_pct']:g}%. Idealised concentration factor {sysd['concentration_factor']:.2f}; idealised "
        f"concentrate TDS ≈ {sysd['concentrate_tds_ideal_mg_l']:,.0f} mg/L (assumes complete salt rejection, no precipitation).",
        st["base"]))
    story.append(Paragraph("Pressure and recovery assessment", st["h3"]))
    for c in sysd["checks"]:
        story.append(Paragraph(f"<b>{_esc(c['label'])}</b> — {c['status'].upper()}: {_esc(c['message'])}", st["base"]))
    if rec and rec["estimates"]["required_pressure_bar"] is not None:
        e = rec["estimates"]
        basis = (rec.get("technical") or {}).get("pressure_basis_flux_lmh") or inp.get("design_flux_lmh")
        story.append(Paragraph(
            f"Indicative feed pressure for {_esc(rec['name'])}: {e['required_pressure_bar']:.1f}–{e['required_pressure_high_bar']:.1f} bar "
            f"at an average flux of {basis:.1f} LMH (design flux {inp.get('design_flux_lmh')} LMH, element count rounded up); "
            f"indicative element count {e.get('elements_required') or 'not estimated'}.", st["base"]))

    # 5. Chemistry
    story.append(Paragraph("5. Water-chemistry warnings", st["h2"]))
    story.append(Paragraph(f"Analysis completeness: {result['chemistry']['completeness']}.", st["base"]))
    rows = [["Topic", "Status", "Assessment"]]
    for i in result["chemistry"]["items"]:
        rows.append([i["label"], i["status"].replace("_", " "), i["message"]])
    if len(rows) > 1:
        story.append(_table(rows, [W * 0.22, W * 0.13, W * 0.65], st))

    # 6. Assumptions
    story.append(Paragraph("6. Assumptions and uncertainty", st["h2"]))
    for a in result["assumptions"]:
        story.append(Paragraph("• " + _esc(a), st["base"]))
    story.append(Paragraph("Not modelled in this version", st["h3"]))
    for a in result["unavailable"]:
        story.append(Paragraph("• " + _esc(a), st["base"]))

    # 7. Sources
    story.append(Paragraph("7. Sources", st["h2"]))
    for s in result.get("sources", []):
        link = s.get("url") or (f"https://doi.org/{s['doi']}" if s.get("doi") else "")
        story.append(Paragraph(
            f"[{s['id']}] {_esc(s.get('authors') or '')} {('(' + str(s['year']) + ')') if s.get('year') else ''} "
            f"<i>{_esc(s['title'])}</i>. {_esc(s.get('publisher') or '')}. {_esc(link)} "
            f"— {_esc(s['source_type'])}, {_esc(s['verification_status'])}.", st["small"]))

    # 8. Statement
    story.append(Paragraph("8. Statement of limitations", st["h2"]))
    for l in result["limitations"]:
        story.append(Paragraph("• " + _esc(l), st["base"]))

    if include_appendix:
        story.append(PageBreak())
        story.append(Paragraph("Technical appendix — calculation methodology", st["h2"]))
        for m in methodology():
            story.append(KeepTogether([Paragraph(_esc(m["title"]), st["h3"]), Paragraph(_esc(m["equation"]), st["mono"]),
                                       Paragraph(_esc(m["note"]), st["small"])]))
        tech = result.get("technical") or {}
        story.append(Paragraph("System intermediate values", st["h3"]))
        rows = [["Quantity", "Value"],
                ["Feed osmotic pressure (ideal, NaCl-equivalent)", _num(tech.get("osmotic_feed_bar"), 2, "bar")],
                ["Average feed-side osmotic pressure", _num(tech.get("osmotic_avg_bar"), 2, "bar")],
                ["Concentrate osmotic pressure (idealised)", _num(tech.get("osmotic_concentrate_bar"), 2, "bar")],
                ["Average feed-side TDS", _num(tech.get("avg_feed_side_tds_mg_l"), 0, "mg/L")],
                ["Flow-balance closure error", f"{tech.get('flow_closure_error_m3d', 0):.2e} m³/d"]]
        story.append(_table(rows, [W * 0.6, W * 0.4], st))
        if rec and rec.get("technical"):
            t = rec["technical"]
            story.append(Paragraph(f"Candidate intermediate values — {_esc(rec['name'])}", st["h3"]))
            rows = [["Quantity", "Value"]]
            for k, lab, nd, unit in [("rated_flux_lmh", "Rated flux", 2, "LMH"), ("test_osmotic_avg_bar", "Average test osmotic pressure", 2, "bar"),
                                     ("test_ndp_bar", "Test net driving pressure", 2, "bar"),
                                     ("apparent_permeance_lmh_bar", "Apparent permeance A (calculated)", 3, "LMH/bar"),
                                     ("required_pressure_bar", "Indicative feed pressure", 1, "bar"),
                                     ("required_pressure_high_bar", "Indicative feed pressure (−15% element flow)", 1, "bar"),
                                     ("permeate_estimate_mg_l", "Permeate TDS estimate", 1, "mg/L"),
                                     ("permeate_per_element_m3d", "Permeate per element at design flux", 2, "m³/d")]:
                if t.get(k) is not None:
                    rows.append([lab, _num(t[k], nd, unit)])
            story.append(_table(rows, [W * 0.6, W * 0.4], st))
            rows = [["Check", "Technical detail"]]
            for c in rec["checks"]:
                if c.get("detail"):
                    rows.append([c["label"], c["detail"]])
            story.append(_table(rows, [W * 0.3, W * 0.7], st))

    doc.build(story, onFirstPage=_page, onLaterPages=_page)
    return buf.getvalue()
