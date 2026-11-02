"""Fixture provider. Unknown contracts fail. This adapter never invents a live memo."""

from __future__ import annotations

from halo.models.gateway import GenerateRequest, ModelGateway, ProviderResult

# Contract ids the fixture catalog is willing to validate. Bodies are supplied by tests
# or by an explicit evidence bundle reference already stored in the product database.
KNOWN_CONTRACTS = {
    "xavier.scorecard.v1",
    "ainge.report.v1",
    "mutombo.independent.v1",
    "scout.shortlist.v1",
    "gm.brief.v1",
}


class FakeModelGateway(ModelGateway):
    def __init__(self, catalog: dict[str, dict] | None = None) -> None:
        self.catalog = catalog or {}

    def generate(self, request: GenerateRequest) -> ProviderResult:
        if request.contract_id not in KNOWN_CONTRACTS:
            return ProviderResult(
                status="unsupported_schema",
                detail=f"{request.contract_id} is not a known contract",
            )
        output = self.catalog.get(request.contract_id)
        if output is None:
            return ProviderResult(
                status="invalid_output",
                detail="fake provider has no fixture body for this contract",
            )
        return ProviderResult(status="validated_candidate", output=output, usage_known=True)
