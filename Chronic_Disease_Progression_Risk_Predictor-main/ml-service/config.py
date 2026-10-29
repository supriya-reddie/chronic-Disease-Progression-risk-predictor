"""
Configuration for the CDPRP ML service.

All ML/feature-engineering/model parameters live here or in the frozen
artifacts (feature_columns.json, thresholds.json, *.pkl). Nothing here is
ever read by Node.js - the Node backend only calls this service over HTTP.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/cdprp")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", None)  # if None, taken from URI

MODEL_DIR = Path(os.environ.get("MODEL_DIR", BASE_DIR / "models"))
ACUTE_MODEL_PATH = MODEL_DIR / "acute_model.pkl"
PROGRESSION_MODEL_PATH = MODEL_DIR / "progression_model.pkl"

FEATURE_COLUMNS_PATH = Path(os.environ.get("FEATURE_COLUMNS_PATH", BASE_DIR / "feature_columns.json"))
THRESHOLDS_PATH = Path(os.environ.get("THRESHOLDS_PATH", BASE_DIR / "thresholds.json"))

# Missing-value fill value used at both training and inference time
# (matches prepare_Xy / predict_and_explain in the original training script -
# DO NOT change this without retraining).
MISSING_VALUE_FILL = -999

# How many patients to process per progress-update batch during a batch job.
BATCH_PROGRESS_CHUNK = 25

MODEL_VERSION = os.environ.get("MODEL_VERSION", "chronicare-v1")

HOST = os.environ.get("ML_SERVICE_HOST", "0.0.0.0")
PORT = int(os.environ.get("ML_SERVICE_PORT", "8000"))
