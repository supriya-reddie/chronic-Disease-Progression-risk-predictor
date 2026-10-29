"""
Risk tier classification. Thresholds come exclusively from thresholds.json
(frozen at training time) - never hard-coded here and never in Node/React.
"""


def assign_risk_tier(prob, low_thr, high_thr):
    if prob >= high_thr:
        return "HIGH"
    elif prob >= low_thr:
        return "MEDIUM"
    return "LOW"


def get_thresholds(thresholds_cfg, key):
    """key = 'acute' | 'progression'"""
    cfg = thresholds_cfg[key]
    high = cfg["selected"]
    low = cfg.get("low_threshold", high * 0.4)
    return low, high
