# Setup Plan

## Phase 1 — Prove the signal

Do not buy premium datasets yet.

1. Create a GitHub account/repository for the project.
2. Create a Supabase project for the research database.
3. Run `sql/schema.sql` in Supabase SQL Editor.
4. Add API credentials only after each source is selected and its permitted use is confirmed.
5. Connect a phone notification provider.
6. Run the collector manually for several days.
7. Record every candidate thesis, including rejected candidates.
8. Begin paper tracking immediately.

## Phone alerts

Recommended lean option: Pushover. It supports an HTTPS message API and gives individual users a 10,000-message/month allowance; the mobile app is a one-time purchase after the trial period. SMS can be added later through Twilio.

## Scheduling

The first production schedule should be:

- continuous/intraday collection: several times per day
- thesis rescoring: several times per day
- exceptional alert: whenever a thesis crosses the alert threshold
- morning report: 7:00 AM America/New_York

The actual production schedule should live in the hosting scheduler, not on a personal computer.

## Phase 2 — Add sources

Start with sources that can be accessed legally and reliably. Suggested order:

1. Reddit / community signals where permitted
2. web/search trend signals
3. commerce/product evidence
4. SEC/company fundamentals
5. news and earnings transcripts
6. additional social platforms
7. premium alternative data only after measurement shows it improves hit rate

TikTok should not be treated as an automatically available unrestricted feed. Its current Research Tools require eligibility and approval and have data-freshness limitations.

## Phase 3 — Calibration

For every thesis save:

- timestamp
- score
- trend evidence
- company/ticker
- stock price at discovery
- expected catalyst
- invalidation criteria
- contradictory evidence
- 7/30/60/90/180-day outcome

The system should eventually learn which combinations of evidence produce the best forward returns.

## No auto-trading

The system must never submit an order, connect to a brokerage for execution, or place a trade.
