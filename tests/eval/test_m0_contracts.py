import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

AGENTS = {
    "gm": "PartnerBrief",
    "scout": "ScoutShortlist",
    "ainge": "AingeReport",
    "xavier": "XavierScorecard",
    "mutombo": "IndependentRiskReport",
    "stockton": "ActivationThesis",
    "sloan": "OperatingRoadmap",
    "trainer": "PortfolioHealth",
    "scorekeeper": "DecisionRetrospective",
}

SCHEMAS = [
    "agent_run.schema.json",
    "evidence.schema.json",
    "artifact.schema.json",
    "review.schema.json",
    "decision.schema.json",
    "events.schema.json",
]


def test_prompt_pack_v1_names_its_output_contract():
    for agent, output_type in AGENTS.items():
        text = (ROOT / "prompts" / agent / "v1.md").read_text()
        assert "Prompt version: v1" in text
        assert output_type in text
        assert "Do not" in text


def test_json_schemas_parse():
    for name in SCHEMAS:
        document = json.loads((ROOT / "contracts" / name).read_text())
        assert document["$schema"].endswith("/schema")
        assert document["type"] == "object"


def test_generated_client_covers_the_openapi_document():
    spec = json.loads((ROOT / "contracts" / "openapi.json").read_text())
    client = (ROOT / "apps" / "web" / "src" / "api" / "generated.ts").read_text()
    assert "/api/v1/ic-packets/{packet_id}/decisions" in spec["paths"]
    assert "export function postDecision" in client
    assert "export function getOverview" in client
    for path in spec["paths"]:
        assert path.startswith("/api/v1/")
