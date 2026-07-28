# AI-enabled-CI-Agent
I built an AI Agent that is able to classify and triage Continuous Improvement (CI) ideas in line with defined autonomy tiers, massively improving the efficiency of managing the CI lifecycle.
## Overview
- Role: Designer / Developer
- Timeline: 1 week
- Tools: Python, Claude
- Live demo: [View it](#)
- Repository: You’re here
## The problem
At FIS, I manually triaged 300+ improvement ideas across 8 functions (2 Lines of Business). This project rebuilds that process as an AI-enabled pipeline, while making the same risk and control decisions I'd apply manually, explicit and auditable.

## What it does

State what success looked like. For example:

- Classify the raw CI ideas by effort and impact
- Triage the classified ideas as auto-filed to backlog or flagged for human review, based on defined autonomy tiers
- Draft high-level DMAIC style feasibility assessment for high-impact ideas, to help the human reviewer decide whether to proceed

## Architecture at a glance
[![CI Classification & Triage Map](CI%20Classification%20%26%20Triage%20Map.png)](CI%20Classification%20%26%20Triage%20Map.png)

## The interesting part: the AX design decisions - [Read the AX Design Document](AX%20Design%20Document.md)
Every classified idea gets routed through a risk-based autonomy check, not just filed automatically. Low-impact, low-effort ideas move straight to the backlog with no human involvement. Ideas with large business impact, or medium impact paired with a large delivery effort, is always flagged for a human to sign off before resource gets committed.
The logic is deliberately conservative: the cost of a wrong automatic decision on a high-impact idea is judged too high to automate away.

## What I'd do next

mentioning Excel/SharePoint input, Power Automate no-code version, real process mining data. Shows this is a live capability, not a one-off exercise.

## Results

Use measurable outcomes where possible:

- Reduced [time/errors] by X%
- Increased [completion/adoption] by X%
- Delivered [feature/system] by [date]
- Learned [important insight]

If you do not have metrics, state observable outcomes and feedback honestly.

## What I’d improve next

- Improvement one
- Improvement two
- Improvement three

## Running the project locally

```bash
git clone https://github.com/YOUR-USERNAME/YOUR-REPO.git
cd YOUR-REPO
# Add setup/run instructions here
