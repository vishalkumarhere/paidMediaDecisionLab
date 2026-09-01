# Luxe Café Paid Media Decision Lab

An independent marketing analytics portfolio project built around a fictional US Ninja Luxe Café campaign. **All campaigns, customers, sales, media spend and costs are simulated. This is not SharkNinja performance data, an official product, or evidence of marketing lift.**

The question: when two campaigns report similar ROAS, do their returns, costs and data quality justify the same budget decision?

## Interactive dashboard

The project now includes a local Streamlit interface. Open `http://127.0.0.1:8501` while the server is running.

From this project folder in PowerShell:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

The environment on this machine is already installed. `start-app.ps1` starts the same app. Keep its terminal running; Ctrl+C stops it. The server listens on this computer only, not the public internet.

The interface provides four views:

- **Overview:** spend, net revenue, contribution, business ROAS, daily/weekly trends and a campaign scorecard.
- **Campaigns:** contribution comparisons and a per-campaign revenue-to-contribution waterfall.
- **Order economics:** cost/refund breakdowns and exact order-line values.
- **Data & methodology:** filtered tables, literal-text search, CSV downloads, site-wide tracking coverage, definitions and validation results.

Dataset, date, channel and campaign filters are interactive. Unattributed sales are excluded from paid-media reporting by default and can be included explicitly. CSV files preserve the selected dates, information cutoff and dataset hash. The app never reads hidden evaluation labels or modifies data.

Charts use Plotly's browser-side JSON renderer; tables use escaped, read-only HTML with a 100-row preview and complete filtered CSV downloads. Data is read through DuckDB. This design does not load the native PyArrow library, which Windows Application Control blocks on this machine. Security settings have not been changed.

## Foundation: milestones 1 and 2

Implemented: measurement and product contracts; an independently calculated two-campaign example; a seeded generator; 12 typed raw Parquet datasets; information-cutoff staging; order economics; single-credit business attribution; campaign/day and reconciliation datasets; validation; reproducibility manifests and automated tests.

Not implemented: automated recommendations, cohort maturity estimates, forecasting, budget scenarios, workbook exports, deployment or outreach. The data UI is implemented; the original plan's full decision workflow remains future work.

## Run on Windows

Prerequisite: Python 3.12 and internet access for the initial dependency installation. Run from this project folder in PowerShell. No paid services, credentials, ad accounts or API keys are required.

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-ui.txt
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\python.exe -m luxe_lab build --output data/my-first-run
```

If the `py` launcher is unavailable, use the full path to your Python 3.12 executable for the first command. Activation is unnecessary. The virtual environment is machine-specific and intentionally not included in the release archive.

The last command generates, validates and transforms the data in one step. It prints a summary and writes `manifest.json` last. The default seed is 42. The supplied `data/demo-final` folder is a completed sample; choose a new output folder when reproducing it. Existing nonempty run folders are never overwritten.

```powershell
& .\.venv\Scripts\python.exe -m luxe_lab build --seed 43 --output data/seed-43
& .\.venv\Scripts\python.exe -m luxe_lab build --as-of 2026-07-13T12:00:00+00:00 --output data/july-cutoff
```

Each run includes:

- `raw/`: typed simulator source records, including records after the reporting cutoff.
- `processed/`: five analytical datasets restricted to information available at the cutoff.
- `evaluation_only/`: simulator incident labels; never an input to the SQL pipeline.
- `manifest.json`: configuration, runtime, source-code hash, raw and processed hashes, row counts, validations and warnings.

The reporting period is May 4–August 23, 2026: 112 days / 16 weeks, plus 30 days of warmup. The default information cutoff is August 24 at 12:00 UTC. Prices and dates are fictional scenario inputs, not reconstructed business history.

## Read the project

- [Product contract and four view sketches](docs/product-contract.md)
- [Measurement contract](docs/metric-contract.md)
- [Hand-calculated financial example](docs/hand-calculated-example.md)
- [Data dictionary](docs/data-dictionary.md)
- [Architecture, reproducibility and limitations](docs/architecture.md)
- [Validation evidence](docs/validation-report.json)

The UI entry point is `streamlit_app.py`, with read-only calculations, charts and tables in `dashboard/` and the native theme in `.streamlit/config.toml`. Foundation implementation lives in `luxe_lab/`, SQL transformations in `sql/`, versioned assumptions in `config/`, and independent fixtures and tests in `tests/`. Financial values are integer USD cents; ratios are unrounded floating-point values until presentation.

## What this demonstrates

The included fixture gives both campaigns 5.0x business net ROAS. One loses $55 after media while the other contributes $75, because the first has different return and cost economics. This is a demonstrable arithmetic result, not a finding about SharkNinja or evidence that increasing spend would create profit.

The next decision milestone connects these views to explicit data/maturity gates and the first explainable recommendation. No live advertising budget should be changed from this prototype.
