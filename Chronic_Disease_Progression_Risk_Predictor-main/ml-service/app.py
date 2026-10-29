"""
CDPRP ML Service
=================
FastAPI service that owns ALL machine-learning logic for the Chronic
Disease Risk Intelligence Platform:
  - loading the frozen acute_model.pkl / progression_model.pkl (once, at
    startup)
  - feature engineering from raw MongoDB clinical data
  - risk prediction + threshold-based tiering
  - SHAP/occlusion explanations
  - care-management recommendations

Node.js never performs any of the above - it only calls this service and
reads what it writes back to MongoDB.

Run with:
    uvicorn app:app --host 0.0.0.0 --port 8000
"""
import logging
import traceback
from datetime import datetime, timezone

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import db
import feature_engineering
import model_loader
import predictor
from bson import ObjectId   # add this import near your other imports at the top

def _jsonable(value):
    """Recursively convert Mongo/BSON and datetime types into JSON-safe values."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("cdprp-ml.app")

app = FastAPI(title="CDPRP ML Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    try:
        model_loader.load_all()
    except Exception as e:
        logger.error("FATAL: could not load models at startup: %s", e)
        raise
    try:
        db.ping()
        logger.info("MongoDB connection OK.")
    except Exception as e:
        logger.warning("MongoDB not reachable at startup (%s). Will retry on first request.", e)


class BatchRequest(BaseModel):
    job_id: str
    patient_ids: list[str] | None = None


class SinglePatientRequest(BaseModel):
    patient_id: str


@app.get("/health")
def health():
    state = model_loader.get_state()
    mongo_ok = True
    mongo_error = None
    try:
        db.ping()
    except Exception as e:
        mongo_ok = False
        mongo_error = str(e)

    return {
        "status": "ok" if (state["loaded"] and mongo_ok) else "degraded",
        "modelsLoaded": state["loaded"],
        "featureCount": len(state["feature_columns"]) if state["feature_columns"] else 0,
        "mongoConnected": mongo_ok,
        "mongoError": mongo_error,
        "modelVersion": config.MODEL_VERSION,
    }


def _score_patients(patient_ids, job_id=None):
    """Fetch raw data, engineer features, predict, and return prediction docs."""
    patients_df = db.fetch_patients(patient_ids)
    if len(patients_df) == 0:
        return [], 0

    ids = patients_df["Id"].tolist()
    conditions_df = db.fetch_conditions(ids)
    encounters_df = db.fetch_encounters(ids)
    medications_df = db.fetch_medications(ids)
    observations_df = db.fetch_observations(ids)

    cutoff = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None)

    feature_df = feature_engineering.build_feature_dataframe(
        patients_df, conditions_df, encounters_df, medications_df, observations_df, cutoff
    )
    predictions = predictor.run_predictions(feature_df, job_id=job_id)
    return predictions, len(patients_df)


def _run_batch_job(job_id: str, patient_ids):
    logger.info("Starting batch job %s", job_id)
    db.upsert_prediction_job(job_id, status="running", startedAt=datetime.now(timezone.utc))

    try:
        all_ids = patient_ids or db.all_patient_ids()
        total = len(all_ids)
        db.upsert_prediction_job(job_id, total=total)

        chunk_size = max(config.BATCH_PROGRESS_CHUNK, 1)
        successful = 0
        failed = 0

        for start in range(0, total, chunk_size):
            chunk_ids = all_ids[start:start + chunk_size]
            try:
                preds, scored_count = _score_patients(chunk_ids, job_id=job_id)
                inserted = db.save_predictions(preds)
                successful += inserted
                failed += max(0, len(chunk_ids) - inserted)
            except Exception as e:
                logger.error("Chunk starting at %d failed: %s\n%s", start, e, traceback.format_exc())
                failed += len(chunk_ids)

            db.increment_job_progress(job_id, processed_delta=len(chunk_ids))

        db.upsert_prediction_job(
            job_id,
            status="completed",
            successful=successful,
            failed=failed,
            completedAt=datetime.now(timezone.utc),
        )
        logger.info("Batch job %s completed: %d successful, %d failed", job_id, successful, failed)
    except Exception as e:
        logger.error("Batch job %s failed: %s\n%s", job_id, e, traceback.format_exc())
        db.upsert_prediction_job(
            job_id, status="failed", errorMessage=str(e), completedAt=datetime.now(timezone.utc)
        )


@app.post("/predict/batch", status_code=202)
def predict_batch(req: BatchRequest, background_tasks: BackgroundTasks):
    if not model_loader.get_state()["loaded"]:
        raise HTTPException(503, "Models are not loaded.")
    background_tasks.add_task(_run_batch_job, req.job_id, req.patient_ids)
    return {"jobId": req.job_id, "status": "started"}


@app.post("/predict/patient")
def predict_patient(req: SinglePatientRequest):
    if not model_loader.get_state()["loaded"]:
        raise HTTPException(503, "Models are not loaded.")
    try:
        preds, scored_count = _score_patients([req.patient_id])
    except Exception as e:
        logger.error("Single prediction failed for %s: %s\n%s", req.patient_id, e, traceback.format_exc())
        raise HTTPException(500, "Prediction failed: " + str(e))

    if scored_count == 0:
        raise HTTPException(404, "Patient not found in the database.")
    if not preds:
        raise HTTPException(500, "Feature engineering produced no result for this patient.")

    inserted = db.save_predictions(preds)
    if inserted == 0:
        raise HTTPException(500, "Failed to save prediction to MongoDB.")

    return _jsonable(preds[0])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=config.HOST, port=config.PORT, reload=False)
