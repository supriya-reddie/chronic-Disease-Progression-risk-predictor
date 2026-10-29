# ChroniCare Intelligence — Chronic Disease Risk Intelligence Platform

A payer-side application built around your **existing, frozen** ML artifacts
(`acute_model.pkl`, `progression_model.pkl`, `feature_columns.json`,
`thresholds.json`). No retraining, no modified training logic, no
precomputed-Excel/CSV shortcuts — every prediction shown in the UI is
produced live by the real models running in a Python service.

```
React  →  Node/Express  →  MongoDB  →  Python ML service  →  PKL models  →  MongoDB  →  Node API  →  React
```

---

## 1. Important note on data

Your upload (`ML.zip`) contained the trained model artifacts and evaluation
outputs, but **not** the raw 1,500-patient CSVs (`web_patients_1500.csv`,
`web_conditions_1500.csv`, etc.) referenced in `chronicare_model.py`. Since
the brief explicitly forbids using `unseen_1500_predictions.csv` as the
runtime data source, this project ships with:

- `sample-data/` — a small **synthetic** demo cohort (220 patients) shaped
  exactly like the CSVs the import pipeline expects. It exists only so you
  can run the whole stack immediately and see it work end-to-end. It is
  **not** your real population and risk numbers from it are not meaningful.
- A CSV import pipeline that works identically with your real files —
  just point `CSV_DATA_DIR` (or `--dir`) at the folder containing your real
  `patients/conditions/encounters/medications/observations` CSVs and
  re-import.

## 2. What was fixed vs. the original training script

- **Explanations were always zero, and SHAP caused timeouts.**
  `acute_model.pkl` / `progression_model.pkl` are `HistGradientBoostingClassifier`
  models wrapped in `CalibratedClassifierCV`. That estimator has no
  `feature_importances_`, and the original fallback logic returned all-zero
  contributions (`test_predictions.csv` shows this: every row says
  "Insufficient signal..."). An initial fix used SHAP, but SHAP's `numba`
  dependency has a slow first-call JIT warm-up (20-60+ seconds) that can
  time out a live single-patient request. `ml-service/explainer.py` now
  uses a fast, dependency-free **occlusion importance** instead: each
  candidate feature is temporarily masked and the model is re-scored; the
  drop in predicted probability is that feature's contribution *for that
  patient*, computed fresh from the real frozen model every time. Only a
  curated set of clinically-labeled features are ever considered, so the
  UI never shows a raw internal code (e.g. `enc_90d`) — every displayed
  factor has a plain-language label.
- **178 features, not 35.** The brief describes a 35-feature model;
  `feature_columns.json` actually lists 178. The application uses the file
  as authoritative, per your own instructions (section 9), and validates
  the engineered vector against it before every prediction
  (`model_loader.validate_feature_vector`).
- **One current prediction per patient**, not many historical cutoffs.
  Training scored patients at many historical cutoffs to build a labeled
  dataset. A live risk-scoring app needs one current answer per patient, so
  the service engineers features at `cutoff = now` using the *identical*
  feature-engineering functions from `chronicare_model.py` (ported
  unmodified into `ml-service/feature_engineering.py`).

## 3. Architecture

```
CDPRP/
  backend/       Node.js + Express + MongoDB. Patient CRUD, CSV import,
                 batch-job orchestration, dashboard aggregation.
                 Contains ZERO ML/feature-engineering/model code.
  ml-service/    Python + FastAPI. Loads the frozen PKL models once at
                 startup, engineers features from MongoDB, runs inference,
                 computes explanations, writes predictions back to Mongo.
  frontend/      React + Vite. Dashboard, Patients, Patient Detail, Risk
                 Analytics, High-Risk Patients, Care Management,
                 Prediction History.
  sample-data/   Synthetic demo CSVs (see note above).
```

Node and the ML service both connect directly to MongoDB. Node triggers a
batch job and polls its status; the ML service does the actual data
fetch → feature engineering → prediction → write-back, entirely on its own.

**Single-patient "Re-score Patient" fails or times out** — this was caused
by `shap`/`numba` in `requirements.txt`: numba's first-call JIT warm-up can
take 20-60+ seconds, longer than Node's request timeout. Both have been
removed; explanations now use a fast, dependency-free occlusion method
(see `ml-service/explainer.py`). Re-run `pip install -r requirements.txt`
in a fresh venv to pick this up. Node's timeout to the ML service was also
raised to 60s as a safety margin (`backend/services/mlServiceClient.js`).

## 3.5 Troubleshooting

**`ValueError: <class 'numpy.random._pcg64.PCG64'> is not a known BitGenerator module`**
on ML-service startup — your `acute_model.pkl` / `progression_model.pkl` were
pickled under NumPy 2.x, and something in your environment resolved to
NumPy 1.x, which uses an incompatible pickle format for its random-state
objects. Fix: make sure you're installing from the `requirements.txt` in
this zip (it pins `numpy>=2.0.0`), and if you have a stale virtualenv,
recreate it:
```bash
cd ml-service
rmdir /s /q venv          # Windows PowerShell: Remove-Item -Recurse -Force venv
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -c "import numpy; print(numpy.__version__)"   # must print 2.x
uvicorn app:app --reload --port 8000
```

**PowerShell doesn't support `&&`** — the README's Unix-style
`cmd1 && cmd2` examples don't work in PowerShell. Run each command on its
own line instead, or use `;` as a separator, e.g.:
```powershell
python -m venv venv; .\venv\Scripts\Activate.ps1
```

**`python3` not found on Windows** — use `python` instead of `python3`
(Windows's Python launcher is usually just `python`).

## 4. Running it

### Prerequisites
- Node.js 18+
- Python 3.10+
- MongoDB running locally at `mongodb://localhost:27017`

**1. MongoDB** — have an instance running.

**2. ML service**
```bash
cd ml-service
python -m venv venv
source venv/bin/activate      # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

**3. Backend**
```bash
cd backend
cp .env.example .env      # adjust if needed
npm install
npm run seed               # imports sample-data/ into MongoDB
npm run dev                # or: npm start
```

**4. Frontend**
```bash
cd frontend
cp .env.example .env
npm install
npm run dev                 # http://localhost:5173
```

**5. Run a risk assessment** — click "Run Risk Assessment" on the
Dashboard, or:
```bash
curl -X POST http://localhost:5000/api/predictions/run-batch
```

### Importing your real 1,500 patients
A `backend/data/` folder is included for this. Copy your 5 CSVs into it
using these exact names (matches what `seed/runImport.js` looks for
automatically):
```
backend/data/
    web_patients_1500.csv
    web_conditions_1500.csv
    web_encounters_1500.csv
    web_medications_1500.csv
    web_observations_1500.csv
```
Then, from `backend/`:
```bash
node seed/runImport.js
```
`CSV_DATA_DIR` in `.env` already defaults to `../data` (relative to
`backend/seed/`, i.e. `backend/data/`), so no extra flags are needed. To
import from somewhere else instead, pass `--dir /absolute/path`.

## 5. API reference

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Mongo + ML service reachability |
| GET | `/api/patients` | Paginated patient list, filterable by risk/gender/search |
| GET | `/api/patients/:patientId` | Patient profile + latest prediction + history |
| GET | `/api/patients/:patientId/timeline` | Chronological clinical timeline |
| POST | `/api/predictions/run-batch` | Kick off a batch assessment for all patients |
| GET | `/api/predictions/job/:jobId` | Batch job status (for polling) |
| GET | `/api/predictions/jobs` | Recent batch job history |
| POST | `/api/predictions/patient/:patientId/run` | Score a single patient on demand |
| GET | `/api/predictions/:patientId` | Latest prediction for a patient |
| GET | `/api/dashboard/summary` | Aggregate stats + chart data |
| GET | `/api/high-risk-patients` | All patients flagged HIGH on either model |
| GET | `/api/care-management` | Care-management outreach queue |
| PATCH | `/api/care-management/:predictionId/status` | Update a queue item's status |

## 6. Validation checklist (from the brief)

- [x] Patients import into MongoDB from raw CSV (works with real or sample data)
- [x] Feature engineering runs in Python only, ported unmodified from `chronicare_model.py`
- [x] Feature vector validated against `feature_columns.json` before every prediction
- [x] Both frozen PKL models load once at ML-service startup, never retrained
- [x] Single-patient and full-batch prediction both implemented and tested against the real models
- [x] Predictions, explanations, and recommendations stored in MongoDB (`predictions` collection)
- [x] Dashboard / patient pages read only from MongoDB, never from the Excel/CSV outputs
- [x] Thresholds come only from `thresholds.json` — never hard-coded in Node or React
- [x] `unseen_1500_predictions.csv` is not read anywhere at runtime

## 7. Disclaimer

This platform produces **risk predictions only** — not a diagnosis and not
treatment advice. All recommended actions are care-management workflow
suggestions; clinical decisions require human review.
