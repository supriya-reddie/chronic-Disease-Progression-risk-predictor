"""
Runs the frozen acute_model.pkl / progression_model.pkl on an engineered
feature DataFrame, classifies risk tiers using thresholds.json, generates
per-patient explanations, and builds care-management recommendations.

This is the only place predictions are produced. Node.js never computes a
prediction; it only reads what this module has already written to MongoDB.
"""
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import config
import explainer
import feature_engineering
import model_loader
import recommendations
from risk_classifier import assign_risk_tier, get_thresholds

logger = logging.getLogger("cdprp-ml.predictor")


def run_predictions(feature_df: pd.DataFrame, job_id: str = None):
    """
    feature_df: one row per patient, output of
    feature_engineering.build_feature_dataframe(). Must contain
    'patient_id' plus every column in feature_columns.json.

    Returns a list of dicts shaped for the Prediction Mongoose schema.
    """
    if len(feature_df) == 0:
        return []

    state = model_loader.get_state()
    feature_cols = state["feature_columns"]
    thresholds_cfg = state["thresholds"]
    acute_model = state["acute_model"]
    progression_model = state["progression_model"]

    validation = model_loader.validate_feature_vector(feature_df.columns)
    logger.info("Feature vector validated: %s", validation)

    # Ensure exact column order matches feature_columns.json (authoritative).
    for col in feature_cols:
        if col not in feature_df.columns:
            feature_df[col] = np.nan
    X_df = feature_df[feature_cols].copy()
    for col in X_df.columns:
        X_df[col] = pd.to_numeric(X_df[col], errors="coerce")

    # Same missing-value strategy used at training time.
    X_arr = X_df.fillna(config.MISSING_VALUE_FILL).values

    acute_proba = acute_model.predict_proba(X_arr)[:, 1]
    progression_proba = progression_model.predict_proba(X_arr)[:, 1]

    a_low, a_high = get_thresholds(thresholds_cfg, "acute")
    p_low, p_high = get_thresholds(thresholds_cfg, "progression")

    acute_contrib, acute_method = explainer.compute_contributions_batch(acute_model, X_arr, feature_cols)
    prog_contrib, prog_method = explainer.compute_contributions_batch(progression_model, X_arr, feature_cols)
    logger.info("Explanation methods used: acute=%s, progression=%s", acute_method, prog_method)

    results = []
    now = datetime.now(timezone.utc)

    for i in range(len(feature_df)):
        patient_id = feature_df.iloc[i]["patient_id"]
        x_row = X_arr[i]
        a_prob = float(acute_proba[i])
        p_prob = float(progression_proba[i])
        a_tier = assign_risk_tier(a_prob, a_low, a_high)
        p_tier = assign_risk_tier(p_prob, p_low, p_high)

        a_expl = explainer.explain_row(acute_contrib[i], x_row, feature_cols, "acute-event")
        p_expl = explainer.explain_row(prog_contrib[i], x_row, feature_cols, "progression")

        feat_dict = {feature_cols[j]: (None if x_row[j] == config.MISSING_VALUE_FILL else float(x_row[j]))
                     for j in range(len(feature_cols))}
        completeness_score, completeness_cat = feature_engineering.compute_data_completeness(
            {feature_cols[j]: x_row[j] if x_row[j] != config.MISSING_VALUE_FILL else np.nan for j in range(len(feature_cols))}
        )

        recs = recommendations.get_recommendations(a_tier, p_tier, feat_dict)

        results.append({
            "patientId": patient_id,
            "jobId": job_id,
            "predictionDate": now,
            "acuteProbability": round(a_prob, 4),
            "acuteRisk": a_tier,
            "progressionProbability": round(p_prob, 4),
            "progressionRisk": p_tier,
            "features": feat_dict,
            "acuteExplanation": a_expl["explanation"],
            "acuteTopFactors": a_expl["top_factors"],
            "progressionExplanation": p_expl["explanation"],
            "progressionTopFactors": p_expl["top_factors"],
            "recommendations": recs,
            "dataCompletenessScore": completeness_score,
            "dataCompletenessCategory": completeness_cat,
            "modelVersion": config.MODEL_VERSION,
        })

    return results
