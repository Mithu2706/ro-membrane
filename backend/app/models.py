"""ORM entities.

Manufacturer ratings (``MembraneSpecification``) and experimental / pilot / plant
observations (``ExperimentalObservation``) are deliberately separate tables so the
two kinds of evidence can never be mixed up. Every numeric value carries its unit,
source, evidence type, original test conditions and verification status. Missing
values are simply absent (no row) or NULL - never zero or "unlimited".
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Controlled vocabularies -------------------------------------------------------

EVIDENCE_TYPES = (
    "manufacturer-rated",  # datasheet / manufacturer specification
    "laboratory-experimental",  # lab cross-flow / coupon / small spiral tests
    "pilot-plant",  # pilot or full-scale plant observation
    "calculated",  # derived by this software from stored data
    "estimated",  # model estimate or assumption
)

VERIFICATION_STATUSES = (
    "verified",  # checked against the original document text
    "report-extracted",  # taken from the supplied review report; original not yet checked
    "unverified",  # entered but not yet checked
    "disputed",  # conflicts with another source; needs review
)

MEMBRANE_CATEGORIES = (
    "BWRO",
    "BWRO-low-energy",
    "BWRO-fouling-resistant",
    "BWRO-high-rejection",
    "SWRO",
    "SWRO-low-energy",
    "Industrial",
)

SOURCE_TYPES = ("manufacturer-datasheet", "peer-reviewed", "review-report", "other")


class ResearchSource(Base):
    __tablename__ = "research_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    authors: Mapped[str | None] = mapped_column(String(500), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40))
    publisher: Mapped[str | None] = mapped_column(String(300), nullable=True)
    page_table: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Membrane(Base):
    __tablename__ = "membranes"
    __table_args__ = (UniqueConstraint("manufacturer", "model", name="uq_membrane_model"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manufacturer: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    intended_applications: Mapped[list] = mapped_column(JSON, default=list)  # e.g. ["bwro", "second_pass"]
    element_size: Mapped[str | None] = mapped_column(String(60), nullable=True)
    feed_limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    specifications: Mapped[list[MembraneSpecification]] = relationship(
        back_populates="membrane", cascade="all, delete-orphan", order_by="MembraneSpecification.id"
    )
    observations: Mapped[list[ExperimentalObservation]] = relationship(
        back_populates="membrane", cascade="all, delete-orphan", order_by="ExperimentalObservation.id"
    )

    @property
    def display_name(self) -> str:
        return f"{self.manufacturer} {self.model}"


class MembraneSpecification(Base):
    """One rated / calculated parameter value with full provenance."""

    __tablename__ = "membrane_specifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    membrane_id: Mapped[int] = mapped_column(ForeignKey("membranes.id", ondelete="CASCADE"), index=True)
    parameter: Mapped[str] = mapped_column(String(60), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(200), nullable=True)  # verbatim e.g. "600 psig (41 bar)"
    unit: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("research_sources.id"), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(40))
    test_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    membrane: Mapped[Membrane] = relationship(back_populates="specifications")
    source: Mapped[ResearchSource | None] = relationship()


class ExperimentalObservation(Base):
    __tablename__ = "experimental_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    membrane_id: Mapped[int] = mapped_column(ForeignKey("membranes.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(40))  # laboratory-experimental | pilot-plant
    feed_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    feed_salinity_mg_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    feed_salinity_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pressure_bar: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    flow_or_flux_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    salt_rejection_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    performance_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    permeate_concentration_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    test_method: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("research_sources.id"), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="report-extracted")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    membrane: Mapped[Membrane] = relationship(back_populates="observations")
    source: Mapped[ResearchSource | None] = relationship()


class ClientSubmission(Base):
    __tablename__ = "client_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client_organization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    client_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    project_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    application: Mapped[str] = mapped_column(String(40), index=True)
    inputs: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    outcome: Mapped[str] = mapped_column(String(40), index=True)  # recommended | no_supported_recommendation
    recommended_membrane: Mapped[str | None] = mapped_column(String(200), nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    engine_version: Mapped[str] = mapped_column(String(20))


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(120))
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    username: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    description: Mapped[str] = mapped_column(String(300))
