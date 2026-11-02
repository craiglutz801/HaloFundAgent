"""Model gateway. Only a validated candidate is eligible for domain checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

ResultStatus = Literal[
    "validated_candidate",
    "refusal",
    "timeout_usage_unknown",
    "rate_limited",
    "unsupported_schema",
    "truncated",
    "invalid_output",
]


@dataclass
class ProviderResult:
    status: ResultStatus
    output: dict[str, Any] | None = None
    detail: str = ""
    usage_known: bool = False
    tokens_in: int | None = None
    tokens_out: int | None = None


@dataclass
class GenerateRequest:
    contract_id: str
    schema_version: str
    prompt_ref: str
    evidence_bundle_ref: str
    tool_registry_ref: str
    budget_ref: str
    extra: dict[str, Any] = field(default_factory=dict)


class ModelGateway(Protocol):
    def generate(self, request: GenerateRequest) -> ProviderResult: ...
