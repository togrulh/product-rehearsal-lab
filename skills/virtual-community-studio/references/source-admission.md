# Admit evidence before building a panel

## From a business question to sources

Choose the population anchor before enrichment. A session, payment, customer, account, card, ticket and contract are different grains. A signup-friction question normally starts from signup attempts, including unfinished attempts if in scope; it does not start from active cards by default. A loyalty-choice question might start from eligible loyalty members and enrich with observed reward use and channel preferences. A repeated event does not make a customer count twice.

For a connected system, read the approved tenant catalog or semantic mapping first. Search metadata in the allowed schemas; a name match is a candidate, not a business definition. ClickHouse often supplies behavioral events; Oracle often supplies contractual or accounting state. These are roles, not assumptions about particular tables. Check required columns and read access, then verify grain, window, status, units/currency, nulls and effective-time rules. Reduce one-to-many histories at their own grain before joining; a coincident key, overlapping dates or equal totals do not prove shared identity. Audit one-to-one/many counts, unmatched and conflicting rows. Report what stayed unmatched rather than assigning the nearest record.

If the workspace retains a validated baseline, read its current handoff, progress and checkpoints before rebuilding. Inherit only compatible rules and pinned inputs; a newer explicit correction wins. Use the current owner's approved transaction taxonomy: e.g., a card balance top-up, transfer, technical posting, authorization and completed purchase are different even when titles look alike. Apply corrections within their verified era and product. Do not publish a private join map.

## Time and meaning

For historical runs, require event time **and** availability/version time strictly before the cutoff. Use the latest eligible version of each fact. For example, a Feb 1 event arriving Feb 12 is not evidence for a Feb 8 run. A later upload or current master state cannot stand in for what was known. Treat unavailable, conflicting and inapplicable evidence as distinct from a measured zero. Hold out later outcome labels from profile generation even when easy to query.

Preserve joint feature relationships when creating panels; don't independently attach demographic or economic traits from external marginal rates. Take relevant product behavior, observed app friction, support categories and dated financial indicators where needed. Do not infer family status, psychology, income, residence or intent from an unrelated field: purchase location is not home, incoming funds are not necessarily salary, and zodiac is not a customer behavior signal. Sensitive attributes are not default features; use only appropriate, explicitly permitted, minimized bands for a justified purpose.

At the model boundary use reviewed numeric, Boolean or closed category features plus their scope and date. Keep raw IDs, contacts, addresses, exact dates of birth, raw messages and identifying sequences in protected source systems. Hiding an identifier does not make a rare combination safe. Data-derived inference stays in the approved local or organization-controlled boundary; if unavailable, offer a separately labeled demo or report the gap, not an external fallback.
