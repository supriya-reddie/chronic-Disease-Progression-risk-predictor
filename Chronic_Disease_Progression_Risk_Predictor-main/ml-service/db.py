"""
MongoDB access layer for the ML service.

The ML service talks to the SAME MongoDB the Node backend writes raw patient
data into (patients, conditions, encounters, medications, observations), and
writes its own outputs back to `predictions` and `prediction_jobs`. It never
goes through Node for data access - that keeps ML logic fully separated from
the API layer while still sharing one source of truth.
"""
import logging
from datetime import datetime, timezone

import pandas as pd
from pymongo import MongoClient, UpdateOne

import config

logger = logging.getLogger("cdprp-ml.db")

_client = None


def get_client():
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=8000)
    return _client


def get_db():
    client = get_client()
    if config.MONGO_DB_NAME:
        return client[config.MONGO_DB_NAME]
    return client.get_default_database()


def ping():
    get_client().admin.command("ping")
    return True


# ---------------------------------------------------------------------------
# Readers - raw clinical data -> pandas DataFrames
# ---------------------------------------------------------------------------

def fetch_patients(patient_ids=None):
    db = get_db()
    query = {"patientId": {"$in": patient_ids}} if patient_ids else {}
    cursor = db.patients.find(query)
    rows = list(cursor)
    if not rows:
        return pd.DataFrame(columns=["Id", "BIRTHDATE", "GENDER", "MARITAL", "INCOME"])
    df = pd.DataFrame(rows)
    df["Id"] = df["patientId"].astype(str)
    df["BIRTHDATE"] = pd.to_datetime(df.get("birthDate"), errors="coerce")
    df["GENDER"] = df.get("gender", "U").fillna("U")
    df["MARITAL"] = df.get("marital")
    df["INCOME"] = pd.to_numeric(df.get("income"), errors="coerce")
    return df


def _fetch_collection_df(collection_name, patient_ids, rename_map, date_cols, desc_col=None):
    db = get_db()
    query = {"patientId": {"$in": patient_ids}} if patient_ids else {}
    rows = list(db[collection_name].find(query))
    if not rows:
        cols = list(rename_map.values())
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df = df.rename(columns=rename_map)
    for c in date_cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    if desc_col and desc_col in df.columns:
        df[desc_col] = df[desc_col].fillna("").astype(str).str.strip()
        df["DESC_LOWER"] = df[desc_col].str.lower()
    return df


def fetch_conditions(patient_ids=None):
    return _fetch_collection_df(
        "conditions",
        patient_ids,
        {"patientId": "PATIENT", "start": "START", "stop": "STOP", "description": "DESCRIPTION"},
        ["START", "STOP"],
        desc_col="DESCRIPTION",
    )


def fetch_encounters(patient_ids=None):
    df = _fetch_collection_df(
        "encounters",
        patient_ids,
        {
            "patientId": "PATIENT",
            "start": "START",
            "stop": "STOP",
            "encounterClass": "ENCOUNTERCLASS",
            "description": "DESCRIPTION",
        },
        ["START", "STOP"],
    )
    if "ENCOUNTERCLASS" in df.columns:
        df["ENCOUNTERCLASS"] = df["ENCOUNTERCLASS"].fillna("").astype(str).str.lower().str.strip()
    return df


def fetch_medications(patient_ids=None):
    return _fetch_collection_df(
        "medications",
        patient_ids,
        {"patientId": "PATIENT", "start": "START", "stop": "STOP", "description": "DESCRIPTION", "dispenses": "DISPENSES"},
        ["START", "STOP"],
    )


def fetch_observations(patient_ids=None):
    df = _fetch_collection_df(
        "observations",
        patient_ids,
        {
            "patientId": "PATIENT",
            "date": "DATE",
            "category": "CATEGORY",
            "description": "DESCRIPTION",
            "valueNumeric": "VALUE_NUMERIC",
        },
        ["DATE"],
        desc_col="DESCRIPTION",
    )
    if "CATEGORY" in df.columns:
        df["CATEGORY"] = df["CATEGORY"].fillna("").astype(str).str.lower()
    if "VALUE_NUMERIC" in df.columns:
        df["VALUE_NUMERIC"] = pd.to_numeric(df["VALUE_NUMERIC"], errors="coerce")
    return df


def count_patients():
    return get_db().patients.count_documents({})


def all_patient_ids():
    return get_db().patients.distinct("patientId")


# ---------------------------------------------------------------------------
# Writers - predictions + job status
# ---------------------------------------------------------------------------

def upsert_prediction_job(job_id, **fields):
    db = get_db()
    fields["jobId"] = job_id
    fields.setdefault("updatedAt", datetime.now(timezone.utc))
    db.predictionjobs.update_one({"jobId": job_id}, {"$set": fields}, upsert=True)


def increment_job_progress(job_id, processed_delta=0, successful_delta=0, failed_delta=0):
    db = get_db()
    db.predictionjobs.update_one(
        {"jobId": job_id},
        {
            "$inc": {
                "processed": processed_delta,
                "successful": successful_delta,
                "failed": failed_delta,
            },
            "$set": {"updatedAt": datetime.now(timezone.utc)},
        },
    )


def save_predictions(prediction_docs):
    """Bulk-write prediction results. One doc per patient per run."""
    if not prediction_docs:
        return 0
    db = get_db()
    docs_to_insert = [dict(d) for d in prediction_docs]  # copies — insert_many()
                                                            # mutates whatever list
                                                            # you pass it, so never
                                                            # hand it the originals
    for d in docs_to_insert:
        d.setdefault("createdAt", datetime.now(timezone.utc))
        d.setdefault("updatedAt", datetime.now(timezone.utc))
        d.setdefault("careStatus", "Pending")
    result = db.predictions.insert_many(docs_to_insert, ordered=False)
    return len(result.inserted_ids)
