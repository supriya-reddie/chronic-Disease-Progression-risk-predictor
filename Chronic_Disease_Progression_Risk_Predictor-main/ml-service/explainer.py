"""
Patient-level explanations for acute-event and progression risk.

Deliberately dependency-free: no SHAP/numba. Those pull in a JIT compiler
whose first-call warm-up can take 20-60+ seconds, which is long enough to
time out a synchronous single-patient request. Instead this uses occlusion
importance: for each clinically meaningful feature, its value is replaced
with the "missing" sentinel used at training time and the model is
re-scored; the drop in predicted probability is that feature's contribution
for THIS patient. It's computed fresh from the real frozen model every
time - nothing is hard-coded - and it's fast enough for both single-patient
and full-batch scoring.

Only features in FEATURE_LABELS are ever considered, so the UI never shows
a raw internal code like "enc_90d" - every displayed factor has a plain
clinical label.
"""
import logging

import numpy as np

import config

logger = logging.getLogger("cdprp-ml.explainer")


# Human-readable labels for the clinically meaningful features. This is
# also the ONLY set of features ever surfaced as a "top contributing
# factor" - anything not listed here is excluded from explanations rather
# than shown with a raw column name.
FEATURE_LABELS = {
    "enc_total_90d": "Recent healthcare visits (last 90 days)",
    "enc_ed_90d": "Emergency department visits (last 90 days)",
    "enc_ed_180d": "Emergency department visits (last 180 days)",
    "enc_inp_90d": "Hospital admissions (last 90 days)",
    "enc_inp_180d": "Hospital admissions (last 180 days)",
    "enc_uc_90d": "Urgent care visits (last 90 days)",
    "enc_acute_90d": "Acute care visits (last 90 days)",
    "enc_acute_365d": "Acute care visits (last year)",
    "enc_total_365d": "Total healthcare visits (last year)",
    "days_since_last_ed": "Days since last emergency visit",
    "days_since_last_inp": "Days since last hospital admission",
    "days_since_last_enc": "Days since last healthcare visit",
    "util_trend_90v365": "Rising healthcare use vs. yearly average",
    "util_accel": "Healthcare use trending up",
    "comorbidity_count": "Number of chronic conditions",
    "has_diabetes": "Diabetes",
    "has_ckd": "Chronic kidney disease",
    "has_chf": "Heart failure",
    "has_copd": "COPD",
    "has_cad": "Coronary artery disease",
    "has_hypertension": "High blood pressure",
    "has_afib": "Atrial fibrillation",
    "has_asthma": "Asthma",
    "ckd_stage_current": "Current kidney disease stage",
    "ckd_stage_change": "Kidney disease stage change",
    "ckd_stage_increased": "Worsening kidney disease",
    "ckd_activity_90d": "Recent kidney-related diagnoses",
    "days_since_ckd_dx": "Time since kidney disease diagnosis",
    "lab_gfr_latest": "Latest kidney function test (GFR)",
    "lab_gfr_slope": "Kidney function trend",
    "lab_gfr_change": "Kidney function change",
    "lab_creatinine_latest": "Latest creatinine level",
    "lab_creatinine_slope": "Creatinine trend",
    "lab_hba1c_latest": "Latest blood sugar control (HbA1c)",
    "lab_hba1c_slope": "Blood sugar control trend",
    "lab_glucose_latest": "Latest blood glucose",
    "lab_bun_latest": "Latest kidney function marker (BUN)",
    "known_complication_count": "Known diabetes complications",
    "days_since_latest_complication": "Time since last diabetes complication",
    "diab_duration_days": "Diabetes duration",
    "diab_activity_90d": "Recent diabetes-related activity",
    "med_changes_90d": "Recent medication changes",
    "med_churn_90d": "Medication turnover rate",
    "med_active_approx": "Number of active medications",
    "med_starts_90d": "New medications started (90 days)",
    "med_stops_90d": "Medications stopped (90 days)",
    "diag_total": "Total diagnoses on record",
    "diag_90d": "Recent diagnoses (90 days)",
    "diag_accel": "Diagnosis activity trending up",
    "sdoh_total_count": "Social/economic risk factors",
    "sdoh_housing_insecurity": "Housing insecurity",
    "sdoh_transport_barrier": "Transportation barriers",
    "sdoh_social_isolation": "Social isolation",
    "vital_systolic_bp_latest": "Latest systolic blood pressure",
    "vital_systolic_bp_change": "Blood pressure change",
    "age_at_cutoff": "Patient age",
    "chronic_duration_days": "Time living with chronic disease",
}

_OCCLUSION_CANDIDATES = list(FEATURE_LABELS.keys())


def humanize(feature_name):
    return FEATURE_LABELS.get(feature_name, feature_name.replace("_", " "))


def _occlusion_contributions_batch(model, X_arr, feature_cols, fill_value=config.MISSING_VALUE_FILL):
    """
    For each row, for each candidate feature, occlude that feature and
    measure the probability drop vs the original prediction. Batched per
    patient: one predict_proba call scores all candidate perturbations for
    that patient at once, so this stays fast even for 1,500 patients.
    """
    candidate_idx = [i for i, c in enumerate(feature_cols) if c in _OCCLUSION_CANDIDATES]
    n_rows, n_feats = X_arr.shape
    contributions = np.zeros((n_rows, n_feats), dtype=float)
    if not candidate_idx:
        return contributions

    base_proba = model.predict_proba(X_arr)[:, 1]

    for r in range(n_rows):
        base_row = X_arr[r]
        n_cand = len(candidate_idx)
        perturbed = np.tile(base_row, (n_cand, 1))
        for k, feat_idx in enumerate(candidate_idx):
            perturbed[k, feat_idx] = fill_value
        perturbed_proba = model.predict_proba(perturbed)[:, 1]
        deltas = base_proba[r] - perturbed_proba  # positive => feature raises risk
        for k, feat_idx in enumerate(candidate_idx):
            contributions[r, feat_idx] = deltas[k]
    return contributions


def compute_contributions_batch(model, X_arr, feature_cols):
    return _occlusion_contributions_batch(model, X_arr, feature_cols), "occlusion"


def _build_explanation_text(top_pos_factors, risk_type):
    if not top_pos_factors:
        return "Not enough recent activity to explain this " + risk_type + " risk score."
    labels = [f["label"] for f in top_pos_factors[:2]]
    if len(labels) == 1:
        return risk_type.capitalize() + " risk is mainly driven by: " + labels[0] + "."
    return risk_type.capitalize() + " risk is mainly driven by: " + labels[0] + " and " + labels[1] + "."


def explain_row(contributions_row, x_row, feature_cols, risk_type, top_n=3):
    """
    Ranks ONLY the clinically-labeled candidate features by contribution
    magnitude, so the UI never has to display a raw column name.
    """
    candidate_positions = [i for i, c in enumerate(feature_cols) if c in _OCCLUSION_CANDIDATES]
    ranked = sorted(candidate_positions, key=lambda i: abs(contributions_row[i]), reverse=True)

    top_factors = []
    for idx in ranked[:top_n]:
        val = float(x_row[idx])
        contrib = float(contributions_row[idx])
        if contrib == 0:
            continue
        top_factors.append({
            "feature": feature_cols[idx],
            "label": humanize(feature_cols[idx]),
            "value": None if val == config.MISSING_VALUE_FILL else round(val, 2),
            "shapValue": round(contrib, 5),
            "direction": "increases_risk" if contrib > 0 else "decreases_risk",
        })

    pos_factors = [f for f in top_factors if (f["shapValue"] or 0) > 0]
    explanation = _build_explanation_text(pos_factors, risk_type)
    return {"top_factors": top_factors, "explanation": explanation}
