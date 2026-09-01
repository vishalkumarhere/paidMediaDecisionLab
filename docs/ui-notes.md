# Streamlit interface

The data interface adds a read-only exploration layer to the milestone 2 foundation. It does not claim completion of the planned recommendation, forecasting or incrementality work.

## Data correctness

The loader verifies every displayed source against its manifest checksum. It loads the five analytical tables and only the required public/synthetic dimension context; it does not read `evaluation_only`. Order dates and attribution come from the verified analytical layer. Any raw dated context is additionally filtered by source availability at the selected run's cutoff.

Ratios are calculated from summed numerators and denominators, not averaged daily ratios. Missing monetary values propagate to unknown totals. Financial waterfalls reconcile with independently calculated fixtures and retain affiliate media expense only once. The order view does not invent an allocation of campaign-level spend onto individual orders.

Date selection changes the reporting range, not the run's information cutoff. Recent orders may still receive later refunds. The tracking-coverage chart is explicitly site-wide: only its date filter applies, not campaign or channel filters. Source-platform revenue retains its pre-refund definition and is never relabeled as business net revenue.

## Rendering and access

Native Streamlit layout, controls, theme and metric cards are combined with Plotly charts and escaped HTML tables. All plotted data is encoded as ordinary JSON lists. DuckDB reads Parquet files. PyArrow is a transitive Streamlit dependency but its native library is not loaded by this app, because Windows Application Control blocks that binary here. No security policy, binary trust metadata or package internals were modified.

Table cells and headers are HTML-escaped, unknown values are labeled, and overflow regions support keyboard scrolling. Larger tables show the first 100 matching rows; CSV downloads include all matches and metadata. Tables do not currently support clicking column headers to sort.

The server binds to `127.0.0.1`. There are no credentials, uploads, external data writes or public deployment. Streamlit usage telemetry is disabled. Per-session filters are isolated; expensive read-only data loading is cached with file-version invalidation and bounded entries.

## Verification

Run `python -m pytest` after installing both `requirements-ui.txt` and `requirements-dev.txt`. UI checks use Streamlit AppTest to exercise all four views, channel/date filters, empty selections, reset and search. Financial tests compare the UI aggregations against the independent fixture, including missing costs and zero spend. Browser checks verify the actual charts and controls in the running app. Release-specific results are recorded separately in the UI validation report.
