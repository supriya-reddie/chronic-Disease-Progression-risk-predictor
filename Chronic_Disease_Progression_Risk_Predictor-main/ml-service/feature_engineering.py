"""
Feature engineering for the CHRONICARE acute-event and progression models.

This module is a direct adaptation of the feature engineering logic in the
original training script (chronicare_model.py, sections 6-7). The keyword
dictionaries and windowed-aggregation formulas are reproduced EXACTLY as
they were during training so that a patient's feature vector at inference
time is computed the same way it was when the models were fit. Do not
change these definitions without retraining acute_model.pkl /
progression_model.pkl.

The only real difference from the training script: training built many
historical cutoffs per patient to construct a labeled dataset. This service
builds ONE feature row per patient at cutoff = now (their current state),
which is what a live risk-scoring application needs.
"""
import logging
from datetime import timedelta

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger("cdprp-ml.features")

# ============================================================
# EXACT KEYWORD DICTIONARIES (DO NOT MODIFY - must match training)
# ============================================================

CHRONIC_KEYWORDS = {
    "has_diabetes":     ["diabetes mellitus type 2"],
    "has_prediabetes":  ["prediabetes"],
    "has_hypertension": ["essential hypertension"],
    "has_chf":          ["heart failure"],
    "has_ckd":          ["chronic kidney disease", "end-stage renal disease"],
    "has_copd":         ["chronic obstructive bronchitis", "pulmonary emphysema"],
    "has_cad":          ["ischemic heart disease", "myocardial infarction", "coronary artery bypass"],
    "has_asthma":       ["asthma"],
    "has_afib":         ["atrial fibrillation"],
}

DIABETIC_COMPLICATION_KEYWORDS = [
    "kidney due to diabetes",
    "microalbuminuria due to type 2 diabetes",
    "proteinuria due to type 2 diabetes",
    "neuropathy due to type 2 diabetes",
    "retinopathy due to type 2 diabetes",
    "blindness due to diabetes",
]

CKD_STAGE_MAP = {
    "chronic kidney disease stage 1": 1,
    "chronic kidney disease stage 2": 2,
    "chronic kidney disease stage 3": 3,
    "chronic kidney disease stage 4": 4,
    "end-stage renal disease":        5,
}

SDOH_KEYWORDS = {
    "sdoh_social_isolation":   ["social isolation", "limited social contact"],
    "sdoh_housing_insecurity": ["homeless", "housing unsatisfactory"],
    "sdoh_transport_barrier":  ["lack of access to transportation", "transport problem"],
    "sdoh_unemployment":       ["unemployed", "not in labor force"],
    "sdoh_violence_exposure":  ["victim of intimate partner abuse", "reports of violence"],
    "sdoh_financial_stress":   ["stress (finding)"],
}

LAB_FEATURES = {
    "gfr":        ["glomerular filtration rate"],
    "creatinine": ["creatinine [mass/volume] in blood", "creatinine [mass/volume] in serum"],
    "hba1c":      ["hemoglobin a1c"],
    "glucose":    ["glucose [mass/volume] in blood", "glucose [mass/volume] in serum"],
    "bun":        ["urea nitrogen [mass/volume] in blood"],
    "potassium":  ["potassium [moles/volume] in blood", "potassium [moles/volume] in serum"],
    "sodium":     ["sodium [moles/volume] in blood", "sodium [moles/volume] in serum"],
}

VITAL_KEYWORDS = {
    "systolic_bp":  ["systolic blood pressure"],
    "diastolic_bp": ["diastolic blood pressure"],
    "weight":       ["body weight"],
    "heart_rate":   ["heart rate"],
    "bmi_vital":    ["body mass index"],
}

ACUTE_ENCOUNTER_CLASSES = {"emergency", "urgentcare", "inpatient"}


# ============================================================
# Helpers
# ============================================================

def matches_any_keyword(desc_lower_series, keywords):
    mask = pd.Series(False, index=desc_lower_series.index)
    for kw in keywords:
        mask = mask | desc_lower_series.str.contains(kw.lower(), na=False, regex=False)
    return mask


def get_ckd_stage(desc_lower):
    for kw, stage in CKD_STAGE_MAP.items():
        if kw in desc_lower:
            return stage
    return 0


def compute_slope(values, times_days):
    if len(values) < 2:
        return 0.0
    try:
        slope, _, _, _, _ = stats.linregress(times_days, values)
        return float(slope) if not np.isnan(slope) else 0.0
    except Exception:
        return 0.0


# ============================================================
# Per-category feature functions (identical logic to training)
# ============================================================

def lab_features_for_patient(obs_df, cutoff):
    feats = {}
    suffixes = ["_latest", "_prev", "_mean", "_min", "_max", "_std", "_change", "_slope", "_count", "_days_since"]
    for lab in LAB_FEATURES:
        for s in suffixes:
            feats["lab_" + lab + s] = np.nan
    if obs_df is None or len(obs_df) == 0:
        return feats
    hist = obs_df[(obs_df["DATE"] < cutoff) & (obs_df["CATEGORY"] == "laboratory")]
    for lab_name, keywords in LAB_FEATURES.items():
        lab_mask = pd.Series(False, index=hist.index)
        for kw in keywords:
            lab_mask = lab_mask | hist["DESC_LOWER"].str.contains(kw, na=False, regex=False)
        lab_rows = hist[lab_mask].dropna(subset=["VALUE_NUMERIC"]).sort_values("DATE")
        prefix = "lab_" + lab_name
        if len(lab_rows) == 0:
            continue
        vals = lab_rows["VALUE_NUMERIC"].values
        times = lab_rows["DATE"].values
        feats[prefix + "_latest"] = float(vals[-1])
        feats[prefix + "_prev"] = float(vals[-2]) if len(vals) >= 2 else np.nan
        feats[prefix + "_mean"] = float(np.mean(vals))
        feats[prefix + "_min"] = float(np.min(vals))
        feats[prefix + "_max"] = float(np.max(vals))
        feats[prefix + "_std"] = float(np.std(vals)) if len(vals) >= 2 else 0.0
        feats[prefix + "_change"] = float(vals[-1] - vals[0]) if len(vals) >= 2 else 0.0
        feats[prefix + "_count"] = len(vals)
        feats[prefix + "_days_since"] = (cutoff - lab_rows["DATE"].iloc[-1]).days
        if len(vals) >= 3:
            days_arr = np.array([(t - times[0]) / np.timedelta64(1, "D") for t in times])
            feats[prefix + "_slope"] = compute_slope(vals, days_arr)
        else:
            feats[prefix + "_slope"] = 0.0
    return feats


def vital_features_for_patient(obs_df, cutoff):
    feats = {}
    for v in VITAL_KEYWORDS:
        for s in ["_latest", "_prev", "_change", "_count"]:
            feats["vital_" + v + s] = np.nan
    if obs_df is None or len(obs_df) == 0:
        return feats
    hist = obs_df[(obs_df["DATE"] < cutoff) & (obs_df["CATEGORY"] == "vital-signs")]
    for v_name, keywords in VITAL_KEYWORDS.items():
        v_mask = pd.Series(False, index=hist.index)
        for kw in keywords:
            v_mask = v_mask | hist["DESC_LOWER"].str.contains(kw, na=False, regex=False)
        v_rows = hist[v_mask].dropna(subset=["VALUE_NUMERIC"]).sort_values("DATE")
        prefix = "vital_" + v_name
        if len(v_rows) == 0:
            continue
        vals = v_rows["VALUE_NUMERIC"].values
        feats[prefix + "_latest"] = float(vals[-1])
        feats[prefix + "_prev"] = float(vals[-2]) if len(vals) >= 2 else np.nan
        feats[prefix + "_change"] = float(vals[-1] - vals[-2]) if len(vals) >= 2 else 0.0
        feats[prefix + "_count"] = len(vals)
    return feats


def encounter_features_for_patient(enc_df, cutoff):
    feats = {}
    for w in [30, 90, 180, 365]:
        for k in ["total", "ed", "uc", "inp", "acute"]:
            feats["enc_" + k + "_" + str(w) + "d"] = 0
    feats.update({"days_since_last_enc": np.nan, "days_since_last_ed": np.nan,
                  "days_since_last_inp": np.nan, "days_since_last_uc": np.nan,
                  "util_trend_90v365": 0.0, "util_accel": 0.0,
                  "total_enc_ever": 0, "ed_enc_ever": 0, "inp_enc_ever": 0})
    if enc_df is None or len(enc_df) == 0:
        return feats
    hist = enc_df[enc_df["START"] < cutoff]
    cls = hist["ENCOUNTERCLASS"]
    for w in [30, 90, 180, 365]:
        cutoff_w = cutoff - timedelta(days=w)
        window = hist[hist["START"] >= cutoff_w]
        feats["enc_total_" + str(w) + "d"] = len(window)
        feats["enc_ed_" + str(w) + "d"] = (window["ENCOUNTERCLASS"] == "emergency").sum()
        feats["enc_uc_" + str(w) + "d"] = (window["ENCOUNTERCLASS"] == "urgentcare").sum()
        feats["enc_inp_" + str(w) + "d"] = (window["ENCOUNTERCLASS"] == "inpatient").sum()
        feats["enc_acute_" + str(w) + "d"] = window["ENCOUNTERCLASS"].isin(ACUTE_ENCOUNTER_CLASSES).sum()
    feats["total_enc_ever"] = len(hist)
    feats["ed_enc_ever"] = (cls == "emergency").sum()
    feats["inp_enc_ever"] = (cls == "inpatient").sum()
    if len(hist) > 0:
        feats["days_since_last_enc"] = (cutoff - hist["START"].max()).days
        ed_h = hist[cls == "emergency"]
        feats["days_since_last_ed"] = (cutoff - ed_h["START"].max()).days if len(ed_h) > 0 else np.nan
        inp_h = hist[cls == "inpatient"]
        feats["days_since_last_inp"] = (cutoff - inp_h["START"].max()).days if len(inp_h) > 0 else np.nan
        uc_h = hist[cls == "urgentcare"]
        feats["days_since_last_uc"] = (cutoff - uc_h["START"].max()).days if len(uc_h) > 0 else np.nan
    enc_90 = feats["enc_total_90d"]
    enc_365 = feats["enc_total_365d"] + 1e-6
    enc_180 = feats["enc_total_180d"] + 1e-6
    feats["util_trend_90v365"] = (enc_90 / 90.0) / (enc_365 / 365.0)
    feats["util_accel"] = (enc_90 / 90.0) - (enc_180 / 180.0)
    return feats


def medication_features_for_patient(med_df, cutoff):
    feats = {"med_total_ever": 0, "med_unique_ever": 0, "med_active_approx": 0,
             "med_starts_30d": 0, "med_starts_90d": 0, "med_starts_180d": 0,
             "med_stops_90d": 0, "med_stops_180d": 0, "med_changes_90d": 0,
             "med_churn_90d": 0.0, "med_burden_total": 0, "med_gaps_count": 0}
    if med_df is None or len(med_df) == 0:
        return feats
    hist = med_df[med_df["START"] < cutoff]
    if len(hist) == 0:
        return feats
    feats["med_total_ever"] = len(hist)
    feats["med_unique_ever"] = hist["DESCRIPTION"].nunique()
    active = hist[(hist["STOP"].isna()) | (hist["STOP"] >= cutoff)]
    feats["med_active_approx"] = len(active)
    for w in [30, 90, 180]:
        feats["med_starts_" + str(w) + "d"] = len(hist[hist["START"] >= (cutoff - timedelta(days=w))])
    for w in [90, 180]:
        stops = hist[(hist["STOP"].notna()) & (hist["STOP"] >= (cutoff - timedelta(days=w))) & (hist["STOP"] < cutoff)]
        feats["med_stops_" + str(w) + "d"] = len(stops)
    feats["med_changes_90d"] = feats["med_starts_90d"] + feats["med_stops_90d"]
    feats["med_churn_90d"] = feats["med_changes_90d"] / (feats["med_starts_90d"] + 1e-6)
    if "DISPENSES" in hist.columns:
        feats["med_burden_total"] = int(pd.to_numeric(hist["DISPENSES"], errors="coerce").fillna(0).sum())
    else:
        feats["med_burden_total"] = len(hist)
    feats["med_gaps_count"] = feats["med_stops_90d"]
    return feats


def diagnosis_features_for_patient(cond_df, cutoff):
    feats = {"diag_total": 0, "diag_chronic_count": 0,
             "diag_30d": 0, "diag_90d": 0, "diag_180d": 0, "diag_365d": 0,
             "diag_new_90d": 0, "diag_accel": 0.0,
             "days_since_first_chronic": np.nan, "days_since_latest_diag": np.nan}
    if cond_df is None or len(cond_df) == 0:
        return feats
    hist = cond_df[cond_df["START"] < cutoff]
    if len(hist) == 0:
        return feats
    feats["diag_total"] = len(hist)
    chronic_mask = pd.Series(False, index=hist.index)
    for kws in CHRONIC_KEYWORDS.values():
        chronic_mask = chronic_mask | matches_any_keyword(hist["DESC_LOWER"], kws)
    feats["diag_chronic_count"] = int(chronic_mask.sum())
    for w in [30, 90, 180, 365]:
        feats["diag_" + str(w) + "d"] = len(hist[hist["START"] >= (cutoff - timedelta(days=w))])
    feats["diag_new_90d"] = feats["diag_90d"]
    rate_90 = feats["diag_90d"] / 90.0
    rate_365 = feats["diag_365d"] / 365.0
    feats["diag_accel"] = rate_90 - rate_365
    chronic_hist = hist[chronic_mask]
    if len(chronic_hist) > 0:
        feats["days_since_first_chronic"] = (cutoff - chronic_hist["START"].min()).days
    feats["days_since_latest_diag"] = (cutoff - hist["START"].max()).days
    return feats


def chronic_condition_features(cond_df, cutoff):
    feats = {feat: 0 for feat in CHRONIC_KEYWORDS}
    feats.update({"comorbidity_count": 0, "chronic_duration_days": np.nan,
                  "days_since_last_chronic_dx": np.nan, "recent_new_chronic_90d": 0})
    if cond_df is None or len(cond_df) == 0:
        return feats
    hist = cond_df[cond_df["START"] < cutoff]
    for feat_name, keywords in CHRONIC_KEYWORDS.items():
        feats[feat_name] = int(matches_any_keyword(hist["DESC_LOWER"], keywords).any())
    feats["comorbidity_count"] = sum(feats[f] for f in CHRONIC_KEYWORDS)
    all_chronic_mask = pd.Series(False, index=hist.index)
    for kws in CHRONIC_KEYWORDS.values():
        all_chronic_mask = all_chronic_mask | matches_any_keyword(hist["DESC_LOWER"], kws)
    chronic_hist = hist[all_chronic_mask]
    if len(chronic_hist) > 0:
        feats["chronic_duration_days"] = (cutoff - chronic_hist["START"].min()).days
        feats["days_since_last_chronic_dx"] = (cutoff - chronic_hist["START"].max()).days
    recent = chronic_hist[chronic_hist["START"] >= (cutoff - timedelta(days=90))] if len(chronic_hist) > 0 else pd.DataFrame()
    feats["recent_new_chronic_90d"] = len(recent)
    return feats


def ckd_features_for_patient(cond_df, cutoff):
    feats = {"ckd_stage_current": 0, "ckd_stage_prev": 0, "ckd_stage_change": 0,
             "ckd_stage_increased": 0, "days_since_ckd_dx": np.nan,
             "days_since_latest_ckd": np.nan, "ckd_activity_90d": 0, "ckd_total_records": 0}
    if cond_df is None or len(cond_df) == 0:
        return feats
    hist = cond_df[cond_df["START"] < cutoff]
    if len(hist) == 0:
        return feats
    ckd_mask = pd.Series(False, index=hist.index)
    for kw in CKD_STAGE_MAP:
        ckd_mask = ckd_mask | hist["DESC_LOWER"].str.contains(kw, na=False, regex=False)
    ckd_rows = hist[ckd_mask].copy()
    if len(ckd_rows) == 0:
        return feats
    ckd_rows["STAGE"] = ckd_rows["DESC_LOWER"].apply(get_ckd_stage)
    ckd_rows = ckd_rows[ckd_rows["STAGE"] > 0].sort_values("START")
    if len(ckd_rows) == 0:
        return feats
    feats["ckd_total_records"] = len(ckd_rows)
    feats["days_since_ckd_dx"] = (cutoff - ckd_rows["START"].min()).days
    feats["days_since_latest_ckd"] = (cutoff - ckd_rows["START"].max()).days
    stages = ckd_rows["STAGE"].values
    feats["ckd_stage_current"] = int(stages[-1])
    feats["ckd_stage_prev"] = int(stages[-2]) if len(stages) >= 2 else int(stages[-1])
    feats["ckd_stage_change"] = int(stages[-1] - stages[0])
    feats["ckd_stage_increased"] = int(stages[-1] > stages[0])
    recent_ckd = ckd_rows[ckd_rows["START"] >= (cutoff - timedelta(days=90))]
    feats["ckd_activity_90d"] = len(recent_ckd)
    return feats


def diabetes_features_for_patient(cond_df, cutoff):
    feats = {"diab_duration_days": np.nan, "known_complication_count": 0,
             "days_since_latest_complication": np.nan, "diab_activity_90d": 0}
    if cond_df is None or len(cond_df) == 0:
        return feats
    hist = cond_df[cond_df["START"] < cutoff]
    if len(hist) == 0:
        return feats
    diab_mask = hist["DESC_LOWER"].str.contains("diabetes mellitus type 2", na=False, regex=False)
    diab_rows = hist[diab_mask]
    if len(diab_rows) > 0:
        feats["diab_duration_days"] = (cutoff - diab_rows["START"].min()).days
    comp_mask = pd.Series(False, index=hist.index)
    for kw in DIABETIC_COMPLICATION_KEYWORDS:
        comp_mask = comp_mask | hist["DESC_LOWER"].str.contains(kw.lower(), na=False, regex=False)
    comp_rows = hist[comp_mask]
    feats["known_complication_count"] = comp_rows["DESC_LOWER"].nunique() if len(comp_rows) > 0 else 0
    if len(comp_rows) > 0:
        feats["days_since_latest_complication"] = (cutoff - comp_rows["START"].max()).days
    recent = hist[(diab_mask | comp_mask) & (hist["START"] >= (cutoff - timedelta(days=90)))]
    feats["diab_activity_90d"] = len(recent)
    return feats


def sdoh_features_for_patient(cond_df, cutoff):
    feats = {feat: 0 for feat in SDOH_KEYWORDS}
    feats["sdoh_total_count"] = 0
    if cond_df is None or len(cond_df) == 0:
        return feats
    hist = cond_df[cond_df["START"] < cutoff]
    if len(hist) == 0:
        return feats
    for feat_name, keywords in SDOH_KEYWORDS.items():
        feats[feat_name] = int(matches_any_keyword(hist["DESC_LOWER"], keywords).any())
    feats["sdoh_total_count"] = sum(feats[f] for f in SDOH_KEYWORDS)
    return feats


def patient_demographics(pat_row, cutoff):
    feats = {}
    birthdate = pat_row.get("BIRTHDATE", None)
    if pd.notna(birthdate):
        feats["age_at_cutoff"] = max(0, (cutoff - pd.Timestamp(birthdate)).days // 365)
    else:
        feats["age_at_cutoff"] = np.nan
    gender = str(pat_row.get("GENDER", "")).strip().upper()
    feats["gender_M"] = 1 if gender == "M" else 0
    marital = str(pat_row.get("MARITAL", "")).strip().upper()
    feats["marital_M"] = 1 if marital == "M" else 0
    feats["marital_S"] = 1 if marital == "S" else 0
    try:
        feats["income"] = float(pat_row.get("INCOME", np.nan))
    except (ValueError, TypeError):
        feats["income"] = np.nan
    return feats


def compute_data_completeness(feat_dict):
    total = len(feat_dict)
    non_nan = sum(1 for v in feat_dict.values() if not (isinstance(v, float) and np.isnan(v)))
    score = non_nan / total if total > 0 else 0.0
    key_signals = ["enc_total_90d", "med_total_ever", "diag_total",
                   "lab_gfr_latest", "lab_hba1c_latest", "vital_systolic_bp_latest"]
    key_available = sum(1 for s in key_signals
                        if s in feat_dict and not (isinstance(feat_dict[s], float) and np.isnan(feat_dict[s])))
    key_score = key_available / len(key_signals)
    combined = 0.6 * score + 0.4 * key_score
    if combined >= 0.65:
        cat = "HIGH DATA AVAILABILITY"
    elif combined >= 0.35:
        cat = "MODERATE DATA AVAILABILITY"
    else:
        cat = "LOW DATA AVAILABILITY"
    return round(combined, 3), cat


def engineer_features_for_patient(pid, cutoff, pat_row, cond_df, enc_df, med_df, obs_df):
    feats = {"patient_id": pid, "cutoff_date": cutoff}
    feats.update(patient_demographics(pat_row, cutoff))
    feats.update(chronic_condition_features(cond_df, cutoff))
    feats.update(encounter_features_for_patient(enc_df, cutoff))
    feats.update(medication_features_for_patient(med_df, cutoff))
    feats.update(diagnosis_features_for_patient(cond_df, cutoff))
    feats.update(lab_features_for_patient(obs_df, cutoff))
    feats.update(vital_features_for_patient(obs_df, cutoff))
    feats.update(ckd_features_for_patient(cond_df, cutoff))
    feats.update(diabetes_features_for_patient(cond_df, cutoff))
    feats.update(sdoh_features_for_patient(cond_df, cutoff))
    return feats


def build_feature_dataframe(patients_df, conditions_df, encounters_df, medications_df,
                             observations_df, cutoff):
    """
    Builds one engineered feature row per patient, at the given cutoff
    (typically "now"), using vectorized groupby lookups instead of one
    Python-process-per-patient.
    """
    if len(patients_df) == 0:
        return pd.DataFrame()

    cond_g = {pid: g for pid, g in conditions_df.groupby("PATIENT")} if len(conditions_df) else {}
    enc_g = {pid: g for pid, g in encounters_df.groupby("PATIENT")} if len(encounters_df) else {}
    med_g = {pid: g for pid, g in medications_df.groupby("PATIENT")} if len(medications_df) else {}
    obs_g = {pid: g for pid, g in observations_df.groupby("PATIENT")} if len(observations_df) else {}

    pat_index = patients_df.set_index("Id")
    rows = []
    for pid in patients_df["Id"].tolist():
        pat_row = pat_index.loc[pid] if pid in pat_index.index else pd.Series(dtype=object)
        row = engineer_features_for_patient(
            pid, cutoff, pat_row,
            cond_g.get(pid), enc_g.get(pid), med_g.get(pid), obs_g.get(pid),
        )
        rows.append(row)
    return pd.DataFrame(rows)
