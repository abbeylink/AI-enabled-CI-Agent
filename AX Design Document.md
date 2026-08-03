# AX Design Document
### AI-Enabled Continuous Improvement Idea Intake & Triage Agent

---

## Scope

**In Scope** — the agent handles:
- Classification of each improvement idea by: function, estimated effort (S/M/L), estimated impact (S/M/L), and a one-line rationale for the classification.
- Storage of classification output in .csv format, as input for the next stage.
- A genuine autonomy-tier decision for every classified idea — auto-file to backlog vs. flag for human review — based on business risk (impact/effort).
- Automatic drafting of a high-level DMAIC-style feasibility assessment for high-impact ideas, to help the human reviewer decide whether to proceed.

**Out of Scope** — the agent does not handle:
- Generation of improvement ideas for classification and routing.
- The final decision on how to proceed with ideas flagged for human review.
- Overriding a human reviewer's decision once made.

---

## Autonomy Tiers

| Tier | Trigger | Human involvement |
|---|---|---|
| Auto-file | S/M impact with S/M effort | None — proceeds directly to backlog |
| Flag for review | Medium impact + Large effort | Required before resource is committed |
| Flag for review | Large impact (any effort) | Always required — cost of a wrong auto-decision is too high to automate away |

Classification itself (function, effort, impact, rationale) is automatic and does not require human review — only the *routing decision* that follows it is risk-gated.

---

## Guardrails

Guardrails are the protective mechanisms that catch things going wrong *within* the autonomy-tier logic above — distinct from the tiers themselves, which decide *where an idea goes*.

- **Low-confidence or malformed classification output:** if the model's response doesn't parse into the expected structure (e.g., missing fields, malformed JSON), the idea is never silently dropped or auto-filed by default — it fails safe to "flag for review" and is logged as a processing exception.
- **Ambiguous or borderline classification:** ideas sitting on a tier boundary (e.g., impact rated inconsistently across similar ideas) are surfaced for periodic sampling review rather than trusted as ground truth on a single pass.
- **Service availability:** transient API failures (e.g., provider overload) are retried automatically with backoff; a persistent failure after retries escalates to a notification rather than failing the pipeline silently.
- **Human override, always available:** a human can adjust the impact/effort thresholds underlying the autonomy tiers, or manually override any auto-file decision after the fact — the agent's decisions are never final or irreversible.

---

## Failure Mode Analysis

| Failure mode | Risk if unmitigated | Mitigation |
|---|---|---|
| High-impact idea misclassified as low-impact | Auto-filed without human sign-off, bypassing the control that exists specifically for high-risk ideas | Periodic sampling audit of auto-filed ideas (e.g., 10% weekly review); classification rationale logged for every idea to support the audit |
| Output variability across runs | High variability of ideas classification across multiple runs of the 'Classify Ideas' script. This risk is inherent to LLM-based classifications and not unique to this Agent | <ul><li> Concrete anchors for effort and impact, replacing vague guidance ("frequency × time lost × risk") with specific thresholds (e.g., "under 5 hours/week = S impact," "cross-functional integration = L effort"), so the model has fixed reference points instead of re-deciding the boundary each time.</li><li> A conservative tie-breaking rule for impact specifically: if an idea sits exactly on a boundary, it rounds up toward the higher impact tier rather than down. This is to ensure adherence to the AX design's safety principle of erring towards the tier that gets human review, not away from it.</li><li> Output consistency is managed through prompt design (fixed rubric anchors) rather than a sampling-parameter setting, since that lever isn't available on this model generation</li></ul>|
| Model produces malformed or unparseable output | Pipeline fails, or an idea is silently dropped from the process entirely | Defensive parsing with explicit error surfacing; failed items default to flag-for-review rather than being dropped |
| API unavailable or overloaded | Processing stalls or partially completes | Automatic retry with exponential backoff; persistent failure triggers a notification rather than a silent stop |
| Feasibility assessment draft contains inaccurate or misleading content | Human reviewer makes a decision based on flawed input | Draft is explicitly labelled as a first-pass aid, not a final assessment; reviewer retains full decision authority and access to the original classification rationale |
| Autonomy thresholds become miscalibrated over time (e.g., business risk appetite changes) | Ideas are routed against outdated risk tolerance | Thresholds are configuration, not hardcoded logic, reviewable and adjustable by a human on a periodic basis |

---

## Audit Trail

An audit log entry is produced for every improvement idea the agent processes, containing:

- Timestamp
- Improvement idea
- Impact
- Effort
- Autonomy tier
- Guardrail reason
- Action taken
- Model used

This is designed so that if the agent ran unsupervised and a downstream issue emerged, the full decision — including which guardrail fired and why — can be reconstructed without needing to re-run anything.

---

## Handoff Protocol

Ideas flagged for human review are sent to an assigned reviewer **role** (a distribution list or shared mailbox, rather than a single named individual, to avoid a single point of failure) via email, containing:

- The flagged idea, its classification, and the guardrail reason it was flagged.
- The draft feasibility assessment, where one was generated (Large-impact ideas).
- A .csv attachment of all flagged ideas from that run, for batch review.

**Service level:** if a flagged batch is not actioned within 48 hours, a reminder notification is sent; the agent does not re-attempt the routing decision or take any further autonomous action on unactioned items.

---

## Human Override

A human can, at any time:
- Adjust the impact/effort thresholds that define the autonomy tiers.
- Manually override an auto-file decision after the fact.
- Pull any auto-filed idea back into the review queue.

No decision made by the agent is final or irreversible.
