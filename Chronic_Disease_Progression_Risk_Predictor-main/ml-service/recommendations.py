"""
Care-management recommendation rules (payer / care-management perspective).

These are population-health workflow suggestions for a care manager, NOT
prescriptions or medical treatment instructions, per the project brief.
"""


def get_recommendations(acute_tier, progression_tier, feature_row):
    recs = []

    if acute_tier == "HIGH":
        recs.append("Care management outreach")
        recs.append("Recent utilization review")
        recs.append("Provider follow-up within 7 days")
    elif acute_tier == "MEDIUM":
        recs.append("Care-manager monitoring")

    if progression_tier == "HIGH":
        recs.append("Chronic disease follow-up")
        recs.append("Monitoring outreach")
        recs.append("Care-management review")
    elif progression_tier == "MEDIUM":
        recs.append("Schedule chronic-disease follow-up visit")

    if feature_row.get("sdoh_transport_barrier", 0) == 1:
        recs.append("Transportation support")
    if feature_row.get("sdoh_housing_insecurity", 0) == 1:
        recs.append("Housing support referral")
    if feature_row.get("sdoh_financial_stress", 0) == 1:
        recs.append("Financial assistance / social work referral")
    if feature_row.get("sdoh_social_isolation", 0) == 1:
        recs.append("Social support / community outreach referral")

    if (feature_row.get("med_churn_90d") or 0) >= 1.5 or (feature_row.get("med_changes_90d") or 0) >= 3:
        recs.append("Medication review")

    if not recs:
        recs.append("Continue routine monitoring")

    # de-duplicate, keep order
    seen = set()
    deduped = []
    for r in recs:
        if r not in seen:
            deduped.append(r)
            seen.add(r)
    return deduped


def get_primary_action(acute_tier, progression_tier):
    if acute_tier == "HIGH" or progression_tier == "HIGH":
        return "Prioritize for care-manager review and proactive follow-up."
    if acute_tier == "MEDIUM" or progression_tier == "MEDIUM":
        return "Consider care-manager monitoring and follow-up."
    return "Continue routine monitoring."
