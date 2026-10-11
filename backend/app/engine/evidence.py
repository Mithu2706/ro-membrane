"""Database-independent view of a membrane's evidence.

``resolve_parameters`` picks one value per parameter from possibly several
specification rows, preferring manufacturer ratings and verified sources, and
records conflicts instead of silently averaging or discarding them.
Experimental observations are never used as ratings.
"""
from __future__ import annotations

from dataclasses import dataclass, field

VERIFICATION_RANK = {"verified": 3, "report-extracted": 2, "unverified": 1, "disputed": 0}
RATING_EVIDENCE = {"manufacturer-rated"}


@dataclass
class ParamValue:
    parameter: str
    value: float | None
    unit: str
    evidence_type: str
    verification_status: str
    source_id: int | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_text: str | None = None
    test_conditions: str | None = None
    spec_id: int | None = None
    notes: str | None = None

    @property
    def numeric(self) -> float | None:
        """Single number for calculation; ranges resolve to their conservative end only via helpers."""
        return self.value

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class MembraneEvidence:
    id: int
    manufacturer: str
    model: str
    category: str
    intended_applications: list[str]
    element_size: str | None = None
    verification_status: str = "unverified"
    notes: str | None = None
    feed_limitations: str | None = None
    params: dict[str, ParamValue] = field(default_factory=dict)
    conflicts: dict[str, list[ParamValue]] = field(default_factory=dict)
    observations: list[dict] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.manufacturer} {self.model}"

    def get(self, parameter: str) -> ParamValue | None:
        return self.params.get(parameter)

    def num(self, parameter: str) -> float | None:
        p = self.params.get(parameter)
        return p.value if p is not None else None

    def num_low(self, parameter: str) -> float | None:
        """Value, or the lower bound of a stated range (conservative for rejection)."""
        p = self.params.get(parameter)
        if p is None:
            return None
        return p.value if p.value is not None else p.value_min

    def source_ids(self) -> set[int]:
        ids = {p.source_id for p in self.params.values() if p.source_id}
        ids |= {o["source_id"] for o in self.observations if o.get("source_id")}
        return ids


def _value_key(p: ParamValue) -> tuple:
    return (p.value, p.value_min, p.value_max)


def resolve_parameters(rows: list[ParamValue]) -> tuple[dict[str, ParamValue], dict[str, list[ParamValue]]]:
    """Choose one manufacturer-rated value per parameter.

    * Only manufacturer ratings are used: calculated / estimated / experimental
      values never satisfy an operating limit or rating.
    * Disputed rows are never used, even if they are the only row (the
      parameter is then treated as missing).
    * Among the rest, the best-verified row wins; differing values are recorded
      as conflicts (see ``is_ambiguous_conflict``).
    """
    by_param: dict[str, list[ParamValue]] = {}
    for r in rows:
        if r.evidence_type not in RATING_EVIDENCE:
            continue
        by_param.setdefault(r.parameter, []).append(r)

    chosen: dict[str, ParamValue] = {}
    conflicts: dict[str, list[ParamValue]] = {}
    for param, cands in by_param.items():
        usable = [c for c in cands if c.verification_status != "disputed"]
        if usable:
            usable.sort(key=lambda c: VERIFICATION_RANK.get(c.verification_status, 0), reverse=True)
            chosen[param] = usable[0]
        if len({_value_key(c) for c in cands}) > 1:
            conflicts[param] = cands
    return chosen, conflicts


def is_ambiguous_conflict(cands: list[ParamValue]) -> bool:
    """True when the best-verified, non-disputed rows disagree, so no single value can be preferred."""
    usable = [c for c in cands if c.verification_status != "disputed"]
    if not usable:
        return False
    top = max(VERIFICATION_RANK.get(c.verification_status, 0) for c in usable)
    best = [c for c in usable if VERIFICATION_RANK.get(c.verification_status, 0) == top]
    return len({_value_key(c) for c in best}) > 1
