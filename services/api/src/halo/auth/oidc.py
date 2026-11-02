"""Live OIDC is a provisioning dependency. Fixture mode does not contact an issuer."""

from __future__ import annotations

from halo.errors import CapabilityError
from halo.settings import Settings


def authorization_url(settings: Settings) -> str:
    if settings.halo_mode != "live" or not settings.oidc_issuer:
        raise CapabilityError(
            "OIDC is not configured. Fixture mode uses the local roster and live mode must be provisioned."
        )
    raise CapabilityError("OIDC authorization-code flow is not enabled in this build.")
