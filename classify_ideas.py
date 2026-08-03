"""
Agent Name: CI Idea Classifier
--------------------------------------
Takes a batch of free-text "improvement ideas" and uses Claude to classify
each one by function, effort, impact, and a one-line rationale.
 
This is the foundation on which the agentic triage/routing logic
 
SETUP:
 
    1. pip install anthropic python-dotenv
    2. In the SAME folder as this script, create a file named exactly ".env"
       containing one line:
         ANTHROPIC_API_KEY=your-key-here
       (no quotes, no "export", no spaces around the =)
    3. Run: python classify_ideas.py
 """
 
import json
import csv
import os
import sys
import time
from anthropic import Anthropic
from anthropic import APIStatusError, APIConnectionError
 
try:
    from dotenv import load_dotenv
    load_dotenv()  # loads variables from a .env file in the current directory, if one exists
except ImportError:
    pass 
 
MODEL = "claude-sonnet-5" 
BATCH_SIZE = 15  # ideas per API call — keeps each response comfortably within max_tokens
 
# --------------------------------------------------------------------------
# the improvement ideas are synthetic and not tied to any real employer's confidential process.
# --------------------------------------------------------------------------
SAMPLE_IDEAS = [
    "Accounts payable spends 4 hours every Monday manually matching purchase orders to paper delivery notes.",
    "Credit control tracks overdue invoices in an offline Excel sheet that isn't synced with the accounting software, leading to duplicate payment reminders.", 
    "Monthly bank reconciliations are done manually line-by-line because the banking portal and ERP aren't integrated.", 
    "Department heads submit budget requests via individual email attachments, forcing finance to consolidate 30+ files manually.", 
    "Foreign currency expense conversions are calculated manually using daily spot rates instead of being automated at submission.", 
    "Employee mileage claims require physical paper receipts to be taped to a sheet and handed to finance for approval.", 
    "Fixed asset register is maintained in a standalone spreadsheet, making depreciation entries prone to manual formula errors.", 
    "Intercompany transactions are manually reconciled at month-end via email chains between regional finance managers.", 
    "Corporate credit card statements are distributed as static PDFs, requiring cardholders to write line-item descriptions in a separate email.", 
    "Customer refund requests require sign-offs across three different software tools before payment can be processed.", 
    "Password reset requests dominate the helpdesk queue because there is no self-service portal for remote staff.", 
    "Software license allocations are tracked in a static sheet, resulting in paid subscriptions remaining active for departed employees.",
    "Offboarding an employee requires IT staff to manually revoke access across 15 separate SaaS platforms one by one.", 
    "System outage notifications are sent manually via email, which fails to reach users if the email server itself goes down.", 
    "Hardware inventory counts rely on annual physical audits rather than automated endpoint management software.", 
    "Local admin rights requests sit in a general ticketing queue for days because they lack an automated escalation path.", 
    "Security patch updates require manual deployment to individual laptops, leading to inconsistent compliance across remote teams.", 
    "IT asset returns from leaving employees are tracked via email notes, causing unreturned laptops to go unnoticed for months.", 
    "Access requests for sensitive shared folders are approved via verbal or Slack confirmation without a centralized audit log.", 
    "SaaS renewal dates and seat counts are managed across disparate department folders instead of a single IT procurement hub.", 
    "Address and emergency contact updates are submitted via PDF forms, requiring HR to re-key the data into the HRIS.", 
    "Annual leave balances must be calculated manually in a spreadsheet whenever an employee takes a half-day or unpaid leave.", 
    "Performance review forms are filled out in Word documents and stored in local folders, making company-wide talent mapping impossible.", 
    "Employee tenure milestones and probation end dates are tracked on a whiteboard, leading to missed review windows.", 
    "Benefits enrollment requires employees to fill out paper forms that HR manually inputs into the provider's third-party portal.", 
    "Parental leave requests require manual calculation of paid vs. unpaid time off across changing payroll cutoff dates.", 
    "Verification of employment letters are drafted manually from scratch for every landlord or mortgage lender request.", 
    "Sick leave reporting relies on employees messaging managers directly, leaving HR to chase up missing attendance records at month-end.", 
    "Employee handbooks are distributed as static PDFs, making it impossible to track who has read and acknowledged policy updates.", 
    "Workplace injury reports are logged via printed paper forms that must be physically scanned and filed in HR's archives.", 
    "Candidate interview feedback is gathered through informal Slack messages, leaving hiring decisions without structured scoring data.", 
    "Recruiter interview scheduling requires back-and-forth emails because calendars aren't integrated with a public scheduling link.", 
    "Job postings must be manually copied and pasted onto five different job boards individually for every open role.", 
    "Candidate reference checks are conducted via phone calls with manual notes taken in Word documents.", 
    "Offer letter creation requires manually re-entering candidate details from the ATS into a Word template.", 
    "Background check status updates must be manually checked on the vendor portal and typed into the ATS for hiring managers to see.", 
    "Candidate rejection emails are sent individually by recruiters, causing long delays and poor applicant experience.", 
    "Employee referral submissions are sent via email to HR, leading to lost records and missed referral bonus payouts.", 
    "Interview prep kits and candidate briefs are emailed as attachments rather than linked dynamically within the ATS candidate profile.", 
    "Sourcing metrics and time-to-hire data are calculated manually by exporting raw CSVs into Excel every quarter.", 
    "Non-Disclosure Agreements (NDAs) are drafted manually for standard third parties instead of using an automated self-service portal.", 
    "Contract redlines are managed through back-and-forth Word attachments via email, creating version control confusion.", 
    "Executed contracts are stored across individual local drives rather than a centralized, searchable digital repository.", 
    "Contract expiration and auto-renewal dates are tracked manually, risking unwanted auto-renewals with vendors.", 
    "Standard contract templates are updated locally by team members, resulting in outdated legal terms being sent to clients.", 
    "Signature requests are printed, physically signed, scanned, and emailed back instead of using an e-signature tool.", 
    "External legal counsel invoices are reviewed without centralized tracking, making it hard to audit against agreed hourly rates.", 
    "Compliance training completion rates are tracked via manual spreadsheets, making regulatory reporting tedious.", 
    "Trademark renewal deadlines are maintained on an individual lawyer's outlook calendar with no team-wide visibility.", 
    "Subpoena and data subject access requests (DSARs) require manually searching through unindexed email mailboxes across the organization.",
]

SYSTEM_PROMPT = """You are a continuous improvement analyst. For each improvement idea provided, \
classify it and respond with ONLY a JSON array (no other text, no markdown fences) where each \
element has exactly these fields:
 
- "idea": the original idea text (verbatim)
- "function": your best guess at the business function (e.g. Finance, HR, Talent Acquisition, IT, Sales, Legal, Operations, Customer Service)
- "effort": one of "S", "M", "L"
- "impact": one of "S", "M", "L"
- "rationale": a single sentence explaining the effort and impact rating
 
Use these fixed anchors — do not deviate from them, even if an idea seems borderline:
 
EFFORT:
- S: fixable via existing tools, a config change, or a single person's action. No new system integration. Days of work.
- M: needs a small, single-team project (e.g. a new workflow, a simple automation build). Weeks of work.
- L: needs cross-functional coordination and/or system integration (e.g. connecting two platforms, a new tool rollout). Months of work.
 
IMPACT (time saved, risk reduced, or error rate implied by the idea as described):
- S: affects one person or a small, occasional task. Roughly under 5 hours/week saved, low risk/ error reduction.
- M: affects a team or a regular weekly process. Roughly 5-20 hours/week saved, or moderate risk/error reduction.
- L: affects multiple teams, a customer-facing process, or has compliance/financial-control implications. Over 20 hours/week saved, or meaningfully reduces significant risk.
 
If an idea's EFFORT sits exactly on a boundary, use your best single judgement — effort ambiguity \
doesn't need to default any particular way. If an idea's IMPACT sits exactly on a boundary, round UP \
to the higher category — this keeps classification conservative by erring toward the tier that gets \
human review, rather than risking a high-impact idea being auto-filed."""
 
 
def chunked(items: list, size: int):
    """Split a list into successive chunks of at most `size` items."""
    for i in range(0, len(items), size):
        yield items[i:i + size]
 
 
def classify_ideas(client: Anthropic, ideas: list[str]) -> list[dict]:
    """Send a batch of ideas to Claude and return the parsed classification list."""
    user_content = "Improvement ideas to classify:\n\n" + "\n".join(
        f"{i+1}. {idea}" for i, idea in enumerate(ideas)
    )
 
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4000,
                thinking={"type": "disabled"},  # this task doesn't need reasoning tokens — keep the full budget for the answer
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            break
        except (APIStatusError, APIConnectionError) as e:
            # Retry on transient server-side issues (529 overloaded, 5xx, connection drops).
            # Don't retry on things like 401 auth errors — those won't fix themselves.
            is_transient = isinstance(e, APIConnectionError) or getattr(e, "status_code", 0) >= 500
            if is_transient and attempt < max_attempts:
                wait_seconds = 2 ** attempt  # 2, 4, 8, 16 seconds
                print(f"  Attempt {attempt} failed ({e}). Retrying in {wait_seconds}s...")
                time.sleep(wait_seconds)
            else:
                raise
 
    # Find the text block explicitly — response.content can include other
    # block types (e.g. a "thinking" block) before the actual text, so don't
    # assume it's always at index 0.
    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ValueError(
            f"No text block found in response (stop_reason={response.stop_reason!r}, "
            f"block types={[block.type for block in response.content]!r}). "
            "If stop_reason is 'max_tokens', increase max_tokens in the API call."
        )
    raw_text = text_blocks[0].strip()
 
    # Defensive parsing: strip markdown fences if the model adds them anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()
 
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        print("Failed to parse model output as JSON. Raw output was:\n", raw_text)
        raise e
 
 
def save_to_csv(results: list[dict], filename: str = "classified_ideas.csv") -> None:
    """Write classification results to a CSV file."""
    if not results:
        print("No results to save.")
        return
 
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["idea", "function", "effort", "impact", "rationale"])
        writer.writeheader()
        writer.writerows(results)
 
    print(f"Saved {len(results)} classified ideas to {filename}")
 
 
if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY")
 
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY not found.\n"
            "Either create a .env file next to this script (Option A in the setup "
            "instructions above), or export it in the SAME terminal session before "
            "running this script (Option B). See the top of this file for exact steps."
        )
 
    # Diagnostic: confirm a key was actually found, without printing the whole thing
    print(f"API key detected (starts with: {api_key[:8]}...)")
    print(f"Running from directory: {os.getcwd()}")
 
    client = Anthropic(api_key=api_key)
 
    try:
        batches = list(chunked(SAMPLE_IDEAS, BATCH_SIZE))
        print(f"\nClassifying {len(SAMPLE_IDEAS)} ideas using {MODEL} "
              f"in {len(batches)} batch(es) of up to {BATCH_SIZE}...")
 
        results = []
        for i, batch in enumerate(batches, start=1):
            print(f"\n  Batch {i}/{len(batches)} ({len(batch)} ideas)...")
            results.extend(classify_ideas(client, batch))
            if i < len(batches):
                time.sleep(1)  # small pause between batches, easy on rate limits
 
        print("\n--- Results ---")
        for r in results:
            print(f"[{r['function']}] Effort: {r['effort']} | Impact: {r['impact']} | {r['idea'][:60]}...")
            print(f"   Rationale: {r['rationale']}\n")
 
        save_to_csv(results)
        print(f"Full path: {os.path.abspath('classified_ideas.csv')}")
 
    except Exception as e:
        # Print the full error instead of failing silently, so you can see exactly
        # what went wrong (auth error, rate limit, malformed response, etc.)
        print(f"\nSomething went wrong: {type(e).__name__}: {e}", file=sys.stderr)
        raise
