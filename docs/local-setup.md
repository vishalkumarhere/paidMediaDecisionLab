# Local project setup

The active project directory is `C:\Users\visha\Documents\Codex\Projects\luxe-cafe-paid-media-decision-lab`.

This folder has its own Python 3.12 virtual environment, pinned dependencies, local Git repository and verified sample data. It does not depend on the earlier task workspace. The original working copy has been retained as a backup; make future edits in this permanent folder.

Run these commands from this folder in PowerShell. The environment is already installed, so activation and reinstallation are unnecessary.

```powershell
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\python.exe -m luxe_lab build --output data/my-next-run
```

Choose a fresh output folder for each build. The supplied `data/demo-final` sample is ready for inspection.

All 27 tests passed from this location using its own environment. All 17 supplied data files match their release checksums, and dependency validation passed. Details are in `docs/validation-report.json`.

The Streamlit data interface has now been added. Start it with `.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py`, then open `http://127.0.0.1:8501`. Its dependencies are installed in this project's environment. The UI adds charts, filters, order drill-downs and CSV downloads; the automated recommendation engine is still unimplemented.
