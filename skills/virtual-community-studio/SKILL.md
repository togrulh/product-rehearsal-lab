---
name: virtual-community-studio
description: Use when a product or research team wants to build a virtual customer panel, derive task-specific personas from approved data, generate first-person survey answers, or continue a simulated product or support conversation. Also applies to packaging a portable customer-simulation workflow. Not for routine BI, individual credit decisions, or running live experiments.
---

# Virtual Community Studio

Turn a product question into a panel and replies. The reusable unit is a **question, a versioned audience, and the evidence that audience can see**. A different product can reuse the engine, not another product's facts, terms, or outcomes.

## Run the requested mode

- **Existing panel:** resolve the last accepted panel, model and session state first. Apply only the user's change. Keep identities, weights, prompt, model and unchanged conditions unless the request explicitly replaces them.
- **New company-backed panel:** write a short run card (question, options or conditions, eligible audience and sampling, cutoff/time zone, answer language, model and output). Read [source admission](references/source-admission.md). Route against approved mappings, not guessed joins. If some evidence is missing, use the verified subset only if it still answers the question; otherwise name the exact missing mapping.
- **No usable company source:** if a demo answers the request, run separately with invented inputs. Public persona data can inform structure or explicitly synthetic coverage, never fill a person's missing attributes.

For execution and follow-ups read [panel and dialogue](references/panel-and-dialogue.md). Use an available, verified local runner; `Product Rehearsal Lab` is supported but not required. Do not silently substitute a different model or a hand-written answer for a requested model run. Do not start a second worker or replace failed agents to improve a split.

## Deliver

Put the simulation label once in the run header. Then give direct first-person replies in the requested language. For a summary, state the panel and denominator, distinguish incomplete responses, and apply weights only if their source and target population are defined. Unknown is not zero or rejection. Keep observed facts, scenario conditions, stated choices and actual outcomes separate. The user owns external validation and A/B testing; do not run them or add an accuracy discussion by default.

Reopen the result and verify audience, conditions, model, sample coverage and meaning of material claims. Read [verification and provenance](references/verification-and-provenance.md) for a comparison, a validation request, or a shareable package. This workflow does not authorize publication, data transfer, production changes, new services, or dependency installation.
