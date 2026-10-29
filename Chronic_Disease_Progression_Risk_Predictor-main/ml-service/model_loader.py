"""
Loads the frozen acute_model.pkl / progression_model.pkl, feature_columns.json
and thresholds.json exactly ONCE at service startup. No retraining, no
modification of these artifacts happens anywhere in this service.
"""
import json
import logging
import pickle

import config

logger = logging.getLogger("cdprp-ml.model_loader")

_state = {
    "acute_model": None,
    "progression_model": None,
    "feature_columns": None,
    "thresholds": None,
    "loaded": False,
}


def load_all():
    if _state["loaded"]:
        return _state

    logger.info("Loading feature_columns.json from %s", config.FEATURE_COLUMNS_PATH)
    with open(config.FEATURE_COLUMNS_PATH, "r") as f:
        feature_columns = json.load(f)

    logger.info("Loading thresholds.json from %s", config.THRESHOLDS_PATH)
    with open(config.THRESHOLDS_PATH, "r") as f:
        thresholds = json.load(f)

    logger.info("Loading acute_model.pkl from %s", config.ACUTE_MODEL_PATH)
    with open(config.ACUTE_MODEL_PATH, "rb") as f:
        acute_model = pickle.load(f)

    logger.info("Loading progression_model.pkl from %s", config.PROGRESSION_MODEL_PATH)
    with open(config.PROGRESSION_MODEL_PATH, "rb") as f:
        progression_model = pickle.load(f)

    _state.update({
        "acute_model": acute_model,
        "progression_model": progression_model,
        "feature_columns": feature_columns,
        "thresholds": thresholds,
        "loaded": True,
    })
    logger.info(
        "Models loaded. Feature count = %d (acute threshold=%.4f, progression threshold=%.4f)",
        len(feature_columns),
        thresholds["acute"]["selected"],
        thresholds["progression"]["selected"],
    )
    return _state


def get_state():
    if not _state["loaded"]:
        load_all()
    return _state


def validate_feature_vector(df_columns):
    """
    Section 9 validation: confirm the engineered feature set exactly matches
    feature_columns.json (same names, same count). Raises ValueError if not.
    """
    expected = set(get_state()["feature_columns"])
    actual = set(df_columns)
    missing = expected - actual
    unexpected = actual - expected - {"patient_id", "cutoff_date"}
    if missing:
        raise ValueError("Feature vector is missing required columns: " + ", ".join(sorted(missing)))
    return {
        "expected_count": len(expected),
        "actual_count": len(actual & expected),
        "unexpected_columns": sorted(unexpected),
    }
