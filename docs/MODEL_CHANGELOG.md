# Model changelog

No production model is called in this milestone. Prompt pack `v1` is the text under `prompts/*/v1.md`, aligned to policy version `2026-10-06`.

| Date | Change |
|---|---|
| 2026-10-06 | Prompt pack v1 committed for GM, Scout, Ainge, Xavier, Mutombo, Stockton, Sloan, Trainer, and Scorekeeper. Output types are the contracts in those files. |
| 2026-11-02 | Fixture processes set `MODEL_PROVIDER=fake`. The fake gateway returns `unsupported_schema` and an empty body for an unknown contract. It does not draft a memo. |
| 2026-11-02 | OpenAI and Anthropic adapters exist and raise `CAPABILITY_UNAVAILABLE` when the process is not a reviewed live configuration. They do not send a request. |

`MODEL_ID_FAST`, `MODEL_ID_ANALYSIS`, and `MODEL_ID_CRITIC` stay empty until a live provider is chosen. Do not treat the fixture gross-MOIC illustration or the 200 hour capacity example as model output. Both are deterministic calculations with their classifications stored on the row.
