import { useEffect, useState } from "react";
import TopBar from "../components/TopBar.jsx";
import LoadingRow from "../components/LoadingRow.jsx";
import EmptyState from "../components/EmptyState.jsx";
import RiskLegend from "../components/RiskLegend.jsx";
import RiskDistributionChart from "../charts/RiskDistributionChart.jsx";
import DiseaseDistributionChart from "../charts/DiseaseDistributionChart.jsx";
import { getDashboardSummary } from "../services/api.js";

export default function RiskAnalytics() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await getDashboardSummary();
        setSummary(data);
        setError(null);
      } catch (err) {
        setError(err.response?.data?.error || "Could not load analytics.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <>
        <TopBar title="Risk Analytics" subtitle="Population-level risk patterns" />
        <div className="content">
          <LoadingRow />
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <TopBar title="Risk Analytics" subtitle="Population-level risk patterns" />
        <div className="content">
          <EmptyState title="Couldn't load analytics" description={error} />
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar title="Risk Analytics" subtitle="How risk is spread across the scored patient population" />
      <div className="content">
        <div className="grid grid-2" style={{ marginBottom: 20 }}>
          <div className="card">
            <div className="card-title">Acute Risk</div>
            <div className="card-sub">Chance of needing urgent/emergency care in the next 90 days</div>
            <RiskDistributionChart data={summary.acuteRiskDistribution || []} />
          </div>
          <div className="card">
            <div className="card-title">Progression Risk</div>
            <div className="card-sub">Chance of a chronic condition getting worse</div>
            <RiskDistributionChart data={summary.progressionRiskDistribution || []} />
          </div>
        </div>

        <div className="card" style={{ marginBottom: 20 }}>
          <RiskLegend />
        </div>

        <div className="card">
          <div className="card-title">Chronic Conditions in the Population</div>
          <div className="card-sub">Number of scored patients with each condition on record</div>
          <DiseaseDistributionChart data={summary.chronicDiseaseDistribution || []} />
        </div>
      </div>
    </>
  );
}
