from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from halo.calculations.capacity import classification_for_capacity, estimated_capacity_hours
from halo.calculations.errors import CalculationError
from halo.calculations.health import DefinitionView, ObservationView, evaluate_health
from halo.calculations.retention import gross_revenue_retention, retention_definitions_conflict
from halo.calculations.returns import (
    apply_dilution,
    entry_ownership,
    gross_irr_or_unavailable,
    gross_moic,
    gross_proceeds,
)
from halo.calculations.runway import runway_months
from halo.errors import CapabilityError
from halo.models.fake_adapter import FakeModelGateway
from halo.models.gateway import GenerateRequest
from halo.models.openai_adapter import OpenAIAdapter
from halo.models.schemas import LensAssessment, XavierScorecard
from halo.settings import Settings, assert_fixture_reset_target


def test_live_mode_rejects_fake_provider():
    with pytest.raises(ValueError, match="MODEL_PROVIDER=fake"):
        Settings(
            halo_mode="live",
            halo_bind_host="10.0.0.4",
            database_url="postgresql+psycopg://halo_app@db/halo_live",
            migration_database_url="postgresql+psycopg://halo_migrator@db/halo_live",
            model_provider="fake",
            session_cookie_secure=True,
            session_secret="x" * 32,
            object_store="s3",
            object_bucket="halo",
            oidc_issuer="https://issuer.example",
            oidc_client_id="client",
            oidc_client_secret="secret",
        )


def test_reset_refuses_non_fixture_names():
    with pytest.raises(RuntimeError, match="fixture"):
        assert_fixture_reset_target("postgresql+psycopg://halo@db/halo", "fixture")
    with pytest.raises(RuntimeError, match="live"):
        assert_fixture_reset_target("postgresql+psycopg://halo@db/halo_live_fixture", "fixture")
    with pytest.raises(RuntimeError, match="HALO_MODE"):
        assert_fixture_reset_target("postgresql+psycopg://halo@db/halo_fixture", "live")
    assert assert_fixture_reset_target("postgresql+psycopg://halo@db/halo_fixture", "fixture") == "halo_fixture"


def test_illustrative_gross_moic_fixture():
    ownership = entry_ownership(Decimal("20000000"), Decimal("200000000"))
    diluted = apply_dilution(ownership, Decimal("0.20"))
    assert diluted == Decimal("0.080000")
    exits = [Decimal("250000000"), Decimal("625000000"), Decimal("1000000000")]
    moics = [
        gross_moic(gross_proceeds(exit_value, diluted), Decimal("20000000")) for exit_value in exits
    ]
    assert moics == [Decimal("1.00"), Decimal("2.50"), Decimal("4.00")]
    assert gross_irr_or_unavailable(cash_flow_dates_present=False) is None


def test_invalid_return_inputs():
    with pytest.raises(CalculationError):
        entry_ownership(Decimal("10"), Decimal("0"))
    with pytest.raises(CalculationError):
        entry_ownership(Decimal("-1"), Decimal("10"))


def test_retention_conflict_is_not_averaged():
    dollar = gross_revenue_retention(
        starting_arr=Decimal("1000000"), contraction=Decimal("90000"), churn=Decimal("69000")
    )
    assert dollar == Decimal("0.8410")
    assert retention_definitions_conflict(stated_rate=Decimal("0.92"), computed_rate=dollar)


def test_runway_edges():
    assert runway_months(cash=Decimal("100"), monthly_burn=Decimal("0"), cash_restriction_unknown=False) is None
    assert runway_months(cash=Decimal("100"), monthly_burn=Decimal("10"), cash_restriction_unknown=True) is None
    assert runway_months(cash=None, monthly_burn=Decimal("10"), cash_restriction_unknown=False) is None


def test_capacity_fixture_is_estimated():
    hours = estimated_capacity_hours(
        baseline_minutes=Decimal("12"), future_minutes=Decimal("8"), monthly_cases=Decimal("3000")
    )
    assert hours == Decimal("200.00")
    assert classification_for_capacity() == "estimated"


def test_unknown_health_beats_a_prior_green_period():
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    definition = DefinitionView(slug="quarterly_net_revenue", required=True, freshness_limit_days=45)
    stale = ObservationView(
        period_end=now - timedelta(days=110),
        value=Decimal("1"),
        completeness="complete",
        observed_at=now - timedelta(days=100),
    )
    status, missing = evaluate_health([definition], {"quarterly_net_revenue": [stale]}, now)
    assert status == "unknown"
    assert missing == ["quarterly_net_revenue"]
    current_missing = ObservationView(
        period_end=now,
        value=None,
        completeness="missing",
        observed_at=None,
    )
    fresh_prior = ObservationView(
        period_end=now - timedelta(days=20),
        value=Decimal("1"),
        completeness="complete",
        observed_at=now - timedelta(days=1),
    )
    status, _missing = evaluate_health(
        [definition],
        {"quarterly_net_revenue": [fresh_prior, current_missing]},
        now,
    )
    assert status == "unknown"


def test_unscored_lens_rejects_a_zero():
    with pytest.raises(ValidationError):
        LensAssessment(
            lens="EX",
            score=0,
            status="insufficient_evidence",
            confidence="insufficient",
            confidence_reason="missing",
            evidence_ids=[],
            sample_summary="none",
            observed_period=None,
            limitations=[],
        )


def test_scorecard_requires_four_lenses_and_no_overall_field():
    with pytest.raises(ValidationError):
        XavierScorecard(
            summary="s",
            findings=[],
            missing_evidence=[],
            human_questions=[],
            proposed_actions=[],
            limitations=[],
            lenses=[],
            claim_gaps=[],
            overall_score=4,
        )


def test_fake_provider_does_not_invent_unknown_contracts():
    result = FakeModelGateway().generate(
        GenerateRequest("unknown.contract", "v1", "p", "e", "t", "b")
    )
    assert result.status == "unsupported_schema"
    assert result.output is None


def test_openai_adapter_is_a_capability_error_in_fixture():
    adapter = OpenAIAdapter(Settings())
    with pytest.raises(CapabilityError):
        adapter.generate(GenerateRequest("xavier.scorecard.v1", "v1", "p", "e", "t", "b"))
