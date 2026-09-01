# Architecture and reproducibility

## Data flow

`config → seeded journey generator → typed raw Parquet → cutoff staging → order economics → order attribution → campaign/day + reconciliation → processed Parquet + manifest`

Simulator labels go separately to `evaluation_only/ground_truth.json`. The transform function receives a database loaded from the 12 raw tables only, and SQL reads staging/parameters rather than the evaluation directory. Labels are isolated to prevent accidental analytical leakage; they are not encrypted or a security boundary against someone inspecting the project.

The stack is Python 3.12, DuckDB and Parquet, with pytest for verification. There is no web server, database service, account integration or LLM dependency. Dependency versions are pinned in the requirements files. DuckDB's timezone conversion requires both the bundled timezone database and Python timezone support; these are declared runtime dependencies.

## Generation design

One seeded random process produces connected customer journeys, touches, orders, tracking events and platform claims. This maintains meaningful relationships between sources instead of generating unrelated totals. Repeat synthetic customers, organic traffic, cross-channel paths, conversion delays, cancellations, returns, commissions, known spend plans and creative tags are included.

Three incident types are planted: a promotion, a purchase-tracking outage and an inventory constraint. Prospecting also uses a fictional additional discount and higher return probability. These are test conditions, not discovered business findings. Later milestones must add neutral and held-out cases before claiming a detector works.

Conversions can occur up to 10 days after a touch; refunds 8–35 days after a purchase, with additional source-availability delay. Platform reporting snapshots occur at one, three and seven days after the reported purchase date. All are immutable source observations in this simulation. Data after the cutoff intentionally remains in raw files so temporal restrictions are testable.

## Execution and integrity

`python -m luxe_lab build --output data/new-run` performs generation, raw export, validation, SQL transformation, output validation and manifest creation. The destination must be empty or absent. A failed run may leave diagnostic files without a manifest; choose a new folder on retry. There is no recursive cleanup or silent overwrite.

SQL is executed in filename order. Refunds aggregate before joining lines; delivery and commerce each aggregate before joining campaign/day totals. Costs have unique date/SKU keys. Attribution emits one row per order. Checks verify that revenue, spend and allocation counts survive those transformations.

The manifest is written only after validation succeeds. Warnings such as missing costs are not classified as valid complete financial estimates: the relevant metrics remain NULL. All integrity errors stop the build; missing cost/media conditions can pass structural validation while explicitly limiting use.

## Reproduction and provenance

With identical configuration and runtime, seed 42 must reproduce the same raw and processed logical-content and Parquet-file hashes. Tests perform two independent builds and compare both. A different seed changes generated outcomes. Logical hashes canonicalize column names and sorted normalized row values, independent of source row ordering. File hashes also check the serialized output.

The combined dataset hash covers raw table logical hashes; it does not include the reporting cutoff. Consequently, changing only `as_of` preserves raw hashes but changes eligible processed outputs. The full config and individual processed hashes in the manifest identify that analytical state. `source_code_sha256` covers Python, SQL, configuration and dependency declarations. Runtime versions are recorded separately. Byte-for-byte identity across different DuckDB/Python/timezone versions is not promised.

Windows runtime used for the release is recorded in `docs/validation-report.json`. Create a new local virtual environment after extracting; copying an existing `.venv` between machines or drive letters is unsupported. Generated data and environments are ignored by Git, while a release archive includes one verified sample dataset for convenience.

## Verified behavior and remaining limits

Tests cover fixed-cent arithmetic, partial and physical refunds, cancellations, missing costs, zero spend, unmatched orders, duplicate keys, foreign keys, creative ownership, snapshot replacement, seven-day boundaries, daylight-saving conversion, future-information exclusion and seeded reproduction. See the validation report for the executed test count and run evidence.

These are foundational correctness checks, not a full production audit. No causal inference, recommendation quality, forecasting accuracy, UI usability or hosting performance has been evaluated yet.

Important simplifications: one SKU and currency; stable synthetic identities; no tax/shipping revenue; initial-known cancellation status; no lifecycle revisions; no marketplace fees, overhead or subscription lifetime value; no inventory movement accounting; complete simulated commerce ledger; no real consent, ingestion, authentication or platform API integration. Cost recovery checks cannot prove the value of returned goods; values remain supplied assumptions. Daily media summaries are period reporting, not causal or cohort estimates.

## Next implementation boundary

Milestone 3 should derive maturity and data gates, then implement one decision record and screen against the hand fixture. Keep evaluation labels outside the screen's data path, show NULLs honestly, and keep the action traceable to calculations and policy. Do not begin forecasts or publish a demo until the later gates are satisfied.
