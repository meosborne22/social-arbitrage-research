# Social Arbitrage Research Engine — MVP

This is the lean first version of a systematic social-arbitrage research operation.

## Core rule

The system does **not** start with stocks. It starts with consumer behavior:

consumer behavior -> emerging trend -> corroborating evidence -> company exposure -> fundamental impact -> market awareness -> valuation -> Level 3/4 thesis -> 0-100 score -> alert

It never places trades.

## Initial thresholds

- 90-100: Exceptional / immediate alert candidate
- 80-89: High conviction / alert candidate
- 70-79: Developing / 7 AM report
- <70: Research/watchlist only

Scores are dynamic. Contradictory evidence can reduce a thesis score.

## Portfolio constraint

Reference portfolio: ~$20,000-$25,000.
Maximum intended position size: 10% (~$2,500).
This is a research constraint, not an automatic position recommendation.

## Microcap policy

Microcaps are allowed, but must pass strict checks for:
- liquidity and dollar volume
- bid/ask spread
- dilution / share issuance
- convertibles
- debt and cash runway
- going-concern warnings
- reverse splits
- stock-based compensation
- insider transactions
- related-party transactions
- auditor/filing quality
- OTC/promotion risk

## MVP infrastructure

The intended lean production stack is:
- Python research engine
- Supabase/Postgres for the evidence and thesis database
- scheduled jobs via Supabase Cron or GitHub Actions
- Pushover for low-cost phone push alerts, with Twilio SMS as an optional fallback
- legitimate APIs/data providers and public-web research rather than unrestricted social scraping

Supabase Cron can schedule HTTP requests/Edge Functions, and GitHub Actions can run scheduled workflows. See the project notes in `SETUP.md`.

## Important data-access constraint

Do not assume every social platform permits unrestricted commercial scraping.
TikTok Research Tools require eligibility/application/approval, and Reddit has specific developer/data rules. The production collector should only use permitted access methods or licensed data providers.

## Files

- `config/scoring.json` — scoring weights and thresholds
- `config/guardrails.json` — microcap and thesis guardrails
- `src/scorer.py` — deterministic score calculator
- `src/thesis_schema.json` — machine-readable thesis structure
- `sql/schema.sql` — initial database schema
- `.github/workflows/daily.yml` — example scheduler
- `SETUP.md` — setup plan for a non-technical owner
