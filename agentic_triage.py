"""
Agent Name: CI Idea Triage & Routing
----------------------------------------------
Reads the output of classify_ideas.py (classified_ideas.csv) and takes the
next step: deciding what happens to each idea, and acting on that decision.

This is what makes it "agentic" rather than a batch classifier:
  - It makes a genuine autonomy-tier decision per idea (auto-file vs.
    flag for human review), based on business risk (impact/effort).
  - For high-impact ideas, it drafts a short DMAIC-style feasibility
    assessment automatically — a real multi-step action, not just a label.
  - Every decision is logged to an audit trail, so if this ran unsupervised
    overnight, you could reconstruct exactly why it did what it did.

SETUP:
  Same as classify_ideas.py — .env file or exported ANTHROPIC_API_KEY.
  Run classify_ideas.py FIRST so that classified_ideas.csv exists.

RUN:
   python agentic_triage.py
"""

import csv
import os
import sys
import time
from datetime import datetime, timezone
from anthropic import Anthropic, APIStatusError, APIConnectionError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MODEL = "claude-sonnet-5"
INPUT_CSV = "classified_ideas.csv"
ROUTED_CSV = "routed_ideas.csv"
AUDIT_LOG_CSV = "audit_log.csv"


def determine_autonomy_tier(impact: str, effort: str) -> tuple[str, str]:
    """
    Decide what happens to an idea, and why. Returns (tier, guardrail_reason).

    Rules (business-risk based, same logic you'd use for a CI control design):
      - Any Large-impact idea always goes to a human — the cost of a wrong
        auto-decision is too high to automate away.
      - Medium-impact + Large-effort also goes to a human — committing
        significant delivery effort shouldn't happen without sign-off.
      - Everything else (S/M impact with S/M effort) is low-risk enough
        to auto-file directly into the backlog.
    """
    if impact == "L":
        return "flag_for_review", "High business impact — always requires human sign-off."
    if impact == "M" and effort == "L":
        return "flag_for_review", "Medium impact but large delivery effort — requires sign-off before committing resource."
    return "auto_file", "Low impact/effort combination — within auto-approval guardrail."


# --------------------------------------------------------------------------
# The multi-step action: draft a feasibility assessment for flagged,
# high-impact ideas — this is the "does something", not "labels something" part.
# --------------------------------------------------------------------------

FEASIBILITY_SYSTEM_PROMPT = """You are a continuous improvement analyst drafting a first-pass \
feasibility assessment for a business improvement idea, to help a human reviewer decide whether \
to proceed. Structure your response using DMAIC headings: Define, Measure, Analyze, Improve, Control. \
Keep each section to 1-2 sentences — this is a draft to speed up human review, not a final assessment. \
Respond with ONLY the assessment text, no preamble."""


def call_claude(client: Anthropic, system_prompt: str, user_content: str) -> str:
    """Shared retry-wrapped call to Claude, with thinking disabled for speed/cost on this task."""
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1000,
                thinking={"type": "disabled"},
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            text_blocks = [b.text for b in response.content if b.type == "text"]
            if not text_blocks:
                raise ValueError(f"No text block found (stop_reason={response.stop_reason!r})")
            return text_blocks[0].strip()
        except (APIStatusError, APIConnectionError) as e:
            is_transient = isinstance(e, APIConnectionError) or getattr(e, "status_code", 0) >= 500
            if is_transient and attempt < max_attempts:
                wait_seconds = 2 ** attempt
                print(f"    Attempt {attempt} failed ({e}). Retrying in {wait_seconds}s...")
                time.sleep(wait_seconds)
            else:
                raise


def draft_feasibility_assessment(client: Anthropic, idea_row: dict) -> str:
    user_content = (
        f"Idea: {idea_row['idea']}\n"
        f"Function: {idea_row['function']}\n"
        f"Effort: {idea_row['effort']} | Impact: {idea_row['impact']}\n"
        f"Original classification rationale: {idea_row['rationale']}"
    )
    return call_claude(client, FEASIBILITY_SYSTEM_PROMPT, user_content)


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def load_classified_ideas(path: str) -> list[dict]:
    if not os.path.exists(path):
        raise SystemExit(
            f"'{path}' not found. Run classify_ideas.py first — this script "
            "picks up where that one left off."
        )
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_results(routed: list[dict], audit_log: list[dict]) -> None:
    if routed:
        with open(ROUTED_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(routed[0].keys()))
            writer.writeheader()
            writer.writerows(routed)
        print(f"Saved {len(routed)} routed ideas to {os.path.abspath(ROUTED_CSV)}")

    if audit_log:
        with open(AUDIT_LOG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(audit_log[0].keys()))
            writer.writeheader()
            writer.writerows(audit_log)
        print(f"Saved audit trail to {os.path.abspath(AUDIT_LOG_CSV)}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY not found. See classify_ideas.py's setup instructions — "
            "same .env file or exported variable works here too."
        )

    client = Anthropic(api_key=api_key)
    ideas = load_classified_ideas(INPUT_CSV)
    print(f"Loaded {len(ideas)} classified ideas from {INPUT_CSV}\n")

    routed_results = []
    audit_log = []

    try:
        for idx, row in enumerate(ideas, start=1):
            tier, guardrail_reason = determine_autonomy_tier(row["impact"], row["effort"])
            timestamp = datetime.now(timezone.utc).isoformat()

            feasibility_text = ""
            if tier == "flag_for_review" and row["impact"] == "L":
                print(f"  [{idx}/{len(ideas)}] Drafting feasibility assessment (flagged, high impact)...")
                feasibility_text = draft_feasibility_assessment(client, row)
                action_taken = "Flagged for human review; draft feasibility assessment attached"
            elif tier == "flag_for_review":
                action_taken = "Flagged for human review"
                print(f"  [{idx}/{len(ideas)}] Flagged for review (no draft needed at this tier).")
            else:
                action_taken = "Auto-filed to backlog"
                print(f"  [{idx}/{len(ideas)}] Auto-filed.")

            routed_results.append({
                **row,
                "autonomy_tier": tier,
                "action_taken": action_taken,
                "feasibility_assessment": feasibility_text,
            })

            audit_log.append({
                "timestamp": timestamp,
                "idea": row["idea"][:80],
                "impact": row["impact"],
                "effort": row["effort"],
                "autonomy_tier": tier,
                "guardrail_reason": guardrail_reason,
                "action_taken": action_taken,
                "model_used": MODEL if feasibility_text else "n/a (rule-based decision only)",
            })

        save_results(routed_results, audit_log)

        auto_count = sum(1 for r in routed_results if r["autonomy_tier"] == "auto_file")
        review_count = len(routed_results) - auto_count
        print(f"\nSummary: {auto_count} auto-filed, {review_count} flagged for human review.")

    except Exception as e:
        print(f"\nSomething went wrong: {type(e).__name__}: {e}", file=sys.stderr)
        raise
