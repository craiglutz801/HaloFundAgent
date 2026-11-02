"""Anthropic adapter. Unconfigured calls return a capability error and no prose."""

from __future__ import annotations

from halo.errors import CapabilityError
from halo.models.gateway import GenerateRequest, ModelGateway, ProviderResult
from halo.settings import Settings


class AnthropicAdapter(ModelGateway):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, request: GenerateRequest) -> ProviderResult:
        del request
        if self.settings.halo_mode != "live" or not self.settings.model_provider_key:
            raise CapabilityError(
                "Anthropic is not configured for this process. No model output was produced."
            )
        raise CapabilityError(
            "The Anthropic call is not enabled until a reviewed live provider configuration is present."
        )
