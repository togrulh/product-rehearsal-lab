# Evidence memory and validation

This is a point-in-time retrieval layer for simulations, not a neural model of a customer. It separates what the data records from what the model says. The input is an approved feature view, not raw events or private text.

## Which signals are useful?

| Evidence role | Examples from approved views | What it does not establish |
| --- | --- | --- |
| `recent_event` | Last verified signup stage, repeated attempt or dated support contact | Intent, satisfaction, or a completed journey |
| `habit` | Active days and frequency by payment channel, repeated contributions, observed reward usage over a defined window | Personality, a preference that was not observed, or a reward response in another product |
| `current_state` | A dated contractual status, funding state, or verified balance band | The same state before that snapshot; absence of a match is not absence of a product |

Use separate application, transaction, service and contractual views where available. Normalize the event grain, owner bridge, lifecycle, currency and units before producing features. For habits, compute a documented trailing aggregate from eligible events; the runner does not infer repetition from a single event. Observations must have occurred and been available before the cutoff. A current snapshot cannot substitute for an earlier state.

## Retrieval policy

`max_age_days` is a hard freshness limit applied to the selected point-in-time observation, even if it was recently ingested. A value exactly at the limit is retained. `required_features` filters profiles that have some evidence but lack one or more task-critical facts; a profile with no task evidence is counted separately. A valid zero or false remains data. A matched null, stale observation and unmatched source are distinguished in the audit; none becomes a zero or false.

`memory_policy` restricts input to the named `signals` and a `max_features` budget. Define a role, a task relevance weight, and a `half_life_days` value for each signal. Once availability and freshness are checked, the runner uses:

`score = relevance * 2 ** (-age_days / half_life_days)`

The score halves each half-life, and `null` disables decay for that signal. Required signals come first; the rest sort by score and then feature key. The audit separates admission at the source from retrieval into the sampled prompts. Weights, cutoffs, and half-lives are configurable engineering settings, not measured human memory constants or outcome probabilities. The public examples are fictional and their settings are illustrative.

The distinction between individual episodes and slower regularities is inspired by [McClelland, McNaughton and O'Reilly's complementary learning systems paper](https://web.stanford.edu/~jlmcc/papers/McCMcNaughtonOReilly95.pdf). The use of recency and the recommendation to aggregate repeated experiences are inspired by [Anderson and Schooler](https://journals.sagepub.com/doi/abs/10.1111/j.1467-9280.1991.tb00174.x). Neither paper establishes this exponential rule or a banking simulation's accuracy. The package does not infer neural states, psychological traits, or rewards from transaction records. [Schultz, Dayan and Montague](https://pubmed.ncbi.nlm.nih.gov/9054347/) motivates studying expectation versus observed reward as a separate future hypothesis; no reward-learning mechanism is enabled here.

## How to test quality

1. Fix a question, model, cutoff, panel and acceptable choice set. Audit the evidence and missingness first, including whether exclusions change the panel. Check feature windows and identity joins independently of the model.
2. Use evidence ablation with the same profiles and conditions: compare the full prompt with one signal withheld, or with all profile facts withheld. Inspect valid pairs, changes, unaffected profiles, and replies that should be `unsure`. Lack of change can mean the remaining signals suffice, the model ignored the field, or the case was insensitive. A change alone does not show improvement. Inspect explanation claims separately.
3. To measure real predictive quality, define a subsequent observable action and predeclare the benchmark. Hold out both later time and customer groups as appropriate. Compare with simple baselines using matched cases and show coverage and uncertainty. Measure accuracy only against observed labels, not simulated choices or the previously exposed training/evaluation slice. If probabilities are needed, fit and validate calibration separately; this runner does not turn panel choice shares into probabilities.
