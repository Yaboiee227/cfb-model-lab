# QB news and market repricing

Run `python scripts/qb_market_event_study.py research/personnel/qb-news-ledger.json`.

The initial three historical leads are narrative evidence only. Neither qualifies for estimation. No fitted NFL or CFB injury coefficient exists. Historical line changes are market benchmarks, not independent QB point values.

Eligible records require league, affectedSide, kickoff, verified starterExpectedBeforeNews, preNewsQuote and postNewsQuote with the same named bookmaker, source, timezone-aware observedAt, spreadHome and total; news requires source and publishedAt. Require pre quote < news <= post quote < kickoff. Explicit confounders=[] is required for clean-event eligibility. Source timestamps must be independently audited; asserted timestamps alone do not prove provenance.

Capture immediate pre-news, first post-news and later closing quotes separately. Report NFL and CFB separately, time-to-reprice, coverage and exclusions. Do not substitute an opening line for an immediate pre-news quote. Weather, other injuries, lineup expectation and concurrent results can confound repricing. Never add market repricing directly to a forecast that already incorporates that market.

Free opening/closing archives can seed candidates, but lack of event timestamps prevents news attribution. Paid historical odds sources have not been purchased or used. Next requirements: primary-source news archives, same-book quote snapshots, additional CFB historical cases, independent provenance audit and chronological held-out validation.
