"""Admin request schemas with vocabulary validation."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .catalog import PARAMETERS
from .models import EVIDENCE_TYPES, MEMBRANE_CATEGORIES, SOURCE_TYPES, VERIFICATION_STATUSES

APPLICATIONS = ("bwro", "swro", "industrial", "second_pass", "other")


def _in(value, allowed, name):
    if value not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    return value


class LoginIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=1, max_length=256)


class MembraneIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manufacturer: str = Field(..., min_length=1, max_length=120)
    model: str = Field(..., min_length=1, max_length=120)
    category: str
    intended_applications: list[str] = Field(default_factory=list)
    element_size: str | None = Field(None, max_length=60)
    feed_limitations: str | None = None
    verification_status: str = "unverified"
    notes: str | None = None

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        return _in(v, MEMBRANE_CATEGORIES, "category")

    @field_validator("verification_status")
    @classmethod
    def _ver(cls, v):
        return _in(v, VERIFICATION_STATUSES, "verification_status")

    @field_validator("intended_applications")
    @classmethod
    def _apps(cls, v):
        for a in v:
            _in(a, APPLICATIONS, "intended application")
        return v


class SpecIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter: str
    value: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_text: str | None = Field(None, max_length=200)
    unit: str | None = None
    source_id: int | None = None
    evidence_type: str
    test_conditions: str | None = None
    verification_status: str = "unverified"
    notes: str | None = None

    @field_validator("parameter")
    @classmethod
    def _param(cls, v):
        return _in(v, tuple(PARAMETERS), "parameter")

    @field_validator("evidence_type")
    @classmethod
    def _ev(cls, v):
        return _in(v, EVIDENCE_TYPES, "evidence_type")

    @field_validator("verification_status")
    @classmethod
    def _ver(cls, v):
        return _in(v, VERIFICATION_STATUSES, "verification_status")

    @model_validator(mode="after")
    def _value_and_unit(self):
        if self.value is None and self.value_min is None and self.value_max is None and not self.value_text:
            raise ValueError("Provide a value, a range or a verbatim text value")
        expected = PARAMETERS[self.parameter][1]
        if self.unit is None:
            self.unit = expected
        elif self.unit != expected:
            raise ValueError(f"Unit for {self.parameter} must be {expected} (convert before entry)")
        return self


class ObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: str
    feed_description: str | None = None
    feed_salinity_mg_l: float | None = None
    feed_salinity_text: str | None = None
    pressure_bar: float | None = None
    pressure_text: str | None = None
    temperature_c: float | None = None
    recovery_text: str | None = None
    flow_or_flux_text: str | None = None
    salt_rejection_pct: float | None = Field(None, ge=0, le=100)
    performance_text: str | None = None
    permeate_concentration_text: str | None = None
    test_method: str | None = None
    source_id: int | None = None
    verification_status: str = "unverified"
    notes: str | None = None

    @field_validator("evidence_type")
    @classmethod
    def _ev(cls, v):
        return _in(v, ("laboratory-experimental", "pilot-plant"), "evidence_type")

    @field_validator("verification_status")
    @classmethod
    def _ver(cls, v):
        return _in(v, VERIFICATION_STATUSES, "verification_status")


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=500)
    authors: str | None = None
    year: int | None = Field(None, ge=1900, le=2100)
    doi: str | None = None
    url: str | None = None
    source_type: str
    publisher: str | None = None
    page_table: str | None = None
    verification_status: str = "unverified"
    notes: str | None = None

    @field_validator("source_type")
    @classmethod
    def _st(cls, v):
        return _in(v, SOURCE_TYPES, "source_type")

    @field_validator("verification_status")
    @classmethod
    def _ver(cls, v):
        return _in(v, VERIFICATION_STATUSES, "verification_status")

    @field_validator("url")
    @classmethod
    def _url(cls, v):
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class VerifyIn(BaseModel):
    verification_status: str

    @field_validator("verification_status")
    @classmethod
    def _ver(cls, v):
        return _in(v, VERIFICATION_STATUSES, "verification_status")


class ArchiveIn(BaseModel):
    archived: bool
