"""Typed agent contracts. A model cannot add fields or fill a score the evidence does not support."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Finding(StrictModel):
    statement: str
    kind: Literal["observation", "company_claim", "opinion", "inference"]
    materiality: Literal["material", "supporting"]
    evidence_ids: list[UUID]
    confidence: Literal["low", "medium", "high", "insufficient"]
    confidence_reason: str
    limitations: list[str]
    validation_question: str | None

    @model_validator(mode="after")
    def evidence_rules(self) -> Finding:
        factual = self.kind in {"observation", "company_claim"}
        if self.materiality == "material" and factual and not self.evidence_ids:
            raise ValueError("a material factual finding requires evidence")
        if self.kind == "inference" and not self.evidence_ids and not self.validation_question:
            raise ValueError("an unsupported inference requires a validation question")
        return self


class AgentOutput(StrictModel):
    summary: str
    findings: list[Finding]
    missing_evidence: list[str]
    human_questions: list[str]
    proposed_actions: list[str]
    limitations: list[str]


class LensAssessment(StrictModel):
    lens: Literal["CX", "EX", "BX", "PX"]
    score: int | None = Field(default=None, ge=1, le=5)
    status: Literal["assessed", "insufficient_evidence", "not_in_scope"]
    confidence: Literal["low", "medium", "high", "insufficient"]
    confidence_reason: str
    evidence_ids: list[UUID]
    sample_summary: str
    observed_period: str | None
    limitations: list[str]
    rubric_criterion: str | None = None

    @model_validator(mode="after")
    def score_rules(self) -> LensAssessment:
        if self.status == "assessed":
            if self.score is None or not self.evidence_ids or not self.rubric_criterion:
                raise ValueError("an assessed lens requires a score, evidence, and rubric criterion")
            if not self.confidence_reason:
                raise ValueError("an assessed lens requires a rationale")
        elif self.score is not None:
            raise ValueError("an unscored lens requires a null score")
        return self


class XavierScorecard(AgentOutput):
    lenses: list[LensAssessment]
    claim_gaps: list[dict[str, str]]

    @model_validator(mode="after")
    def four_lenses(self) -> XavierScorecard:
        found = [item.lens for item in self.lenses]
        if found != ["CX", "EX", "BX", "PX"]:
            raise ValueError("Xavier requires CX, EX, BX, and PX in that order and no overall score")
        return self


class ValueObservation(StrictModel):
    metric: str
    value: Decimal | None
    unit: str
    period: str
    classification: Literal["observed", "estimated", "verified", "unverified"]
    method: str
    evidence_ids: list[UUID]
    limitations: list[str]


class ConcernDraft(StrictModel):
    question: str
    severity: Literal["critical", "material", "question"]
    evidence_ids: list[UUID]
    evidence_gap: str | None
    suggested_human_role: str
    blocking_recommendation: bool
