# Product Rehearsal Lab

Local, task-routed customer simulation. Ask a product question; the lab routes it to approved data sources, assembles a panel, and generates first-person answers with a local model. The run is labeled as simulation once. Product validation and live experimentation are outside this tool.

The optional [Virtual Community Studio skill](skills/virtual-community-studio/SKILL.md) packages the workflow for Codex. It can use this runner or another approved local runner; the skill itself does not install or start services.

## Install and try it

Clone the repository, then use an activated Python 3.12+ virtual environment:

```text
git clone https://github.com/togrulh/product-rehearsal-lab.git
cd product-rehearsal-lab
python -m pip install .
product-rehearsal plan examples/company_catalog.json examples/scenario_en.json
```

The base CLI has no third-party Python runtime dependencies. Planning does not contact a database or model. To generate demo replies, run [Ollama](https://ollama.com/) locally with a model already installed, and pass its exact tag from `ollama list`. For example, [Qwen 3.5 27B](https://ollama.com/library/qwen3.5:27b) is available separately; check your hardware and the model terms before downloading. No external dataset, cloud key or database is needed for the fictional demo.

```text
python demo.py --topic onboarding --model your-installed-model:tag
python demo.py --topic loyalty --model your-installed-model:tag
python -m unittest discover -s tests -v
```

Both demos use English. `onboarding` exercises two sources and a follow-up changing just one condition. `loyalty` exercises a different pair of sources. `--output new-file.json` writes a UTF-8 demo receipt without overwriting anything. All demo rows are invented independently of any institution.

### Compare two variants on the same panel

```text
python demo.py --compare --model your-installed-model:tag
```

Unlike a follow-up, `compare` asks the **same** question independently in both conditions. It builds the panel once, changes exactly one condition, and does not show either answer to the other invocation. The JSON report shows the sampled panel size (`eligible`), valid replies per variant, failure counts by reason, fully matched pairs, and how choices moved, overall and by segment. `unsure` is a valid choice; missing or invalid replies are not. Matched-choice counts use the same denominator for both sides, and incomplete runs exit with status 2 while still reporting coverage.

For approved data sources, edit [the comparison scenario](examples/comparison_en.json), then run:

```text
product-rehearsal compare company_catalog.json examples/comparison_en.json --model your-installed-model:tag
```

Define a neutral question, one existing condition to change, and 3–8 distinct choice labels including `unsure`. Comparison scenarios cannot contain follow-ups. The CLI returns counts by default; add `--include-replies` for local inspection of synthetic replies and their cited feature keys. This is a sensitivity check on simulated choices, not a live A/B test or an estimate of customer behavior. Differences can reflect model variation, and a valid choice code does not certify its explanation.

### Audit evidence and test whether it matters

```text
python demo.py --audit
python demo.py --memory-check --model your-installed-model:tag
product-rehearsal audit company_catalog.json examples/scenario_en.json
product-rehearsal compare company_catalog.json examples/evidence_sensitivity_en.json --model your-installed-model:tag
```

The audit does not call a model. It reports counts of admitted, stale, null and unmatched features for the bounded anchor and the sampled panel, without exposing profile keys or values. A catalog may define a feature's `max_age_days`, topic-specific `required_features`, and an optional `memory_policy` that ranks relevant evidence under a feature budget. These policies are opt-in and apply to both normal runs and comparisons.

For an evidence sensitivity check, keep the question and conditions unchanged and replace the comparison's `condition` and `value` with `omit_features`. Use a list of retrieved feature keys, or `"all"` for an empty-evidence control. The report states how many profiles were affected. A changed choice shows model sensitivity to the removed input in that run, not an effect on a real customer or proof the explanation is correct. See [evidence memory and validation](docs/evidence-memory.md) for the design, example signals, and validation protocol.

### Check choice stability before interpreting a result

```text
python demo.py --stress --model your-installed-model:tag
product-rehearsal stress company_catalog.json examples/choice_stress_en.json --model your-installed-model:tag
```

`stress` makes three independent calls per profile: the reference, an identical repeat, and a version with only choice order or question wording changed. It reports both switch counts on the same fully matched profiles, including breakdowns by segment and failures by arm. Add `--include-replies` for local review. See [choice design and validation](docs/choice-context.md) for the protocol and marketing examples. The output diagnoses a simulator's sensitivity; it is not a measure of customer persuasion or conversion uplift.

## Connect your company

1. Give dedicated read-only accounts access to approved aggregate feature views. Install the required driver extras with `python -m pip install '.[clickhouse]'`, `python -m pip install '.[oracle]'`, or `python -m pip install '.[databases]'` for both. Supply credentials via your secret manager at process start. ClickHouse uses `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USERNAME` (or `CLICKHOUSE_USER`), `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_SECURE` (TLS on by default). Oracle uses `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE_NAME`, `ORACLE_USER`, `ORACLE_PASSWORD`. Do not put credentials in the mapping file.
2. Copy `examples/company_catalog.json` to a **private** tenant mapping. Specify topics and language-specific aliases, their population anchor, allowed sources, and optional schema scopes and discovery terms. Map a shared identity namespace only after validating the bridge. Other institutions can map their own CRM, event, order and support views; no bank-specific schema is required.
3. Use `plan` to see the selected route, `discover` to search approved schemas for candidate objects, and `probe` to verify the mapped views and columns without retrieving customer rows. Discovered tables are never automatically added to an executable plan. Supply `topic` explicitly if the task is ambiguous or has no registered alias.
4. Edit the example scenario, including its observation cutoff. Run it against the configured local model.

```text
product-rehearsal plan company_catalog.json examples/scenario_en.json
product-rehearsal discover company_catalog.json examples/scenario_en.json
product-rehearsal probe company_catalog.json examples/scenario_en.json
product-rehearsal run company_catalog.json examples/scenario_en.json --model your-installed-model:tag
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
- [Promptfoo test case configuration](https://github.com/promptfoo/promptfoo/blob/main/site/docs/configuration/reference.md#test-case): compare variants on common inputs and validate against explicit response constraints. Product Rehearsal Lab uses a built-in local comparison and does not require Promptfoo.
- The repository intentionally does not ship bank mappings, credentials, customer rows, raw conversations, or weights. There is no production action or A/B execution in this package.

Original project files are available under the [MIT License](LICENSE). External models, datasets and optional packages are distributed separately under their respective terms.
