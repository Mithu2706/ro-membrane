"""Validated client input schema (canonical units).

Optional fields default to ``None`` meaning "not supplied"; ``0`` is a genuine
measured zero and is treated differently from missing data.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Application = Literal["bwro", "swro", "industrial", "second_pass", "other"]
Priority = Literal["quality", "productivity", "low_pressure", "balanced"]
Oxidant = Literal["none", "dechlorinated", "free_chlorine_present", "chloramine", "unknown"]
InputOrigin = Literal["client", "demo"]

APPLICATION_LABELS = {
    "bwro": "Brackish-water RO",
    "swro": "Seawater RO",
    "industrial": "Industrial wastewater / reuse",
    "second_pass": "Second-pass RO",
    "other": "Other / specialised",
}
PRIORITY_LABELS = {
    "quality": "Permeate quality",
    "productivity": "Productivity",
    "low_pressure": "Lower operating pressure",
    "balanced": "Balanced performance",
}


class Chemistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ph: float | None = Field(None, ge=0, le=14)
    alkalinity_mg_l_caco3: float | None = Field(None, ge=0)
    hardness_mg_l_caco3: float | None = Field(None, ge=0)
    calcium_mg_l: float | None = Field(None, ge=0)
    magnesium_mg_l: float | None = Field(None, ge=0)
    sulfate_mg_l: float | None = Field(None, ge=0)
    chloride_mg_l: float | None = Field(None, ge=0)
    sodium_mg_l: float | None = Field(None, ge=0)
    silica_mg_l: float | None = Field(None, ge=0)
    boron_mg_l: float | None = Field(None, ge=0)
    sdi: float | None = Field(None, ge=0, le=20)
    turbidity_ntu: float | None = Field(None, ge=0)
    toc_mg_l: float | None = Field(None, ge=0)
    cod_mg_l: float | None = Field(None, ge=0)
    oxidant_exposure: Oxidant = "unknown"
    free_chlorine_mg_l: float | None = Field(None, ge=0)
    pretreatment: list[str] = Field(default_factory=list)
    pretreatment_notes: str | None = Field(None, max_length=1000)


class ClientInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, max_length=200)
    organization: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=200)
    project_name: str | None = Field(None, max_length=200)


class AssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application: Application
    feed_tds_mg_l: float = Field(..., gt=0, le=100000, description="Feed TDS or salinity, mg/L")
    feed_temperature_c: float = Field(..., gt=0, le=60)
    available_pressure_bar: float = Field(..., gt=0, le=120)
    permeate_flow_m3d: float = Field(..., gt=0, le=1_000_000)
    recovery_pct: float = Field(..., gt=0, lt=100)
    target_permeate_tds_mg_l: float | None = Field(None, ge=0)
    target_boron_mg_l: float | None = Field(None, ge=0)
    feed_flow_limit_m3d: float | None = Field(None, gt=0)
    design_flux_lmh: float | None = Field(None, gt=0, le=60)
    pressure_loss_allowance_bar: float | None = Field(None, ge=0, le=30)
    priority: Priority = "balanced"
    # "demo" when the values were loaded from a built-in demonstration example (possibly edited);
    # such results must never be presented as an assessment of a measured water analysis.
    input_origin: InputOrigin = "client"
    chemistry: Chemistry = Field(default_factory=Chemistry)
    client: ClientInfo = Field(default_factory=ClientInfo)

    @field_validator("recovery_pct")
    @classmethod
    def _recovery(cls, v: float) -> float:
        if not 0 < v < 100:
            raise ValueError("Recovery must be greater than 0% and below 100%")
        return v

    @property
    def recovery(self) -> float:
        return self.recovery_pct / 100.0
