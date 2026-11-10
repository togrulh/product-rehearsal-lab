# Product Rehearsal Lab

Local, task-routed customer simulation. Ask a product question; the lab routes it to approved data sources, assembles a panel, and generates first-person answers with a local model. The run is labeled as simulation once. Product validation and live experimentation are outside this tool.

The optional [Virtual Community Studio skill](skills/virtual-community-studio/SKILL.md) packages the workflow for Codex. It can use this runner or another approved local runner; the skill itself does not install or start services.

## Install and try it

Clone the repository, then use an activated Python 3.12+ virtual environment:

```text
git clone https://github.com/togrulh/product-rehearsal-lab.git
cd product-rehearsal-lab
python -m pip install .
product-rehearsal plan examples/company_catalog.json examples/scenario_az.json
```

The base CLI has no third-party Python runtime dependencies. Planning does not contact a database or model. To generate demo replies, run [Ollama](https://ollama.com/) locally with a model already installed, and pass its exact tag from `ollama list`. For example, [Qwen 3.5 27B](https://ollama.com/library/qwen3.5:27b) is available separately; check your hardware and the model terms before downloading. No external dataset, cloud key or database is needed for the fictional demo.

```text
python demo.py --topic onboarding --model your-installed-model:tag
python demo.py --topic loyalty --model your-installed-model:tag
python -m unittest discover -s tests -v
```

`onboarding` exercises two sources and a follow-up changing just one condition. `loyalty` exercises a different pair of sources. `--output new-file.json` writes a UTF-8 demo receipt without overwriting anything. All demo rows are invented independently of any institution.

## Connect your company

1. Give dedicated read-only accounts access to approved aggregate feature views. Install the required driver extras with `python -m pip install '.[clickhouse]'`, `python -m pip install '.[oracle]'`, or `python -m pip install '.[databases]'` for both. Supply credentials via your secret manager at process start. ClickHouse uses `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USERNAME` (or `CLICKHOUSE_USER`), `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_SECURE` (TLS on by default). Oracle uses `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE_NAME`, `ORACLE_USER`, `ORACLE_PASSWORD`. Do not put credentials in the mapping file.
2. Copy `examples/company_catalog.json` to a **private** tenant mapping. Specify topics and AZ/RU/EN aliases, their population anchor, allowed sources, and optional schema scopes and discovery terms. Map a shared identity namespace only after validating the bridge. Other institutions can map their own CRM, event, order and support views; no bank-specific schema is required.
3. Use `plan` to see the selected route, `discover` to search approved schemas for candidate objects, and `probe` to verify the mapped views and columns without retrieving customer rows. Discovered tables are never automatically added to an executable plan. Supply `topic` explicitly if the task is ambiguous or has no registered alias.
4. Edit the example scenario, including its observation cutoff. Run it against the configured local model.

```text
product-rehearsal plan company_catalog.json examples/scenario_az.json
product-rehearsal discover company_catalog.json examples/scenario_az.json
product-rehearsal probe company_catalog.json examples/scenario_az.json
product-rehearsal run company_catalog.json examples/scenario_az.json --model your-installed-model:tag
```

### View contract

- `profile_key`: text internal cohort key. Never sent to the model or printed. It must refer to the same entity across views using the same declared namespace. `segment`: a reviewed, non-identifying code on the catalog allowlist; sources must agree.
- `event_at` and `available_at`: normalized UTC; snapshots must have been both observed and available strictly before the scenario cutoff. Oracle timestamp columns are UTC without session-dependent conversion; ClickHouse uses UTC `DateTime64` and SQLite uses ISO text. One version per `(profile_key, event_at, available_at)`; duplicates at the selected timestamp are rejected. Publish pre-aggregated, bounded views, not raw histories.
- Features are numeric, boolean or closed enum values with human meanings. Keep observed habits, recent journey signals and product facts in separate source features. Do not expose free text, raw IDs, exact location, sensitive attributes or identifying combinations. Numeric data is not automatically non-identifying: mapping review is required. Keep the model service itself isolated with no external egress.
- The anchor defines membership. Missing enrichment stays unknown, not zero. The default cap is 10,000 eligible source rows per view and the panel is a deterministic, segment-diverse sample, not a population-weighted estimator. A missing/ambiguous mapping, incompatible key scope, duplicate latest record or source over cap fails closed.
- Follow-ups update only listed conditions and carry the successful dialogue forward. Reply format and referenced evidence keys are validated; prose is not automatically certified. Model errors appear in the run output and count as incomplete, with no remote fallback.

## What was borrowed, and what is optional

- [NVIDIA Nemotron Personas](https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA) and [NeMo Data Designer](https://github.com/NVIDIA-NeMo/DataDesigner): keep structured attributes separate from generated prose. The local data supplies the attributes; the US corpus does not provide priors, identities or missing values. No third-party records are redistributed or required.
- [MatrAIx paper](https://arxiv.org/abs/2608.04205) and [source](https://github.com/MatrAIx-ai/MatrAIx-Persona-8B): scenario, agent and response-verifier boundaries. [Concordia](https://github.com/google-deepmind/concordia): carry conversation and environment state across turns. [Nubank/Snowglobe paper](https://arxiv.org/abs/2609.30137v1): isolate the simulated interaction from production actions. These are design references, not runtime dependencies.
- The repository intentionally does not ship bank mappings, credentials, customer rows, raw conversations, or weights. There is no production action or A/B execution in this package.

Original project files are available under the [MIT License](LICENSE). External models, datasets and optional packages are distributed separately under their respective terms.
