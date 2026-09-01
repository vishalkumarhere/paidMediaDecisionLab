# Independent two-campaign financial fixture

Inputs are explicitly written in `tests/fixtures/financial.json`. Expected values are fixed in `tests/fixtures/expected.json`; the tests do not generate expectations from the implementation. All amounts below are USD. Reporting date is July 6, 2026 unless specified; the cutoff is August 24, 2026 at 12:00 UTC.

## Order O1 — campaign C01

Two units at $600 gross per unit → $1,200 gross. Allocated discounts $200 → $1,000 booked revenue. Unit cost $300 → $600 original COGS. Outbound fulfillment $20. Original payment fees $30.

July 8: goodwill refund $200, no physical return, no inventory recovery; $5 of payment fees refunded. July 9: a second partial refund of $300, one physical unit returned, recoverable inventory value $200, return handling $10, no additional fee refund. Both events are available before the cutoff.

Net revenue = $1,200 − $200 − $200 − $300 = **$500**.

Net COGS = 2 × $300 − $200 = **$400**. The goodwill refund does not reduce COGS.

Net fees = $30 − $5 = $25.

Contribution before media = $500 − $400 − $20 − $25 − $10 = **$45**.

Campaign C01 has two ad-delivery rows with $60 and $40 spend. Aggregate them to $100 before joining outcomes. Contribution after media = $45 − $100 = **−$55**. Business net ROAS = $500 / $100 = **5.0x**.

## Order O2 — campaign C06

One unit, $600 gross, $100 discount, no refunds. Unit cost $300. Fulfillment $10 and fees $15.

Net revenue = $600 − $100 = **$500**. Net COGS = **$300**.

Contribution before media = $500 − $300 − $10 − $15 = **$175**.

The fixture supplies $100 affiliate media expense directly, independently of the generator's percentage assumption. Count it once: contribution after media = $175 − $100 = **$75**. Business net ROAS = $500 / $100 = **5.0x**.

## Boundary examples

O3 is a cancelled C01 order on July 6. Despite its nominal gross/discount fields, its booked revenue, net revenue, COGS and contribution are all **zero**; it is not a fulfilled order.

O4 is a fulfilled C06 order on July 7: gross $600 less $100 discount, with $10 fulfillment and $15 fees. That day's unit cost is missing. Net revenue is **$500**, but COGS and contribution are **unknown / NULL**. Its campaign has $10 of media expense. The absence of a cost cannot make its margin appear larger.

## Independent totals

July 6: two fulfilled orders; net revenue **$1,000**; media expense **$200**; contribution before media **$220**; contribution after media **$20**. Adding the July 7 order gives net revenue **$1,500** and media expense **$210**, but complete contribution across both days is unknown due to O4's missing cost.

The two campaigns have equal **business net ROAS**, not equal platform ROAS. The fixture's platform C01 claim is $1,000 before refunds; C06 claims $500. These cannot be relabeled as post-refund business outcomes.

The comparison demonstrates why ROAS alone is insufficient. It does not establish that C06 should receive more budget: volume, maturity, stock, tracking and marginal response still require evidence.
