import os
import sys
import json
import pickle
import warnings
import logging
import traceback
from datetime import timedelta

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("CHRONICARE")

# ============================================================
# CONFIG
# ============================================================



DEV_BASE = os.path.join("data", "dev")
PATIENTS_FILE = os.path.join(DEV_BASE, "patients_chronic.csv")
CONDITIONS_FILE = os.path.join(DEV_BASE, "conditions_chronic.csv")
ENCOUNTERS_FILE = os.path.join(DEV_BASE, "encounters_chronic.csv")
MEDICATIONS_FILE = os.path.join(DEV_BASE, "medications_chronic.csv")
OBSERVATIONS_FILE = os.path.join(DEV_BASE, "observations_chronic.csv")

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

MIN_PRIOR_ENCOUNTERS = 2
MAX_CUTOFFS_PER_PATIENT = 40
PREDICTION_HORIZON_DAYS = 90
TEST_SPLIT_RATIO = 0.20
RANDOM_STATE = 42

# ============================================================
# KEYWORD DICTIONARIES (unchanged from the original - this is the real
# feature vocabulary, so your web app's numbers stay legitimate)
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
    "kidney due to diabetes", "microalbuminuria due to type 2 diabetes",
    "proteinuria due to type 2 diabetes", "neuropathy due to type 2 diabetes",
    "retinopathy due to type 2 diabetes", "blindness due to diabetes",
]
CKD_STAGE_MAP = {
    "chronic kidney disease stage 1": 1, "chronic kidney disease stage 2": 2,
    "chronic kidney disease stage 3": 3, "chronic kidney disease stage 4": 4,
    "end-stage renal disease": 5,
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
NON_FEATURE_COLS = {"patient_id", "cutoff_date", "label_acute_event", "label_progression"}

FEATURE_LABELS = {
    "enc_total_90d": "recent total healthcare encounters (90-day)",
    "enc_ed_90d": "emergency department visits (90-day)",
    "enc_inp_90d": "inpatient admissions (90-day)",
    "enc_acute_90d": "acute healthcare encounters (90-day)",
    "days_since_last_ed": "days since last emergency visit",
    "days_since_last_inp": "days since last inpatient admission",
    "util_accel": "healthcare utilization acceleration",
    "comorbidity_count": "multiple chronic conditions",
    "has_diabetes": "diabetes history", "has_ckd": "chronic kidney disease history",
    "has_chf": "heart failure history", "has_copd": "COPD history",
    "ckd_stage_current": "current CKD stage", "ckd_stage_increased": "previous CKD stage worsening",
    "lab_gfr_latest": "latest kidney filtration rate (GFR)", "lab_gfr_slope": "GFR trend (slope)",
    "lab_creatinine_latest": "latest creatinine level",
    "lab_hba1c_latest": "latest HbA1c (blood sugar control)", "lab_hba1c_slope": "HbA1c trend",
    "known_complication_count": "existing diabetic complication count",
    "med_changes_90d": "recent medication changes", "med_active_approx": "number of active medications",
    "diag_total": "total diagnosis count", "diag_accel": "diagnosis acceleration",
    "sdoh_total_count": "social determinants of health burden",
    "vital_systolic_bp_latest": "latest systolic blood pressure",
    "age_at_cutoff": "patient age", "chronic_duration_days": "chronic disease duration",
}


# ============================================================
# DATA LOADING 
# ============================================================


def validate_file_exists(path, label):
    if not os.path.exists(path):
        print("  [ERROR] Missing file: " + str(path) + " (" + str(label) + ")")
        return False
    print("  [OK] " + str(label) + ": " + f"{os.path.getsize(path)/1e6:.1f}" + " MB")
    return True


def load_patients(path):
    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.upper().strip() for c in df.columns]
    df["Id"] = df["ID"].astype(str).str.strip()
    df["BIRTHDATE"] = pd.to_datetime(df["BIRTHDATE"], errors="coerce")
    df["DEATHDATE"] = pd.to_datetime(df.get("DEATHDATE"), errors="coerce") if "DEATHDATE" in df.columns else pd.NaT
    return df


def load_conditions(path):
    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.upper().strip() for c in df.columns]
    df["PATIENT"] = df["PATIENT"].astype(str).str.strip()
    df["START"] = pd.to_datetime(df["START"], errors="coerce")
    df["STOP"] = pd.to_datetime(df.get("STOP"), errors="coerce") if "STOP" in df.columns else pd.NaT
    df["DESCRIPTION"] = df["DESCRIPTION"].fillna("").astype(str).str.strip()
    df["DESC_LOWER"] = df["DESCRIPTION"].str.lower()
    return df


def load_encounters(path):
    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.upper().strip() for c in df.columns]
    df["PATIENT"] = df["PATIENT"].astype(str).str.strip()
    df["START"] = pd.to_datetime(df["START"], errors="coerce", utc=True).dt.tz_localize(None)
    df["STOP"] = pd.to_datetime(df.get("STOP"), errors="coerce", utc=True).dt.tz_localize(None) if "STOP" in df.columns else pd.NaT
    df["ENCOUNTERCLASS"] = df["ENCOUNTERCLASS"].fillna("").astype(str).str.lower().str.strip()
    return df


def load_medications(path):
    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.upper().strip() for c in df.columns]
    df["PATIENT"] = df["PATIENT"].astype(str).str.strip()
    df["START"] = pd.to_datetime(df["START"], errors="coerce", utc=True).dt.tz_localize(None)
    df["STOP"] = pd.to_datetime(df.get("STOP"), errors="coerce", utc=True).dt.tz_localize(None) if "STOP" in df.columns else pd.NaT
    df["DESCRIPTION"] = df["DESCRIPTION"].fillna("").astype(str).str.strip()
    return df


def load_observations(path):
    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.upper().strip() for c in df.columns]
    df["PATIENT"] = df["PATIENT"].astype(str).str.strip()
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce", utc=True).dt.tz_localize(None)
    df["DESCRIPTION"] = df["DESCRIPTION"].fillna("").astype(str).str.strip()
    df["DESC_LOWER"] = df["DESCRIPTION"].str.lower()
    val_col = "VALUE_NUM" if "VALUE_NUM" in df.columns else ("VALUE" if "VALUE" in df.columns else None)
    df["VALUE_NUMERIC"] = pd.to_numeric(df[val_col], errors="coerce") if val_col else np.nan
    df["CATEGORY"] = df.get("CATEGORY", "unknown")
    df["CATEGORY"] = df["CATEGORY"].fillna("").astype(str).str.lower()
    return df


def build_patient_timelines(pat, cond, enc, med, obs):
    pat_ids = set(pat["Id"])
    cond_g = {pid: g.reset_index(drop=True) for pid, g in cond[cond["PATIENT"].isin(pat_ids)].groupby("PATIENT")}
    enc_g = {pid: g.reset_index(drop=True) for pid, g in enc[enc["PATIENT"].isin(pat_ids)].groupby("PATIENT")}
    med_g = {pid: g.reset_index(drop=True) for pid, g in med[med["PATIENT"].isin(pat_ids)].groupby("PATIENT")}
    obs_g = {pid: g.reset_index(drop=True) for pid, g in obs[obs["PATIENT"].isin(pat_ids)].groupby("PATIENT")}
    return cond_g, enc_g, med_g, obs_g


# ============================================================
# CUTOFF GENERATION 
# ============================================================
def generate_cutoffs_for_patient(pid, enc_df):
    if enc_df is None or len(enc_df) == 0:
        return []
    starts = enc_df["START"].dropna().sort_values().unique()
    if len(starts) < MIN_PRIOR_ENCOUNTERS:
        return []
    valid_positions = list(range(MIN_PRIOR_ENCOUNTERS, len(starts)))
    if not valid_positions:
        return []
    if len(valid_positions) <= MAX_CUTOFFS_PER_PATIENT:
        selected = valid_positions
    else:
        idx = np.round(np.linspace(0, len(valid_positions) - 1, MAX_CUTOFFS_PER_PATIENT)).astype(int)
        selected = [valid_positions[i] for i in idx]
    return [pd.Timestamp(starts[pos]) for pos in selected]


# ============================================================
# KEYWORD MATCHING 
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


# ============================================================
# FEATURE ENGINEERING (unchanged - this is the real feature set)
# ============================================================
def compute_slope(values, times_days):
    if len(values) < 2:
        return 0.0
    try:
        slope, _, _, _, _ = stats.linregress(times_days, values)
        return float(slope) if not np.isnan(slope) else 0.0
    except Exception:
        return 0.0

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
        mask = pd.Series(False, index=hist.index)
        for kw in keywords:
            mask = mask | hist["DESC_LOWER"].str.contains(kw, na=False, regex=False)
        rows = hist[mask].dropna(subset=["VALUE_NUMERIC"]).sort_values("DATE")
        prefix = "lab_" + lab_name
        if len(rows) == 0:
            continue
        vals, times = rows["VALUE_NUMERIC"].values, rows["DATE"].values
        feats[prefix + "_latest"] = float(vals[-1])
        feats[prefix + "_prev"] = float(vals[-2]) if len(vals) >= 2 else np.nan
        feats[prefix + "_mean"] = float(np.mean(vals))
        feats[prefix + "_min"] = float(np.min(vals))
        feats[prefix + "_max"] = float(np.max(vals))
        feats[prefix + "_std"] = float(np.std(vals)) if len(vals) >= 2 else 0.0
        feats[prefix + "_change"] = float(vals[-1] - vals[0]) if len(vals) >= 2 else 0.0
        feats[prefix + "_count"] = len(vals)
        feats[prefix + "_days_since"] = (cutoff - rows["DATE"].iloc[-1]).days
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
        mask = pd.Series(False, index=hist.index)
        for kw in keywords:
            mask = mask | hist["DESC_LOWER"].str.contains(kw, na=False, regex=False)
        rows = hist[mask].dropna(subset=["VALUE_NUMERIC"]).sort_values("DATE")
        prefix = "vital_" + v_name
        if len(rows) == 0:
            continue
        vals = rows["VALUE_NUMERIC"].values
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
        window = hist[hist["START"] >= cutoff - timedelta(days=w)]
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
        for key, name in [("ed", "emergency"), ("inp", "inpatient"), ("uc", "urgentcare")]:
            sub = hist[cls == name]
            feats["days_since_last_" + key] = (cutoff - sub["START"].max()).days if len(sub) > 0 else np.nan
    enc_90, enc_365, enc_180 = feats["enc_total_90d"], feats["enc_total_365d"] + 1e-6, feats["enc_total_180d"] + 1e-6
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
        feats["med_starts_" + str(w) + "d"] = len(hist[hist["START"] >= cutoff - timedelta(days=w)])
    for w in [90, 180]:
        stops = hist[(hist["STOP"].notna()) & (hist["STOP"] >= cutoff - timedelta(days=w)) & (hist["STOP"] < cutoff)]
        feats["med_stops_" + str(w) + "d"] = len(stops)
    feats["med_changes_90d"] = feats["med_starts_90d"] + feats["med_stops_90d"]
    feats["med_churn_90d"] = feats["med_changes_90d"] / (feats["med_starts_90d"] + 1e-6)
    feats["med_burden_total"] = int(pd.to_numeric(hist.get("DISPENSES"), errors="coerce").fillna(0).sum()) if "DISPENSES" in hist.columns else len(hist)
    feats["med_gaps_count"] = feats["med_stops_90d"]
    return feats

def diagnosis_features_for_patient(cond_df, cutoff):
    feats = {"diag_total": 0, "diag_chronic_count": 0, "diag_30d": 0, "diag_90d": 0,
             "diag_180d": 0, "diag_365d": 0, "diag_new_90d": 0, "diag_accel": 0.0,
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
        feats["diag_" + str(w) + "d"] = len(hist[hist["START"] >= cutoff - timedelta(days=w)])
    feats["diag_new_90d"] = feats["diag_90d"]
    feats["diag_accel"] = (feats["diag_90d"] / 90.0) - (feats["diag_365d"] / 365.0)
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
    all_mask = pd.Series(False, index=hist.index)
    for kws in CHRONIC_KEYWORDS.values():
        all_mask = all_mask | matches_any_keyword(hist["DESC_LOWER"], kws)
    chronic_hist = hist[all_mask]
    if len(chronic_hist) > 0:
        feats["chronic_duration_days"] = (cutoff - chronic_hist["START"].min()).days
        feats["days_since_last_chronic_dx"] = (cutoff - chronic_hist["START"].max()).days
    recent = chronic_hist[chronic_hist["START"] >= cutoff - timedelta(days=90)] if len(chronic_hist) > 0 else pd.DataFrame()
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
    feats["ckd_activity_90d"] = len(ckd_rows[ckd_rows["START"] >= cutoff - timedelta(days=90)])
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
    recent = hist[(diab_mask | comp_mask) & (hist["START"] >= cutoff - timedelta(days=90))]
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
    feats["age_at_cutoff"] = max(0, (cutoff - pd.Timestamp(birthdate)).days // 365) if pd.notna(birthdate) else np.nan
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
    key_available = sum(1 for s in key_signals if s in feat_dict and not (isinstance(feat_dict[s], float) and np.isnan(feat_dict[s])))
    combined = 0.6 * score + 0.4 * (key_available / len(key_signals))
    cat = "HIGH DATA AVAILABILITY" if combined >= 0.65 else ("MODERATE DATA AVAILABILITY" if combined >= 0.35 else "LOW DATA AVAILABILITY")
    return round(combined, 3), cat

def engineer_features_for_row(pid, cutoff, pat_row, cond_g, enc_g, med_g, obs_g):
    cond_df, enc_df, med_df, obs_df = cond_g.get(pid), enc_g.get(pid), med_g.get(pid), obs_g.get(pid)
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


# ============================================================
# LABELS 
# ============================================================
def build_acute_label(pid, cutoff, enc_g):
    enc_df = enc_g.get(pid)
    if enc_df is None or len(enc_df) == 0:
        return 0
    horizon_end = cutoff + timedelta(days=PREDICTION_HORIZON_DAYS)
    future = enc_df[(enc_df["START"] > cutoff) & (enc_df["START"] <= horizon_end) &
                     (enc_df["ENCOUNTERCLASS"].isin(ACUTE_ENCOUNTER_CLASSES))]
    return int(len(future) > 0)

def get_ckd_stage_at_cutoff(cond_df, cutoff):
    if cond_df is None or len(cond_df) == 0:
        return 0
    hist = cond_df[cond_df["START"] <= cutoff]
    ckd_mask = pd.Series(False, index=hist.index)
    for kw in CKD_STAGE_MAP:
        ckd_mask = ckd_mask | hist["DESC_LOWER"].str.contains(kw, na=False, regex=False)
    ckd_rows = hist[ckd_mask].copy()
    if len(ckd_rows) == 0:
        return 0
    ckd_rows["STAGE"] = ckd_rows["DESC_LOWER"].apply(get_ckd_stage)
    ckd_rows = ckd_rows[ckd_rows["STAGE"] > 0].sort_values("START")
    return int(ckd_rows["STAGE"].iloc[-1]) if len(ckd_rows) > 0 else 0

def build_progression_label(pid, cutoff, cond_g):
    cond_df = cond_g.get(pid)
    if cond_df is None or len(cond_df) == 0:
        return 0
    past, future = cond_df[cond_df["START"] <= cutoff], cond_df[cond_df["START"] > cutoff]
    ckd_past = get_ckd_stage_at_cutoff(cond_df, cutoff)
    if ckd_past > 0 and len(future) > 0:
        mask = pd.Series(False, index=future.index)
        for kw in CKD_STAGE_MAP:
            mask = mask | future["DESC_LOWER"].str.contains(kw, na=False, regex=False)
        fut_rows = future[mask].copy()
        if len(fut_rows) > 0:
            fut_rows["STAGE"] = fut_rows["DESC_LOWER"].apply(get_ckd_stage)
            fut_rows = fut_rows[fut_rows["STAGE"] > 0]
            if len(fut_rows) > 0 and fut_rows["STAGE"].max() > ckd_past:
                return 1
    if len(future) > 0:
        for kw in DIABETIC_COMPLICATION_KEYWORDS:
            kw_lower = kw.lower()
            if future["DESC_LOWER"].str.contains(kw_lower, na=False, regex=False).any():
                in_past = past["DESC_LOWER"].str.contains(kw_lower, na=False, regex=False).any() if len(past) > 0 else False
                if not in_past:
                    return 1
    return 0


# ============================================================
# DATASET CONSTRUCTION (unchanged)
# ============================================================
def build_dataset(pat, cond_g, enc_g, med_g, obs_g, build_labels=True):
    rows = []
    pat_index = pat.set_index("Id")
    for i, pid in enumerate(pat["Id"].tolist()):
        if i % 500 == 0:
            logger.info(f"  Processing patient {i+1}/{len(pat)}...")
        cutoffs = generate_cutoffs_for_patient(pid, enc_g.get(pid))
        if not cutoffs:
            continue
        pat_row = pat_index.loc[pid] if pid in pat_index.index else pd.Series(dtype=object)
        for cutoff in cutoffs:
            row = engineer_features_for_row(pid, cutoff, pat_row, cond_g, enc_g, med_g, obs_g)
            if build_labels:
                row["label_acute_event"] = build_acute_label(pid, cutoff, enc_g)
                row["label_progression"] = build_progression_label(pid, cutoff, cond_g)
            rows.append(row)
    df = pd.DataFrame(rows)
    logger.info("Dataset shape: " + str(df.shape))
    return df


# ============================================================
# LEAKAGE AUDIT + SPLIT (unchanged)
# ============================================================



def temporal_leakage_audit(feature_cols):
    print("\nTEMPORAL LEAKAGE AUDIT")
    problems = [c for c in feature_cols if c in ("label_acute_event", "label_progression") or "future" in c.lower()]
    if problems:
        print("  [FAIL] Suspicious columns in features: " + str(problems))
        return False
    print("  All features filtered by data['START'/'DATE'] < cutoff. PASS")
    return True

def patient_level_split(df):
    unique_patients = df["patient_id"].unique()
    np.random.seed(RANDOM_STATE)
    np.random.shuffle(unique_patients)
    n_test = max(1, int(len(unique_patients) * TEST_SPLIT_RATIO))
    test_patients = set(unique_patients[:n_test])
    train_patients = set(unique_patients[n_test:])
    return (df[df["patient_id"].isin(train_patients)].copy(),
            df[df["patient_id"].isin(test_patients)].copy(), train_patients, test_patients)


# ============================================================
# FEATURE PREP + METRICS (unchanged)
# ============================================================
def prepare_Xy(df, target, feature_cols=None):
    if feature_cols is None:
        feature_cols = [c for c in df.columns if c not in NON_FEATURE_COLS]
    X = df[feature_cols].copy()
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    return X, df[target].copy(), feature_cols

def get_class_ratio(y):
    vc = y.value_counts()
    return vc.get(0, 1) / max(vc.get(1, 1), 1)

def evaluate_model(y_true, y_proba, threshold=0.5, model_name="", target=""):
    from sklearn.metrics import (roc_auc_score, average_precision_score, accuracy_score,
                                  precision_score, recall_score, f1_score, confusion_matrix, brier_score_loss)
    y_pred = (y_proba >= threshold).astype(int)
    both = len(np.unique(y_true)) > 1
    m = {
        "model": model_name, "target": target, "threshold": threshold,
        "roc_auc": roc_auc_score(y_true, y_proba) if both else np.nan,
        "pr_auc": average_precision_score(y_true, y_proba) if both else np.nan,
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "brier": brier_score_loss(y_true, y_proba),
        "n_pos": int(y_true.sum()), "n_total": int(len(y_true)), "pos_rate": float(y_true.mean()),
    }
    cm = confusion_matrix(y_true, y_pred)
    m["tn"], m["fp"] = int(cm[0, 0]), int(cm[0, 1])
    m["fn"] = int(cm[1, 0]) if cm.shape[0] > 1 else 0
    m["tp"] = int(cm[1, 1]) if cm.shape[0] > 1 else 0
    return m


# ============================================================
# THRESHOLD SELECTION + CALIBRATION (unchanged)
# ============================================================
def select_threshold(y_true, y_proba):
    from sklearn.metrics import precision_recall_curve
    prec, rec, thresh = precision_recall_curve(y_true, y_proba)
    prec, rec = prec[:-1], rec[:-1]
    f1 = 2 * prec * rec / (prec + rec + 1e-9)
    best_idx = np.argmax(f1)
    thresh_f1 = float(thresh[best_idx])
    recall_cands = thresh[rec >= 0.70]
    thresh_recall = float(recall_cands[-1]) if len(recall_cands) > 0 else thresh_f1
    print(f"    F1-max threshold: {thresh_f1:.4f}  |  Recall>=0.70 threshold: {thresh_recall:.4f}")
    print("    -> Selecting recall-oriented threshold for care management")
    return {"threshold_f1": thresh_f1, "threshold_recall": thresh_recall, "selected": thresh_recall}

def compute_risk_tiers(threshold_selected):
    return max(0.05, threshold_selected * 0.4), threshold_selected

def assign_risk_tier(prob, low_thr, high_thr):
    return "HIGH" if prob >= high_thr else ("MEDIUM" if prob >= low_thr else "LOW")

def calibrate_model(model, X_cal, y_cal):
    from sklearn.calibration import CalibratedClassifierCV
    try:
        cal = CalibratedClassifierCV(model, method="isotonic", cv="prefit")
        cal.fit(X_cal, y_cal)
        return cal
    except Exception as e:
        logger.warning("Calibration failed (" + str(e) + "), using uncalibrated model.")
        return model


# ============================================================
# EXPLANATIONS - native feature importance instead of SHAP
# (this is the exact fallback path the original used when SHAP wasn't
# installed, promoted to the default so no extra dependency is required)
# ============================================================
def compute_global_importance(model, feature_cols, target_name):
    base = model.calibrated_classifiers_[0].estimator if hasattr(model, "calibrated_classifiers_") else model
    if hasattr(base, "feature_importances_"):
        imp = base.feature_importances_
    elif hasattr(base, "coef_"):
        imp = np.abs(base.coef_[0])
    else:
        return pd.DataFrame()
    return pd.DataFrame({"feature": feature_cols, "importance": imp, "target": target_name}) \
             .sort_values("importance", ascending=False)

def get_patient_contributions(model, X_row, feature_cols):
    base = model.calibrated_classifiers_[0].estimator if hasattr(model, "calibrated_classifiers_") else model
    try:
        if hasattr(base, "feature_importances_"):
            x_norm = X_row / (np.abs(X_row).max() + 1e-9)
            return base.feature_importances_ * x_norm
        elif hasattr(base, "coef_"):
            return base.coef_[0] * X_row
    except Exception:
        pass
    return np.zeros(len(feature_cols))

def build_human_readable_explanation(top_pos_factors, risk_type):
    if not top_pos_factors:
        return f"Insufficient signal to explain {risk_type} risk from available data."
    labels = [FEATURE_LABELS.get(f["feature"], f["feature"].replace("_", " ")) for f in top_pos_factors[:3]]
    if len(labels) == 1:
        return f"High {risk_type} risk is mainly associated with {labels[0]}."
    if len(labels) == 2:
        return f"High {risk_type} risk is mainly associated with {labels[0]} and {labels[1]}."
    return f"High {risk_type} risk is mainly associated with {labels[0]}, {labels[1]}, and {labels[2]}."

def explain_patient(model, X_row, feature_cols, prob, risk_tier, risk_type, top_n=5):
    contributions = get_patient_contributions(model, X_row, feature_cols)
    ranked_idx = np.argsort(np.abs(contributions))[::-1]
    top_factors = []
    for idx in ranked_idx[:top_n]:
        val = float(X_row[idx])
        top_factors.append({"feature": feature_cols[idx],
                             "patient_value": None if np.isnan(val) else val,
                             "shap_contribution": float(contributions[idx])})
    pos_factors = [f for f in top_factors if f["shap_contribution"] > 0]
    return {"probability": prob, "risk_tier": risk_tier, "top_factors": top_factors,
            "explanation": build_human_readable_explanation(pos_factors, risk_type)}

def get_recommended_action(acute_tier, prog_tier):
    if acute_tier == "HIGH" or prog_tier == "HIGH":
        return "Prioritize for care-manager review and proactive follow-up."
    if acute_tier == "MEDIUM" or prog_tier == "MEDIUM":
        return "Consider care-manager monitoring and follow-up."
    return "Continue routine monitoring."

def predict_and_explain(df, feature_cols, acute_model, prog_model, acute_thresholds, prog_thresholds):
    X, _, _ = prepare_Xy(df, "label_acute_event", feature_cols)
    X_arr = X.fillna(-999).values
    acute_proba = acute_model.predict_proba(X_arr)[:, 1]
    prog_proba = prog_model.predict_proba(X_arr)[:, 1]
    a_high, a_low = acute_thresholds["selected"], acute_thresholds.get("low_threshold", acute_thresholds["selected"] * 0.4)
    p_high, p_low = prog_thresholds["selected"], prog_thresholds.get("low_threshold", prog_thresholds["selected"] * 0.4)
    results = []
    for i in range(len(df)):
        row, x_row = df.iloc[i], X_arr[i]
        a_prob, p_prob = float(acute_proba[i]), float(prog_proba[i])
        a_tier, p_tier = assign_risk_tier(a_prob, a_low, a_high), assign_risk_tier(p_prob, p_low, p_high)
        a_expl = explain_patient(acute_model, x_row, feature_cols, a_prob, a_tier, "acute-event")
        p_expl = explain_patient(prog_model, x_row, feature_cols, p_prob, p_tier, "progression")
        feat_dict = {feature_cols[j]: float(x_row[j]) for j in range(len(feature_cols))}
        completeness_score, completeness_cat = compute_data_completeness(feat_dict)

        def pf(factors, idx):
            if idx < len(factors):
                f = factors[idx]
                v = f["patient_value"]
                return f["feature"], (round(v, 4) if v is not None else None), round(f["shap_contribution"], 4)
            return None, None, None

        a_f = [pf(a_expl["top_factors"], i) for i in range(3)]
        p_f = [pf(p_expl["top_factors"], i) for i in range(3)]
        results.append({
            "patient_id": row.get("patient_id", ""), "cutoff_date": str(row.get("cutoff_date", "")),
            "acute_risk_probability": round(a_prob, 4), "acute_risk_tier": a_tier,
            "acute_risk_flag": 1 if a_tier == "HIGH" else 0,
            "acute_top_factor_1": a_f[0][0], "acute_top_factor_1_value": a_f[0][1], "acute_top_factor_1_contribution": a_f[0][2],
            "acute_top_factor_2": a_f[1][0], "acute_top_factor_2_value": a_f[1][1], "acute_top_factor_2_contribution": a_f[1][2],
            "acute_top_factor_3": a_f[2][0], "acute_top_factor_3_value": a_f[2][1], "acute_top_factor_3_contribution": a_f[2][2],
            "acute_explanation": a_expl["explanation"],
            "progression_risk_probability": round(p_prob, 4), "progression_risk_tier": p_tier,
            "progression_risk_flag": 1 if p_tier == "HIGH" else 0,
            "progression_top_factor_1": p_f[0][0], "progression_top_factor_1_value": p_f[0][1], "progression_top_factor_1_contribution": p_f[0][2],
            "progression_top_factor_2": p_f[1][0], "progression_top_factor_2_value": p_f[1][1], "progression_top_factor_2_contribution": p_f[1][2],
            "progression_top_factor_3": p_f[2][0], "progression_top_factor_3_value": p_f[2][1], "progression_top_factor_3_contribution": p_f[2][2],
            "progression_explanation": p_expl["explanation"],
            "data_completeness_score": completeness_score, "prediction_confidence_category": completeness_cat,
            "recommended_action": get_recommended_action(a_tier, p_tier),
        })
    return pd.DataFrame(results)


# ============================================================
# MODEL COMPARISON - 2 models instead of 6, fixed hyperparameters
# instead of Optuna. Both models ship with scikit-learn: no lightgbm/
# catboost/optuna installs needed for production.
# ============================================================
def run_model_comparison(X_train, y_train, X_test, y_test, class_ratio, target_name):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler

    X_tr, X_te = X_train.fillna(-999), X_test.fillna(-999)
    all_metrics = [evaluate_model(y_test.values, np.full(len(y_test), float(y_train.mean())),
                                   threshold=float(y_train.mean()), model_name="MajorityBaseline", target=target_name)]
    trained = {}

    scaler = StandardScaler()
    X_tr_sc, X_te_sc = scaler.fit_transform(X_tr), scaler.transform(X_te)
    lr = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=RANDOM_STATE, C=0.1)
    lr.fit(X_tr_sc, y_train)
    lr_m = evaluate_model(y_test.values, lr.predict_proba(X_te_sc)[:, 1], model_name="LogisticRegression", target=target_name)
    all_metrics.append(lr_m)
    trained["LogisticRegression"] = (lr, X_tr_sc, X_te_sc)
    print(f"  [LogisticRegression]    PR-AUC={lr_m['pr_auc']:.4f}  ROC-AUC={lr_m['roc_auc']:.4f}")

    histgb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_depth=6,
                                             class_weight="balanced", random_state=RANDOM_STATE)
    histgb.fit(X_tr.values, y_train.values)
    hgb_m = evaluate_model(y_test.values, histgb.predict_proba(X_te.values)[:, 1], model_name="HistGradientBoosting", target=target_name)
    all_metrics.append(hgb_m)
    trained["HistGradientBoosting"] = (histgb, X_tr.values, X_te.values)
    print(f"  [HistGradientBoosting]  PR-AUC={hgb_m['pr_auc']:.4f}  ROC-AUC={hgb_m['roc_auc']:.4f}")

    candidates = [m for m in all_metrics if m["model"] != "MajorityBaseline"]
    best_name = max(candidates, key=lambda m: (m["pr_auc"] if not np.isnan(m["pr_auc"]) else 0))["model"]
    print(f"  -> Best model for {target_name}: {best_name}")
    return trained[best_name][0], all_metrics, best_name


# ============================================================
# MAIN PIPELINE - one run, in memory, no stage/checkpoint dance
# ============================================================
def main():
    print("=" * 70)
    print("CHRONICARE PIPELINE - MID-LEVEL VERSION")
    print("=" * 70)

    # ---- 1. Load & validate ----
    print("\n[1/7] Loading data...")
    required = [(PATIENTS_FILE, "patients"), (CONDITIONS_FILE, "conditions"),
                (ENCOUNTERS_FILE, "encounters"), (MEDICATIONS_FILE, "medications"),
                (OBSERVATIONS_FILE, "observations")]
    if not all(validate_file_exists(p, l) for p, l in required):
        print("[FATAL] Missing dev files. Check DEV_BASE at the top of this script.")
        sys.exit(1)
    pat, cond, enc, med, obs = (load_patients(PATIENTS_FILE), load_conditions(CONDITIONS_FILE),
                                 load_encounters(ENCOUNTERS_FILE), load_medications(MEDICATIONS_FILE),
                                 load_observations(OBSERVATIONS_FILE))
    print(f"  {len(pat):,} patients | {len(cond):,} conditions | {len(enc):,} encounters | "
          f"{len(med):,} medications | {len(obs):,} observations")

    # ---- 2. Feature engineering + labels ----
    print("\n[2/7] Building timelines, engineering features + labels...")
    cond_g, enc_g, med_g, obs_g = build_patient_timelines(pat, cond, enc, med, obs)
    df_all = build_dataset(pat, cond_g, enc_g, med_g, obs_g, build_labels=True)
    if len(df_all) == 0:
        print("[FATAL] No rows generated - check MIN_PRIOR_ENCOUNTERS and your encounter data.")
        sys.exit(1)
    print(f"  Rows: {len(df_all):,} | Patients: {df_all['patient_id'].nunique():,}")
    print(f"  Acute positive rate: {df_all['label_acute_event'].mean():.2%} | "
          f"Progression positive rate: {df_all['label_progression'].mean():.2%}")

    # ---- 3. Leakage audit + split ----
    print("\n[3/7] Leakage audit + patient-level split...")
    feature_cols = [c for c in df_all.columns if c not in NON_FEATURE_COLS]
    if not temporal_leakage_audit(feature_cols):
        sys.exit(1)
    train_df, test_df, train_patients, test_patients = patient_level_split(df_all)
    print(f"  Train: {len(train_patients):,} patients / {len(train_df):,} rows | "
          f"Test: {len(test_patients):,} patients / {len(test_df):,} rows")
    with open(os.path.join(OUTPUT_DIR, "feature_columns.json"), "w") as f:
        json.dump(feature_cols, f, indent=2)

    # ---- 4. Model comparison ----
    print("\n[4/7] Model comparison...")
    X_train_df, y_acute_train, _ = prepare_Xy(train_df, "label_acute_event", feature_cols)
    X_test_df, y_acute_test, _ = prepare_Xy(test_df, "label_acute_event", feature_cols)
    _, y_prog_train, _ = prepare_Xy(train_df, "label_progression", feature_cols)
    _, y_prog_test, _ = prepare_Xy(test_df, "label_progression", feature_cols)

    print("\n  [ACUTE EVENT]")
    best_acute_obj, acute_metrics, best_acute_name = run_model_comparison(
        X_train_df, y_acute_train, X_test_df, y_acute_test, get_class_ratio(y_acute_train), "acute_event")
    print("\n  [PROGRESSION]")
    best_prog_obj, prog_metrics, best_prog_name = run_model_comparison(
        X_train_df, y_prog_train, X_test_df, y_prog_test, get_class_ratio(y_prog_train), "progression")
    pd.DataFrame(acute_metrics + prog_metrics).to_csv(os.path.join(OUTPUT_DIR, "model_comparison.csv"), index=False)

    # ---- 5. Threshold selection + final refit + calibration ----
    print("\n[5/7] Threshold selection, final refit, calibration...")
    np.random.seed(RANDOM_STATE)
    train_pids = train_df["patient_id"].unique()
    np.random.shuffle(train_pids)
    val_pids = set(train_pids[:max(1, int(len(train_pids) * 0.20))])
    val_df, train_only_df = train_df[train_df["patient_id"].isin(val_pids)], train_df[~train_df["patient_id"].isin(val_pids)]
    X_val_df, y_acute_val, _ = prepare_Xy(val_df, "label_acute_event", feature_cols)
    _, y_prog_val, _ = prepare_Xy(val_df, "label_progression", feature_cols)
    X_val_arr = X_val_df.fillna(-999).values
    X_to_df, y_acute_to, _ = prepare_Xy(train_only_df, "label_acute_event", feature_cols)
    _, y_prog_to, _ = prepare_Xy(train_only_df, "label_progression", feature_cols)
    X_to_arr = X_to_df.fillna(-999).values

    def refit_and_calibrate(best_obj, X_to, y_to, X_val, y_val, name):
        print(f"  Refitting {name}...")
        refit_model = None
        try:
            refit_model = type(best_obj)(**best_obj.get_params())
            refit_model.fit(X_to, y_to.values)
            val_proba = refit_model.predict_proba(X_val)[:, 1]
        except Exception as e:
            print(f"  Warning refitting {name}: {e}")
            refit_model = best_obj
            val_proba = best_obj.predict_proba(X_val)[:, 1]
        thresholds = select_threshold(y_val.values, val_proba)
        low, _ = compute_risk_tiers(thresholds["selected"])
        thresholds["low_threshold"] = low
        final_model = calibrate_model(refit_model, X_val, y_val.values)
        return final_model, thresholds

    final_acute, acute_thresholds = refit_and_calibrate(best_acute_obj, X_to_arr, y_acute_to, X_val_arr, y_acute_val, best_acute_name)
    final_prog, prog_thresholds = refit_and_calibrate(best_prog_obj, X_to_arr, y_prog_to, X_val_arr, y_prog_val, best_prog_name)

    with open(os.path.join(OUTPUT_DIR, "acute_model.pkl"), "wb") as f:
        pickle.dump(final_acute, f)
    with open(os.path.join(OUTPUT_DIR, "progression_model.pkl"), "wb") as f:
        pickle.dump(final_prog, f)
    with open(os.path.join(OUTPUT_DIR, "thresholds.json"), "w") as f:
        json.dump({"acute": acute_thresholds, "progression": prog_thresholds}, f, indent=2)

    # ---- 6. Train + test evaluation (all metrics, both splits) + feature importance ----
    print("\n[6/7] Train + test evaluation (all metrics) + feature importance...")
    X_train_arr = X_train_df.fillna(-999).values
    X_test_arr = X_test_df.fillna(-999).values

    acute_train_m = evaluate_model(y_acute_train.values, final_acute.predict_proba(X_train_arr)[:, 1],
                                    threshold=acute_thresholds["selected"], model_name="Final", target="acute_event")
    acute_test_m = evaluate_model(y_acute_test.values, final_acute.predict_proba(X_test_arr)[:, 1],
                                   threshold=acute_thresholds["selected"], model_name="Final", target="acute_event")
    prog_train_m = evaluate_model(y_prog_train.values, final_prog.predict_proba(X_train_arr)[:, 1],
                                   threshold=prog_thresholds["selected"], model_name="Final", target="progression")
    prog_test_m = evaluate_model(y_prog_test.values, final_prog.predict_proba(X_test_arr)[:, 1],
                                  threshold=prog_thresholds["selected"], model_name="Final", target="progression")

    acute_train_m["split"], acute_test_m["split"] = "train", "test"
    prog_train_m["split"], prog_test_m["split"] = "train", "test"

    metrics_df = pd.DataFrame([acute_train_m, acute_test_m, prog_train_m, prog_test_m])
    # put split/target/model first for readability, keep every metric column
    lead_cols = ["target", "split", "model", "threshold"]
    other_cols = [c for c in metrics_df.columns if c not in lead_cols]
    metrics_df = metrics_df[lead_cols + other_cols]
    metrics_df.to_csv(os.path.join(OUTPUT_DIR, "train_test_metrics.csv"), index=False)

    print("\n  ACUTE EVENT")
    print(f"    Train -> ROC-AUC={acute_train_m['roc_auc']:.4f}  PR-AUC={acute_train_m['pr_auc']:.4f}  "
          f"Acc={acute_train_m['accuracy']:.4f}  Prec={acute_train_m['precision']:.4f}  "
          f"Recall={acute_train_m['recall']:.4f}  F1={acute_train_m['f1']:.4f}  Brier={acute_train_m['brier']:.4f}")
    print(f"    Test  -> ROC-AUC={acute_test_m['roc_auc']:.4f}  PR-AUC={acute_test_m['pr_auc']:.4f}  "
          f"Acc={acute_test_m['accuracy']:.4f}  Prec={acute_test_m['precision']:.4f}  "
          f"Recall={acute_test_m['recall']:.4f}  F1={acute_test_m['f1']:.4f}  Brier={acute_test_m['brier']:.4f}")
    print("\n  PROGRESSION")
    print(f"    Train -> ROC-AUC={prog_train_m['roc_auc']:.4f}  PR-AUC={prog_train_m['pr_auc']:.4f}  "
          f"Acc={prog_train_m['accuracy']:.4f}  Prec={prog_train_m['precision']:.4f}  "
          f"Recall={prog_train_m['recall']:.4f}  F1={prog_train_m['f1']:.4f}  Brier={prog_train_m['brier']:.4f}")
    print(f"    Test  -> ROC-AUC={prog_test_m['roc_auc']:.4f}  PR-AUC={prog_test_m['pr_auc']:.4f}  "
          f"Acc={prog_test_m['accuracy']:.4f}  Prec={prog_test_m['precision']:.4f}  "
          f"Recall={prog_test_m['recall']:.4f}  F1={prog_test_m['f1']:.4f}  Brier={prog_test_m['brier']:.4f}")

    train_test_gap_note = (
        f"  Note: a large train-vs-test gap (e.g. train ROC-AUC much higher than test) is a sign of "
        f"overfitting - worth mentioning either way in a viva."
    )
    print("\n" + train_test_gap_note)

    ai = compute_global_importance(final_acute, feature_cols, "acute_event")
    pi = compute_global_importance(final_prog, feature_cols, "progression")
    pd.concat([ai, pi], ignore_index=True).to_csv(os.path.join(OUTPUT_DIR, "feature_importance.csv"), index=False)

    test_preds = predict_and_explain(test_df, feature_cols, final_acute, final_prog, acute_thresholds, prog_thresholds)
    test_preds["true_acute_event"] = y_acute_test.values
    test_preds["true_progression"] = y_prog_test.values
    test_preds.to_csv(os.path.join(OUTPUT_DIR, "test_predictions.csv"), index=False)
    print(f"\n[7/7] Saved per-patient test predictions with explanations: {len(test_preds):,} rows")

    print("\n" + "=" * 70)
    print("DONE. Files written to ./" + OUTPUT_DIR + "/")
    print("=" * 70)


if __name__ == "__main__":
    main()
